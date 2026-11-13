# mling

Reusable embeddings and pgvector storage built on LangChain, backed by the local
TEI model from `docker-compose.yml` (`BAAI/bge-small-en-v1.5`, 384 dimensions).

The storage layer uses `PGVectorStore` from `langchain-postgres` v2. It is the
replacement for the deprecated `PGVector` class.

## Layout

`src/mling` is grouped by responsibility:

- `domain/` — the `Book` and `Page` models.
- `bookparse/` — PDF extraction into the domain models.
- `indexing/` — chunking, the embedding client, storage schema constants, and
  the pgvector store.
- `ingest/` — the parse → chunk → embed → commit pipeline and its CLI.
- `retrieval/` — filtered similarity search over stored chunks and its CLI.
- `config.py` — environment-backed settings shared by the layers.

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

Ingestion adds two tables and a `book_checksum` column:

```sql
CREATE TABLE mling_books (
    checksum TEXT PRIMARY KEY,          -- sha256 of the source file
    name TEXT NOT NULL,
    source TEXT NOT NULL,
    size_bytes BIGINT NOT NULL,
    page_count INTEGER NOT NULL,
    chunk_count INTEGER NOT NULL,
    embedding_model TEXT NOT NULL,
    chunk_size INTEGER NOT NULL,
    chunk_overlap INTEGER NOT NULL,
    metadata JSONB NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE mling_book_leases (
    checksum TEXT PRIMARY KEY,
    token UUID NOT NULL,
    owner TEXT NOT NULL,
    source TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL
);

ALTER TABLE mling_documents
    ADD COLUMN book_checksum TEXT
        REFERENCES mling_books (checksum) ON DELETE CASCADE;
```

`mling_books` only contains fully committed books. `mling_book_leases` holds
in-flight work; a lease expires after `INGEST_LEASE_TIMEOUT_SECONDS` and can be
taken over by a retry. Chunk IDs are `sha256(checksum:page:chunk)`, so ingesting
the same bytes twice is a no-op unless `force` is set.

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

## Book ingestion

`mling.ingest` connects the parser, chunker, embeddings, and vector store. Files
are identified by `sha256` of their bytes, so the same PDF under a different
name is treated as the same book.

Ingest from the command line:

```bash
uv run mling-ingest books/the-great-gatsby.pdf
uv run mling-ingest books/ --force
uv run mling-ingest books/the-great-gatsby.pdf --dry-run

make ingest book=books/the-great-gatsby.pdf
make ingest book=books/the-great-gatsby.pdf args=--dry-run
```

Directories are walked recursively for supported files, and the process exits
non-zero if any input fails. Successful runs print `ingested ...`, `skipped ...`,
or `parsed ...` (for dry runs); per-step progress goes to stderr.

### Command-line flags

`uv run mling-ingest --help` lists everything. The main knobs:

| Flag | What it does |
| --- | --- |
| `path ...` | One or more files or directories to ingest. |
| `--dry-run` | Parse and chunk only: no embeddings, no database writes, no lease. Use it to check extraction and chunk counts. |
| `--force` | Re-ingest a checksum that is already registered. Without it, a known book is reported as `skipped`. |
| `--chunk-size N` | Characters per chunk. Default `1000`. |
| `--chunk-overlap N` | Characters shared between adjacent chunks. Default `200`; must be smaller than `--chunk-size`. |
| `--embed-batch-size N` | Number of chunks embedded between lease renewals. Defaults to `INGEST_EMBED_BATCH_SIZE` (`64`). |
| `--dehyphenate` | Join words broken across line breaks, turning `inter-` / `national` into `international`. Off by default. |
| `--drop-blank-pages` | Drop pages with no extracted text before they reach the domain model. Ingestion already skips blank pages while chunking, so this mainly affects the stored `page_count`. |
| `--name TEXT` | Override the book name instead of using the PDF title or filename. Only valid with a single file. |
| `--quiet` | Hide the per-step `parse` / `documents` / `embed` / `commit` progress; still print the final summary. |

Common combinations:

```bash
# Check parsing and chunking without Postgres or the TEI model running
uv run mling-ingest books/the-great-gatsby.pdf --dry-run

# Smaller chunks and a re-ingest of a book that is already stored
uv run mling-ingest books/the-great-gatsby.pdf \
  --chunk-size 500 --chunk-overlap 100 --force

# Batch a directory and only show the final summaries
uv run mling-ingest books/ --quiet

# Through make: book= is the first path, args= is everything else
make ingest book=books/the-great-gatsby.pdf args=--dry-run
make ingest book=books/ args="--force --quiet"
```

When passing more than one flag through `make`, quote `args` so the shell sees
them as a single value.

