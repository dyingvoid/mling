from __future__ import annotations

from pathlib import Path


class IngestionError(Exception):
    pass


class LeaseHeldError(IngestionError):
    def __init__(self, checksum: str, owner: str) -> None:
        self.checksum = checksum
        self.owner = owner
        super().__init__(f"book {checksum} is already being ingested by {owner}")


class LeaseLostError(IngestionError):
    def __init__(self, checksum: str) -> None:
        self.checksum = checksum
        super().__init__(f"lease for book {checksum} is no longer held by this worker")


class EmptyBookError(IngestionError):
    def __init__(self, source: str | Path) -> None:
        self.source = Path(source)
        super().__init__(f"{self.source}: no extractable text")
