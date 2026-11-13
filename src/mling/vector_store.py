from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_postgres import PGEngine, PGVectorStore
from langchain_postgres.v2.indexes import DistanceStrategy

from mling.config import Settings
from mling.embeddings import build_embeddings

DEFAULT_METADATA_COLUMNS = ("book_name", "page")


class EmbeddingStore:
    def __init__(
        self,
        embeddings: Embeddings,
        engine: PGEngine,
        table_name: str,
        metadata_columns: Sequence[str] = DEFAULT_METADATA_COLUMNS,
        distance_strategy: DistanceStrategy = DistanceStrategy.COSINE_DISTANCE,
    ) -> None:
        self._embeddings = embeddings
        self._engine = engine
        self._table_name = table_name
        self._metadata_columns = tuple(metadata_columns)
        self._store = PGVectorStore.create_sync(
            engine=engine,
            embedding_service=embeddings,
            table_name=table_name,
            metadata_columns=list(self._metadata_columns),
            distance_strategy=distance_strategy,
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> EmbeddingStore:
        return cls(
            embeddings=build_embeddings(settings),
            engine=PGEngine.from_connection_string(url=settings.postgres_dsn),
            table_name=settings.table_name,
        )

    @property
    def embeddings(self) -> Embeddings:
        return self._embeddings

    @property
    def engine(self) -> PGEngine:
        return self._engine

    @property
    def vector_store(self) -> PGVectorStore:
        return self._store

    @property
    def table_name(self) -> str:
        return self._table_name

    @property
    def metadata_columns(self) -> tuple[str, ...]:
        return self._metadata_columns

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._embeddings.embed_documents(list(texts))

    def embed_query(self, text: str) -> list[float]:
        return self._embeddings.embed_query(text)

    def add_texts(
        self,
        texts: Sequence[str],
        metadatas: Sequence[dict[str, Any]] | None = None,
        ids: Sequence[str] | None = None,
    ) -> list[str]:
        return self._store.add_texts(
            texts=list(texts),
            metadatas=list(metadatas) if metadatas is not None else None,
            ids=list(ids) if ids is not None else None,
        )

    def add_documents(
        self,
        documents: Sequence[Document],
        ids: Sequence[str] | None = None,
    ) -> list[str]:
        kwargs: dict[str, Any] = {}
        if ids is not None:
            kwargs["ids"] = list(ids)
        return self._store.add_documents(documents=list(documents), **kwargs)

    def search(
        self,
        query: str,
        k: int = 4,
        filter: dict[str, Any] | None = None,
    ) -> list[Document]:
        return self._store.similarity_search(query, k=k, filter=filter)

    def search_with_score(
        self,
        query: str,
        k: int = 4,
        filter: dict[str, Any] | None = None,
    ) -> list[tuple[Document, float]]:
        return self._store.similarity_search_with_score(query, k=k, filter=filter)

    def as_retriever(self, **kwargs: Any) -> VectorStoreRetriever:
        return self._store.as_retriever(**kwargs)

    def get_by_ids(self, ids: Sequence[str]) -> list[Document]:
        return self._store.get_by_ids(list(ids))

    def delete(self, ids: Sequence[str]) -> None:
        self._store.delete(ids=list(ids))

    def drop_table(self) -> None:
        self._engine.drop_table(self._table_name)

    def close(self) -> None:
        asyncio.run(self._engine.close())
