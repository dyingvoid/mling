from __future__ import annotations

from pathlib import Path
from typing import Protocol

from mling.bookparse.options import Options
from mling.domain import Book


class Extractor(Protocol):
    extensions: tuple[str, ...]

    def extract(self, path: Path, *, options: Options) -> Book: ...
