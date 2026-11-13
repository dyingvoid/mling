from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_postgres import PGVector
from langchain_postgres.vectorstores import DistanceStrategy

from mling.config import Settings
from mling.embeddings import build_embeddings


class EmbeddingStore:
    def __init__(
        self,
        embeddings: Embeddings,
        connection: str,
        collection_name: str,
        embedding_length: int,
    ) -> None:
        self._embeddings = embeddings
        self._store = PGVector(
            embeddings=embeddings,
            connection=connection,
            collection_name=collection_name,
            embedding_length=embedding_length,
            distance_strategy=DistanceStrategy.COSINE,
            use_jsonb=True,
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> EmbeddingStore:
        return cls(
            embeddings=build_embeddings(settings),
            connection=settings.postgres_dsn,
            collection_name=settings.collection_name,
            embedding_length=settings.embedding_dimension,
        )

    @property
    def embeddings(self) -> Embeddings:
        return self._embeddings

    @property
    def vector_store(self) -> PGVector:
        return self._store

    @property
    def collection_name(self) -> str:
        return self._store.collection_name

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

    def delete(self, ids: Sequence[str]) -> None:
        self._store.delete(ids=list(ids))

    def delete_collection(self) -> None:
        self._store.delete_collection()
