"""Manual inspection tool for parsed books.

THIS IS A TEST/DEBUG CLI ONLY.

It exists so the parser can be poked at by hand while the real pipeline (the
embedding and storage layers) is being built. It is not part of the application
surface, nothing else imports it, and it may be deleted once the production
entrypoint exists. Do not build features on top of it. Use `mling-ingest`
(`mling.ingest.cli`) for real ingestion.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from mling.bookparse import Options, parse_book
from mling.bookparse.errors import BookParseError
from mling.domain import Book


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mling-bookparse-test",
        description="Test-only PDF inspection CLI. Not part of the application.",
    )
    parser.add_argument("book", nargs="?", help="path to a PDF; prompted for if omitted")
    parser.add_argument("--dehyphenate", action="store_true", help="join words broken across lines")
    parser.add_argument(
        "--drop-blank-pages",
        action="store_true",
        help="omit pages whose extracted text is empty",
    )
    args = parser.parse_args(argv)

    path = args.book or _prompt_path()
    if not path:
        print("no book given", file=sys.stderr)
        return 2

    options = Options(
        dehyphenate=args.dehyphenate,
        keep_blank_pages=not args.drop_blank_pages,
    )
    try:
        book = parse_book(path, options=options)
    except (BookParseError, OSError) as exc:
        print(f"failed to parse {path}: {exc}", file=sys.stderr)
        return 1

    _print_summary(book)
    return _page_loop(book)


def _prompt_path() -> str:
    try:
        return input("book> ").strip().strip("'\"")
    except (EOFError, KeyboardInterrupt):
        return ""


def _print_summary(book: Book) -> None:
    print(f"title:  {book.title}")
    print(f"source: {book.source}")
    print(f"pages:  {len(book)}")
    if book.metadata:
        details = ", ".join(f"{key}={value}" for key, value in book.metadata.items())
        print(f"meta:   {details}")
    print("enter a page number, 'i' for info, or 'q' to quit")


def _page_loop(book: Book) -> int:
    numbers = [page.number for page in book.pages]
    while True:
        try:
            raw = input("page> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if not raw:
            continue
        if raw.lower() in {"q", "quit", "exit"}:
            return 0
        if raw.lower() in {"i", "info"}:
            _print_summary(book)
            continue

        try:
            number = int(raw)
        except ValueError:
            print(f"not a page number: {raw!r}")
            continue

        try:
            page = book.page(number)
        except KeyError:
            print(f"page {number} not found (available: {_range_hint(numbers)})")
            continue

        print(f"--- page {page.number} ({len(page.text)} chars) ---")
        print(page.text if page.text else "<no text on this page>")


def _range_hint(numbers: list[int]) -> str:
    if not numbers:
        return "none"
    return f"{min(numbers)}..{max(numbers)}"


if __name__ == "__main__":
    raise SystemExit(main())
