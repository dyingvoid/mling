from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from mling.bookparse.errors import ExtractionError
from mling.bookparse.normalize import normalize_text
from mling.bookparse.options import Options
from mling.domain import Book, Page

_METADATA_NAMES = {
    "creationdate": "creation_date",
    "moddate": "mod_date",
}


class PdfExtractor:
    extensions = (".pdf",)

    def extract(self, path: Path, *, options: Options) -> Book:
        try:
            reader = PdfReader(str(path))
            if reader.is_encrypted and not reader.decrypt(""):
                raise ExtractionError(path, "document is encrypted")
            metadata = _read_metadata(reader)
            pages = _read_pages(reader, path, options)
        except ExtractionError:
            raise
        except Exception as exc:
            raise ExtractionError(path, str(exc) or exc.__class__.__name__) from exc

        title = metadata.get("title") or path.stem
        return Book(
            title=title,
            source=path.name,
            format="pdf",
            pages=pages,
            metadata=metadata,
        )


def _read_pages(reader: PdfReader, path: Path, options: Options) -> tuple[Page, ...]:
    pages: list[Page] = []
    for number, raw_page in enumerate(reader.pages, start=1):
        try:
            raw = raw_page.extract_text() or ""
        except Exception as exc:
            raise ExtractionError(path, f"page {number}: {exc}") from exc
        text = normalize_text(raw, dehyphenate=options.dehyphenate)
        if not text and not options.keep_blank_pages:
            continue
        pages.append(Page(number=number, text=text))
    return tuple(pages)


def _read_metadata(reader: PdfReader) -> dict[str, str]:
    info = reader.metadata
    if info is None:
        return {}
    metadata: dict[str, str] = {}
    for key, value in info.items():
        if value is None:
            continue
        name = str(key).lstrip("/").lower()
        text = str(value).strip()
        if text:
            metadata[_METADATA_NAMES.get(name, name)] = text
    return metadata
