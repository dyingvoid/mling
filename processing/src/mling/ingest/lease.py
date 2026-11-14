from __future__ import annotations

import os
import socket
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import Engine, text

from mling.ingest.errors import LeaseHeldError, LeaseLostError
from mling.ingest.sql import quote_identifier


@dataclass(frozen=True, slots=True)
class Lease:
    checksum: str
    token: uuid.UUID
    owner: str
    source: str
    expires_at: datetime


class LeaseStore(Protocol):
    def acquire(self, checksum: str, source: str) -> Lease: ...

    def renew(self, lease: Lease) -> Lease: ...

    def release(self, lease: Lease) -> None: ...


class BookLeaseStore:
    def __init__(
        self,
        engine: Engine,
        *,
        ttl_seconds: int,
        owner: str | None = None,
        table_name: str = "mling_book_leases",
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("lease ttl must be positive")

        table = quote_identifier(table_name)
        self._engine = engine
        self._ttl_seconds = ttl_seconds
        self._owner = owner or _default_owner()
        self._acquire_sql = text(
            f"""
            INSERT INTO {table} (checksum, token, owner, source, expires_at)
            VALUES (
                :checksum,
                :token,
                :owner,
                :source,
                now() + make_interval(secs => :ttl)
            )
            ON CONFLICT (checksum) DO UPDATE
               SET token = EXCLUDED.token,
                   owner = EXCLUDED.owner,
                   source = EXCLUDED.source,
                   started_at = now(),
                   expires_at = EXCLUDED.expires_at
             WHERE {table}.expires_at < now()
            RETURNING token, expires_at
            """
        )
        self._renew_sql = text(
            f"""
            UPDATE {table}
               SET expires_at = now() + make_interval(secs => :ttl)
             WHERE checksum = :checksum AND token = :token
            RETURNING expires_at
            """
        )
        self._release_sql = text(
            f"DELETE FROM {table} WHERE checksum = :checksum AND token = :token"
        )
        self._holder_sql = text(
            f"SELECT owner FROM {table} WHERE checksum = :checksum"
        )

    def acquire(self, checksum: str, source: str) -> Lease:
        token = uuid.uuid4()
        with self._engine.begin() as connection:
            row = connection.execute(
                self._acquire_sql,
                {
                    "checksum": checksum,
                    "token": token,
                    "owner": self._owner,
                    "source": source,
                    "ttl": self._ttl_seconds,
                },
            ).first()

        if row is None:
            with self._engine.connect() as connection:
                holder = connection.execute(
                    self._holder_sql, {"checksum": checksum}
                ).scalar()
            raise LeaseHeldError(checksum, holder or "another worker")
        return Lease(
            checksum=checksum,
            token=row.token,
            owner=self._owner,
            source=source,
            expires_at=row.expires_at,
        )

    def renew(self, lease: Lease) -> Lease:
        with self._engine.begin() as connection:
            row = connection.execute(
                self._renew_sql,
                {
                    "checksum": lease.checksum,
                    "token": lease.token,
                    "ttl": self._ttl_seconds,
                },
            ).first()

        if row is None:
            raise LeaseLostError(lease.checksum)
        return Lease(
            checksum=lease.checksum,
            token=lease.token,
            owner=lease.owner,
            source=lease.source,
            expires_at=row.expires_at,
        )

    def release(self, lease: Lease) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                self._release_sql,
                {"checksum": lease.checksum, "token": lease.token},
            )


def _default_owner() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"