```python
from mling.ingest import IngestOptions, ingest_book

summary = ingest_book(
    "books/the-great-gatsby.pdf",
    options=IngestOptions(chunk_size=1000, chunk_overlap=200),
)
print(summary.name, summary.page_count, summary.chunk_count, summary.skipped)
```

Each page is chunked independently, so `page` metadata is exact. Blank pages are
skipped. Ingestion is atomic per book: chunks are embedded first, then the book
row, chunk rows, and lease cleanup are committed in a single transaction. A
failed run leaves no partial book, and a re-run replaces the old chunks for that
checksum.

`BookPipeline` is reusable and takes steps plus lifecycle hooks:

```python
from mling.ingest import (
    BookPipeline,
    PipelineHooks,
    commit_step,
    documents_step,
    embed_step,
    parse_step,
)

pipeline = BookPipeline(
    leases,
    hooks=PipelineHooks(
        on_start=lambda ctx: print("starting", ctx.source.path),
        after_step=lambda ctx, step: print("done", step.name),
        on_error=lambda ctx, error: print("failed", error),
    ),
)
context = pipeline.run(
    source,
    options,
    [
        parse_step(),
        documents_step(),
        embed_step(embed),
        commit_step(writer, embedding_model="BAAI/bge-small-en-v1.5"),
    ],
    name="Optional override",
)
```

The pipeline acquires the checksum lease, renews it before every step, and
releases it on success or failure. Long steps can call `context.renew()`
themselves; the embedding step does this between batches. Leases are fenced by
a token, so a worker that loses its lease cannot commit stale chunks.

Use `IngestOptions(force=True)` to re-ingest an already registered checksum, for
example after changing the embedding model or chunk size.

## Retrieval

`mling.retrieval` embeds a query and returns the closest chunks for one book.
Results can optionally be restricted to an inclusive page range. The query is
prefixed with `EMBEDDING_QUERY_INSTRUCTION`, exactly like `embed_query`; stored
chunks are not prefixed.

```bash
uv run mling-retrieve \
  --book "The Great Gatsby" \
  --query "What did Gatsby believe?" \
  --limit 5 \
  --from-page 100 \
  --to-page 150
```

| Flag | What it does |
| --- | --- |
| `--book TEXT` | Required. Exact `book_name` stored during ingestion. |
| `--query TEXT` | Required. Text to embed and search for. |
| `--limit N`, `-k N` | Number of rows to return. Default `5`. |
| `--from-page N` | Optional inclusive lower page bound. |
| `--to-page N` | Optional inclusive upper page bound. |
| `--json` | Print rows as JSON instead of formatted blocks. |

Both page bounds are optional; omit either or both to search the whole book. The
default output is a block per result:

```text
[1] The Great Gatsby - page 42 - distance 0.1823
    He stretched out his arms toward the dark water...
```

`distance` is the cosine distance used by the vector index, so a smaller value
means a closer match. `--json` emits the same rows as objects with `rank`,
`book_name`, `page`, `distance`, and `content`.

Through `make`, use `book`, `query`, and optionally `n`, `from_page`, and
`to_page`. Extra CLI flags go through `args`:

```bash
make retrieve book="The Great Gatsby" query="What did Gatsby believe?"

make retrieve \
  book="The Great Gatsby" \
  from_page=100 \
  to_page=150 \
  n=10 \
  query="What did Gatsby believe?"

make retrieve book="The Great Gatsby" query="Gatsby's dream" args=--json
```

Quote values that contain spaces. The `book` value must match the name stored in
`book_name`; ingestion uses the PDF title unless it was run with `--name`.

The same behavior is available as a library:

```python
from mling.retrieval import RetrievalOptions, retrieve

hits = retrieve(
    RetrievalOptions(
        book_name="The Great Gatsby",
        query="What did Gatsby believe?",
        limit=5,
        from_page=100,
        to_page=150,
    )
)
for hit in hits:
    print(hit.rank, hit.page, hit.distance, hit.content)
```

`build_filter(options)` is exported if you need the LangChain metadata filter
without running a search. No schema change is required: retrieval uses the
existing `(book_name, page)` index.

## Configuration

All settings come from the environment, with defaults in `src/mling/config.py`.
See `.env.example`. `PGVECTOR_TABLE` selects the table, and
`EMBEDDING_DIMENSION` must match both the model (384 for `bge-small-en-v1.5`)
and the `vector(...)` type in the migration.

Ingestion uses `INGEST_LEASE_TIMEOUT_SECONDS` (default 300) as the lease
silence budget and `INGEST_EMBED_BATCH_SIZE` (default 64) as the number of
chunks embedded between lease renewals.
