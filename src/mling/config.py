from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import quote_plus


def _env(name: str, default: str) -> str:
    return os.getenv(name) or default


@dataclass(frozen=True, slots=True)
class Settings:
    embedding_model: str
    embedding_base_url: str
    embedding_api_key: str
    embedding_dimension: int
    embedding_batch_size: int
    embedding_timeout: float
    embedding_query_instruction: str
    ingest_lease_timeout_seconds: int
    ingest_embed_batch_size: int
    table_name: str
    postgres_dsn: str

    @classmethod
    def from_env(cls) -> Settings:
        host = _env("TEI_HOST", "localhost")
        port = _env("TEI_PORT", "8090")
        base_url = _env("EMBEDDING_BASE_URL", f"http://{host}:{port}/v1")

        return cls(
            embedding_model=_env("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"),
            embedding_base_url=base_url,
            embedding_api_key=_env("EMBEDDING_API_KEY", "local"),
            embedding_dimension=int(_env("EMBEDDING_DIMENSION", "384")),
            embedding_batch_size=int(_env("EMBEDDING_BATCH_SIZE", "16")),
            embedding_timeout=float(_env("EMBEDDING_TIMEOUT", "30")),
            embedding_query_instruction=_env(
                "EMBEDDING_QUERY_INSTRUCTION",
                "Represent this sentence for searching relevant passages: ",
            ),
            ingest_lease_timeout_seconds=int(
                _env("INGEST_LEASE_TIMEOUT_SECONDS", "300")
            ),
            ingest_embed_batch_size=int(_env("INGEST_EMBED_BATCH_SIZE", "64")),
            table_name=_env("PGVECTOR_TABLE", "mling_documents"),
            postgres_dsn=_env("DATABASE_URL", _postgres_dsn()),
        )


def _postgres_dsn() -> str:
    user = quote_plus(_env("POSTGRES_USER", "postgres"))
    password = quote_plus(_env("POSTGRES_PASSWORD", "postgres"))
    host = _env("POSTGRES_HOST", "localhost")
    port = _env("POSTGRES_PORT", "5432")
    database = quote_plus(_env("POSTGRES_DB", "mling"))
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}"
