"""Command line entrypoint for book ingestion."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from mling.bookparse import DEFAULT_REGISTRY, parse_book
from mling.bookparse.errors import BookParseError
from mling.config import Settings
from mling.ingest.book import ingest_book
from mling.ingest.documents import book_to_documents
from mling.ingest.errors import IngestionError
from mling.ingest.models import IngestionSummary
from mling.ingest.options import IngestOptions
from mling.ingest.pipeline import PipelineContext, PipelineHooks, PipelineStep
from mling.ingest.source import SourceFile


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    options = _build_options(args, settings)
    if options.chunk_overlap >= options.chunk_size:
        print("chunk overlap must be smaller than chunk size", file=sys.stderr)
        return 2

    paths, failures = _collect(args.paths)
    if args.name and len(paths) > 1:
        print("--name can only be used with a single book", file=sys.stderr)
        return 2
    if not paths and not failures:
        print("no supported books found", file=sys.stderr)
        return 1

    total = len(paths) + failures
    hooks = _build_hooks(quiet=args.quiet)
    for path in paths:
        try:
            if args.dry_run:
                summary = _dry_run(path, options, name=args.name)
            else:
                summary = ingest_book(
                    path,
                    options=options,
                    settings=settings,
                    hooks=hooks,
                    name=args.name,
                )
        except (IngestionError, BookParseError, OSError) as exc:
            print(f"failed {path}: {exc}", file=sys.stderr)
            failures += 1
            continue
        _print_summary(summary, dry_run=args.dry_run)

    if failures:
        print(f"{failures} of {total} book(s) failed", file=sys.stderr)
        return 1
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mling-ingest",
        description=(
            "Parse PDFs, chunk them, embed them, and store them in pgvector. "
            "Directories are walked recursively for supported files."
        ),
    )
    parser.add_argument(
        "paths",
        nargs="+",
        metavar="path",
        help="PDF file or directory to ingest",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="parse and chunk only; do not embed or write to the database",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="re-ingest books that are already registered",
    )
    parser.add_argument(
        "--chunk-size",
        type=_positive,
        metavar="N",
        help="characters per chunk",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=_non_negative,
        metavar="N",
        help="characters shared between adjacent chunks",
    )
    parser.add_argument(
        "--embed-batch-size",
        type=_positive,
        metavar="N",
        help="chunks embedded between lease renewals (default: INGEST_EMBED_BATCH_SIZE)",
    )
    parser.add_argument(
        "--dehyphenate",
        action="store_true",
        help="join words broken across line breaks while parsing",
    )
    parser.add_argument(
        "--drop-blank-pages",
        action="store_true",
        help="omit pages whose extracted text is empty",
    )
    parser.add_argument(
        "--name",
        help="override the book name (only valid for a single file)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="only print the final summary",
    )
    return parser


def _build_options(args: argparse.Namespace, settings: Settings) -> IngestOptions:
    options = IngestOptions(
        embed_batch_size=settings.ingest_embed_batch_size,
        dehyphenate=args.dehyphenate,
        keep_blank_pages=not args.drop_blank_pages,
        force=args.force,
    )
    changes: dict[str, int] = {}
    if args.chunk_size is not None:
        changes["chunk_size"] = args.chunk_size
    if args.chunk_overlap is not None:
        changes["chunk_overlap"] = args.chunk_overlap
    if args.embed_batch_size is not None:
        changes["embed_batch_size"] = args.embed_batch_size
    return replace(options, **changes) if changes else options


def _build_hooks(*, quiet: bool) -> PipelineHooks:
    if quiet:
        return PipelineHooks()

    def after_step(_context: PipelineContext, step: PipelineStep) -> None:
        print(f"  {step.name} done", file=sys.stderr)

    return PipelineHooks(after_step=after_step)


def _dry_run(
    path: Path,
    options: IngestOptions,
    *,
    name: str | None,
) -> IngestionSummary:
    source = SourceFile.from_path(path)
    book = parse_book(path, options=options.parse_options())
    book_name = name or book.title.strip() or source.stem
    documents = book_to_documents(
        book,
        checksum=source.checksum,
        name=book_name,
        options=options,
    )
    return IngestionSummary(
        checksum=source.checksum,
        name=book_name,
        source=book.source,
        page_count=len(book),
        chunk_count=len(documents),
    )


def _collect(raw_paths: Sequence[str]) -> tuple[list[Path], int]:
    paths: list[Path] = []
    failures = 0
    seen: set[Path] = set()

    for raw in raw_paths:
        path = Path(raw)
        if path.is_dir():
            candidates = (
                candidate
                for candidate in sorted(path.rglob("*"))
                if candidate.is_file()
                and not _is_hidden(candidate, path)
                and DEFAULT_REGISTRY.supports(candidate)
            )
        elif path.is_file():
            if not DEFAULT_REGISTRY.supports(path):
                print(f"unsupported book format: {path}", file=sys.stderr)
                failures += 1
                continue
            candidates = iter((path,))
        else:
            print(f"not found: {path}", file=sys.stderr)
            failures += 1
            continue

        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            paths.append(candidate)

    return paths, failures


def _is_hidden(path: Path, root: Path) -> bool:
    try:
        return any(part.startswith(".") for part in path.relative_to(root).parts)
    except ValueError:
        return False


def _print_summary(summary: IngestionSummary, *, dry_run: bool) -> None:
    if summary.skipped:
        print(f"skipped {summary.name} ({summary.source})")
        return
    verb = "parsed" if dry_run else "ingested"
    print(
        f"{verb} {summary.name}: {summary.page_count} pages, "
        f"{summary.chunk_count} chunks ({summary.source})"
    )


def _positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def _non_negative(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must not be negative")
    return number


if __name__ == "__main__":
    raise SystemExit(main())
