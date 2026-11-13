from mling.chunking import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    build_text_splitter,
    split_documents,
    split_text,
)
from mling.config import Settings
from mling.embeddings import LocalEmbeddings, build_embeddings
from mling.vector_store import EmbeddingStore

__all__ = [
    "DEFAULT_CHUNK_OVERLAP",
    "DEFAULT_CHUNK_SIZE",
    "EmbeddingStore",
    "LocalEmbeddings",
    "Settings",
    "build_embeddings",
    "build_text_splitter",
    "split_documents",
    "split_text",
]


def main() -> None:
    print("mling: import mling.EmbeddingStore to embed and search documents")
