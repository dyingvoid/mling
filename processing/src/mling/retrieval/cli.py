"""Command line entrypoint for book retrieval."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict

from mling.retrieval.models import RetrievalHit
from mling.retrieval.options import DEFAULT_LIMIT, RetrievalOptions
from mling.retrieval.search import retrieve


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    options = RetrievalOptions(
        book_name=args.book_name,
        query=args.query,
        limit=args.limit,
        from_page=args.from_page,
        to_page=args.to_page,
    )

    try:
        hits = retrieve(options)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"retrieval failed: {exc}", file=sys.stderr)
        return 1

    if not hits:
        print("no matches found")
        return 0

    if args.json:
        print(json.dumps([asdict(hit) for hit in hits], ensure_ascii=False, indent=2))
    else:
        _print_hits(hits)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mling-retrieve",
        description=(
            "Embed a query and return the closest stored chunks for a book, "
            "optionally restricted to a page range."
        ),
    )
    parser.add_argument(
        "--book",
        dest="book_name",
        required=True,
        metavar="TEXT",
        help="book name as stored during ingestion",
    )
    parser.add_argument(
        "--query",
        required=True,
        metavar="TEXT",
        help="text to embed and search for",
    )
    parser.add_argument(
        "--limit",
        "-k",
        type=_positive,
        default=DEFAULT_LIMIT,
        metavar="N",
        help=f"number of results to return (default: {DEFAULT_LIMIT})",
    )
    parser.add_argument(
        "--from-page",
        type=_positive,
        metavar="N",
        help="inclusive lower page bound",
    )
    parser.add_argument(
        "--to-page",
        type=_positive,
        metavar="N",
        help="inclusive upper page bound",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print results as JSON",
    )
    return parser


def _print_hits(hits: Sequence[RetrievalHit]) -> None:
    for hit in hits:
        page = "unknown page" if hit.page is None else f"page {hit.page}"
        print(f"[{hit.rank}] {hit.book_name} - {page} - distance {hit.distance:.4f}")
        for line in hit.content.splitlines():
            print(f"    {line}")
        print()


def _positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


if __name__ == "__main__":
    raise SystemExit(main())
