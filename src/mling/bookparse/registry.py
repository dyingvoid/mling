from __future__ import annotations

from pathlib import Path

from mling.bookparse.errors import UnsupportedFormatError
from mling.bookparse.extractors.base import Extractor
from mling.bookparse.extractors.pdf import PdfExtractor


class ExtractorRegistry:
    def __init__(self, extractors: tuple[Extractor, ...] | None = None) -> None:
        self._extractors = extractors or (PdfExtractor(),)
        self._by_extension: dict[str, Extractor] = {
            extension: extractor
            for extractor in self._extractors
            for extension in extractor.extensions
        }

    @property
    def extensions(self) -> tuple[str, ...]:
        return tuple(self._by_extension)

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() in self._by_extension

    def get(self, path: Path) -> Extractor:
        suffix = path.suffix.lower()
        extractor = self._by_extension.get(suffix)
        if extractor is None:
            raise UnsupportedFormatError(suffix)
        return extractor


DEFAULT_REGISTRY = ExtractorRegistry()
