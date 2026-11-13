# mling

Reusable embeddings and pgvector storage built on LangChain, backed by the local
TEI model from `docker-compose.yml` (`BAAI/bge-small-en-v1.5`, 384 dimensions).

The storage layer uses `PGVectorStore` from `langchain-postgres` v2. It is the
replacement for the deprecated `PGVector` class.

## Setup

```bash
make up
make migrate-up
uv sync
```

TEI exposes an OpenAI-compatible `/v1/embeddings` endpoint, so the component uses
`OpenAIEmbeddings` pointed at `http://localhost:${TEI_PORT}/v1`.

## Schema

`PGVectorStore` works on a single table per store. The migrations create:

```sql
CREATE TABLE mling_documents (
    langchain_id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(384) NOT NULL,
    langchain_metadata JSONB
);

CREATE INDEX ix_mling_documents_embedding_cosine
    ON mling_documents
    USING hnsw (embedding vector_cosine_ops);
```

The column names are the defaults expected by `PGVectorStore`. The table itself
is owned by the migrations; the library only reads and writes rows. If the
embedding model changes, update `EMBEDDING_DIMENSION` **and** the `vector(...)`
dimension in `migrations/000002_create_documents_table.up.sql`.

Document metadata is stored in the `langchain_metadata` JSONB column, so
arbitrary metadata keys remain queryable through `filter`.

## Usage

```python
from langchain_core.documents import Document

from mling import EmbeddingStore, Settings, split_documents

settings = Settings.from_env()
store = EmbeddingStore.from_settings(settings)

documents = [Document(page_content="LangChain is a framework for LLM apps.")]
chunks = split_documents(documents, chunk_size=1000, chunk_overlap=200)

store.add_documents(chunks)

results = store.search("What is LangChain?", k=3)
results_with_scores = store.search_with_score(
    "What is LangChain?",
    k=3,
    filter={"source": {"$eq": "docs"}},
)
retriever = store.as_retriever(search_kwargs={"k": 3})

store.close()
```

`get_by_ids`, `delete`, and `drop_table` are also available. Deleting the table
is the equivalent of the old `delete_collection`.

Embeddings on their own:

```python
from mling import build_embeddings, Settings

embeddings = build_embeddings(Settings.from_env())
vectors = embeddings.embed_documents(["first document", "second document"])
query_vector = embeddings.embed_query("a question")
```

Queries are prefixed with `EMBEDDING_QUERY_INSTRUCTION`; documents are not.

## Configuration

All settings come from the environment, with defaults in `src/mling/config.py`.
See `.env.example`. `PGVECTOR_TABLE` selects the table, and
`EMBEDDING_DIMENSION` must match both the model (384 for `bge-small-en-v1.5`)
and the `vector(...)` type in the migration.
