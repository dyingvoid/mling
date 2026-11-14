from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True, slots=True)
class SourceFile:
    path: Path
    checksum: str
    size_bytes: int

    @property
    def stem(self) -> str:
        return self.path.stem

    @classmethod
    def from_path(cls, path: str | Path) -> SourceFile:
        source = Path(path)
        checksum, size_bytes = checksum_file(source)
        return cls(path=source, checksum=checksum, size_bytes=size_bytes)


def checksum_file(path: str | Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size_bytes = 0
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(_CHUNK_SIZE), b""):
            digest.update(block)
            size_bytes += len(block)
    return digest.hexdigest(), size_bytes
