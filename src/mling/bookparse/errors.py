from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mling.domain import Book


class BookParseError(Exception):
    pass


class UnsupportedFormatError(BookParseError):
    def __init__(self, suffix: str) -> None:
        self.suffix = suffix
        super().__init__(f"unsupported book format: {suffix or '<none>'}")


class ExtractionError(BookParseError):
    def __init__(self, source: str | Path, reason: str) -> None:
        self.source = Path(source)
        self.reason = reason
        super().__init__(f"{self.source}: {reason}")


@dataclass(frozen=True, slots=True)
class FileError:
    path: Path
    error: BookParseError


@dataclass(frozen=True, slots=True)
class BatchResult:
    books: tuple[Book, ...]
    errors: tuple[FileError, ...]
    skipped: tuple[Path, ...]

    @property
    def ok(self) -> bool:
        return not self.errors
