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
    langchain_metadata JSONB,
    book_name TEXT,
    page INTEGER
);

CREATE INDEX ix_mling_documents_embedding_cosine
    ON mling_documents
    USING hnsw (embedding vector_cosine_ops);

CREATE INDEX ix_mling_documents_book_name_page
    ON mling_documents (book_name, page);
```

The column names are the defaults expected by `PGVectorStore`. The table itself
is owned by the migrations; the library only reads and writes rows. If the
embedding model changes, update `EMBEDDING_DIMENSION` **and** the `vector(...)`
dimension in `migrations/000002_create_documents_table.up.sql`.

`book_name` and `page` are promoted to real columns through `metadata_columns`
and stored as nullable values (`page` is optional). Remaining document metadata
stays in the `langchain_metadata` JSONB column, so arbitrary keys remain
queryable through `filter`.

The `(book_name, page)` index serves both book-only queries and book plus page
range queries:

```python
store.search("What did Gatsby believe?", k=3, filter={"book_name": "The Great Gatsby"})

store.search(
    "What did Gatsby believe?",
    k=3,
    filter={
        "$and": [
            {"book_name": "The Great Gatsby"},
            {"page": {"$gte": 200}},
            {"page": {"$lte": 400}},
        ]
    },
)
```

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

## Book parsing

PDFs are parsed into the domain model in `src/mling/domain` (`Book`, `Page`).
The parser lives in `src/mling/bookparse` and depends on the domain layer, not
the other way around.

```python
from mling.bookparse import parse_book

book = parse_book("books/the-great-gatsby.pdf")
print(book.title, len(book), book.metadata)
print(book.page_text(1))
```

`parse_books("books/")` returns a `BatchResult` with parsed books, per-file
errors, and skipped unsupported files.

PDF text extraction uses `pypdf`; no OCR is performed, so scanned pages come
back empty. Whitespace is normalized, and `Options(dehyphenate=True)` joins
words split across line breaks. Pages are kept separate so the embedding layer
can attach a page number to every chunk.

There is also a test-only inspection CLI that is not part of the application
surface:

```bash
uv run mling-bookparse-test books/the-great-gatsby.pdf
# or, with the file passed through make:
make parse book=books/the-great-gatsby.pdf
```

It prints a summary and then prompts for page numbers until you quit with `q`.

## Configuration

All settings come from the environment, with defaults in `src/mling/config.py`.
See `.env.example`. `PGVECTOR_TABLE` selects the table, and
`EMBEDDING_DIMENSION` must match both the model (384 for `bge-small-en-v1.5`)
and the `vector(...)` type in the migration.
