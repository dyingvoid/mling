from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from mling.bookparse.errors import BatchResult, BookParseError, FileError
from mling.bookparse.options import Options
from mling.bookparse.registry import DEFAULT_REGISTRY, ExtractorRegistry
from mling.domain import Book


def parse_book(
    path: str | Path,
    *,
    options: Options | None = None,
    base_dir: str | Path | None = None,
    registry: ExtractorRegistry | None = None,
) -> Book:
    book_path = Path(path)
    extractor = (registry or DEFAULT_REGISTRY).get(book_path)
    book = extractor.extract(book_path, options=options or Options())
    return replace(book, source=_source(book_path, base_dir))


def parse_books(
    root: str | Path,
    *,
    options: Options | None = None,
    registry: ExtractorRegistry | None = None,
) -> BatchResult:
    root_path = Path(root)
    if not root_path.is_dir():
        raise NotADirectoryError(root_path)

    active = registry or DEFAULT_REGISTRY
    books: list[Book] = []
    errors: list[FileError] = []
    skipped: list[Path] = []

    for path in sorted(root_path.rglob("*")):
        if not path.is_file() or _is_hidden(path, root_path):
            continue
        if not active.supports(path):
            skipped.append(path)
            continue
        try:
            books.append(parse_book(path, options=options, base_dir=root_path, registry=active))
        except BookParseError as exc:
            errors.append(FileError(path=path, error=exc))

    return BatchResult(books=tuple(books), errors=tuple(errors), skipped=tuple(skipped))


def _source(path: Path, base_dir: str | Path | None) -> str:
    if base_dir is None:
        return path.as_posix()
    try:
        return path.relative_to(base_dir).as_posix()
    except ValueError:
        return path.as_posix()


def _is_hidden(path: Path, root: Path) -> bool:
    return any(part.startswith(".") for part in path.relative_to(root).parts)
