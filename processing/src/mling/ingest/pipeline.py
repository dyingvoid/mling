from __future__ import annotations

from collections.abc import Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from typing import TypeAlias

from langchain_core.documents import Document

from mling.domain import Book
from mling.ingest.lease import Lease, LeaseStore
from mling.ingest.models import IngestionSummary
from mling.ingest.options import IngestOptions
from mling.ingest.source import SourceFile

StepFunction: TypeAlias = Callable[["PipelineContext"], None]


@dataclass(frozen=True, slots=True)
class PipelineStep:
    name: str
    run: StepFunction


Step: TypeAlias = PipelineStep | StepFunction


@dataclass(slots=True)
class PipelineContext:
    source: SourceFile
    options: IngestOptions
    lease: Lease
    leases: LeaseStore = field(repr=False)
    name: str | None = None
    book: Book | None = None
    documents: list[Document] = field(default_factory=list)
    vectors: list[list[float]] = field(default_factory=list)
    summary: IngestionSummary | None = None

    def renew(self) -> None:
        self.lease = self.leases.renew(self.lease)


def _noop(ctx: PipelineContext) -> None:
    pass


def _noop_step(ctx: PipelineContext, step: PipelineStep) -> None:
    pass


def _noop_error(ctx: PipelineContext, error: BaseException) -> None:
    pass


@dataclass(frozen=True, slots=True)
class PipelineHooks:
    on_start: Callable[[PipelineContext], None] = _noop
    before_step: Callable[[PipelineContext, PipelineStep], None] = _noop_step
    after_step: Callable[[PipelineContext, PipelineStep], None] = _noop_step
    on_success: Callable[[PipelineContext], None] = _noop
    on_error: Callable[[PipelineContext, BaseException], None] = _noop_error
    on_end: Callable[[PipelineContext], None] = _noop


class BookPipeline:
    def __init__(
        self,
        leases: LeaseStore,
        *,
        hooks: PipelineHooks | None = None,
    ) -> None:
        self._leases = leases
        self._hooks = hooks or PipelineHooks()

    def run(
        self,
        source: SourceFile,
        options: IngestOptions,
        steps: Sequence[Step],
        *,
        name: str | None = None,
    ) -> PipelineContext:
        lease = self._leases.acquire(
            source.checksum,
            source.path.as_posix(),
        )
        context = PipelineContext(
            source=source,
            options=options,
            lease=lease,
            leases=self._leases,
            name=name,
        )

        try:
            self._hooks.on_start(context)
            for step in map(_as_step, steps):
                self._hooks.before_step(context, step)
                context.renew()
                step.run(context)
                self._hooks.after_step(context, step)
            self._hooks.on_success(context)
            return context
        except BaseException as error:
            self._hooks.on_error(context, error)
            raise
        finally:
            with suppress(Exception):
                self._leases.release(lease)
            self._hooks.on_end(context)


def _as_step(step: Step) -> PipelineStep:
    if isinstance(step, PipelineStep):
        return step
    return PipelineStep(getattr(step, "__name__", type(step).__name__), step)
