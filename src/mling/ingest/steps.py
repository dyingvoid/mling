from __future__ import annotations

from collections.abc import Callable, Sequence

from mling.bookparse import parse_book
from mling.ingest.documents import book_to_documents
from mling.ingest.errors import EmptyBookError, IngestionError
from mling.ingest.models import BookRecord, IngestionSummary
from mling.ingest.pipeline import PipelineContext, PipelineStep
from mling.ingest.writer import BookWriter

EmbedFunction = Callable[[Sequence[str]], list[list[float]]]


def parse_step() -> PipelineStep:
    def run(context: PipelineContext) -> None:
        book = parse_book(context.source.path, options=context.options.parse_options())
        context.book = book
        title = book.title.strip()
        context.name = context.name or title or context.source.stem

    return PipelineStep("parse", run)


def documents_step() -> PipelineStep:
    def run(context: PipelineContext) -> None:
        if context.book is None:
            raise IngestionError("cannot build documents before parsing the book")
        name = context.name or context.source.stem
        documents = book_to_documents(
            context.book,
            checksum=context.source.checksum,
            name=name,
            options=context.options,
        )
        if not documents:
            raise EmptyBookError(context.source.path)
        context.documents = documents

    return PipelineStep("documents", run)


def embed_step(embed: EmbedFunction) -> PipelineStep:
    def run(context: PipelineContext) -> None:
        texts = [document.page_content for document in context.documents]
        batch_size = context.options.embed_batch_size
        vectors: list[list[float]] = []

        for start in range(0, len(texts), batch_size):
            context.renew()
            vectors.extend(embed(texts[start : start + batch_size]))

        if len(vectors) != len(texts):
            raise IngestionError(
                f"expected {len(texts)} embeddings, received {len(vectors)}"
            )
        context.vectors = vectors

    return PipelineStep("embed", run)


def commit_step(writer: BookWriter, *, embedding_model: str) -> PipelineStep:
    def run(context: PipelineContext) -> None:
        if context.book is None:
            raise IngestionError("cannot commit before parsing the book")
        name = context.name or context.source.stem
        record = BookRecord(
            checksum=context.source.checksum,
            name=name,
            source=context.book.source,
            size_bytes=context.source.size_bytes,
            page_count=len(context.book),
            chunk_count=len(context.documents),
            embedding_model=embedding_model,
            chunk_size=context.options.chunk_size,
            chunk_overlap=context.options.chunk_overlap,
            metadata=dict(context.book.metadata),
        )
        writer.commit(
            context.lease,
            record,
            context.documents,
            context.vectors,
        )
        context.summary = IngestionSummary(
            checksum=record.checksum,
            name=record.name,
            source=record.source,
            page_count=record.page_count,
            chunk_count=record.chunk_count,
        )

    return PipelineStep("commit", run)


def default_steps(
    *,
    embed: EmbedFunction,
    writer: BookWriter,
    embedding_model: str,
) -> tuple[PipelineStep, ...]:
    return (
        parse_step(),
        documents_step(),
        embed_step(embed),
        commit_step(writer, embedding_model=embedding_model),
    )
