from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine

from mling.config import Settings
from mling.ingest.errors import IngestionError
from mling.ingest.lease import BookLeaseStore
from mling.ingest.models import IngestionSummary
from mling.ingest.options import IngestOptions
from mling.ingest.pipeline import BookPipeline, PipelineHooks
from mling.ingest.source import SourceFile
from mling.ingest.steps import default_steps
from mling.ingest.writer import BookWriter
from mling.vector_store import EmbeddingStore


def ingest_book(
    path: str | Path,
    *,
    options: IngestOptions | None = None,
    settings: Settings | None = None,
    store: EmbeddingStore | None = None,
    leases: BookLeaseStore | None = None,
    writer: BookWriter | None = None,
    hooks: PipelineHooks | None = None,
    name: str | None = None,
) -> IngestionSummary:
    settings = settings or Settings.from_env()
    options = options or IngestOptions(
        embed_batch_size=settings.ingest_embed_batch_size
    )
    source = SourceFile.from_path(path)

    engine = _build_engine(settings, leases=leases, writer=writer)
    if leases is None:
        if engine is None:
            raise IngestionError("lease store requires a database engine")
        leases = BookLeaseStore(
            engine,
            ttl_seconds=settings.ingest_lease_timeout_seconds,
        )
    if writer is None:
        if engine is None:
            raise IngestionError("book writer requires a database engine")
        writer = BookWriter(
            engine,
            documents_table=settings.table_name,
            dimension=settings.embedding_dimension,
        )

    existing = writer.get(source.checksum)
    if existing is not None and not options.force:
        return IngestionSummary(
            checksum=existing.checksum,
            name=existing.name,
            source=existing.source,
            page_count=existing.page_count,
            chunk_count=existing.chunk_count,
            skipped=True,
        )

    owns_store = store is None
    store = store or EmbeddingStore.from_settings(settings)

    try:
        pipeline = BookPipeline(leases, hooks=hooks)
        context = pipeline.run(
            source,
            options,
            default_steps(
                embed=store.embed_documents,
                writer=writer,
                embedding_model=settings.embedding_model,
            ),
            name=name,
        )
        if context.summary is None:
            raise IngestionError("pipeline finished without an ingestion summary")
        return context.summary
    finally:
        if owns_store:
            store.close()
        if engine is not None:
            engine.dispose()


def _build_engine(
    settings: Settings,
    *,
    leases: BookLeaseStore | None,
    writer: BookWriter | None,
) -> Engine | None:
    if leases is not None and writer is not None:
        return None
    return create_engine(settings.postgres_dsn)
