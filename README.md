# mling

Reusable embeddings and pgvector storage built on LangChain, backed by the local
TEI model from `docker-compose.yml` (`BAAI/bge-small-en-v1.5`, 384 dimensions).

## Setup

```bash
make up
make migrate-up
uv sync
```

TEI exposes an OpenAI-compatible `/v1/embeddings` endpoint, so the component uses
`OpenAIEmbeddings` pointed at `http://localhost:${TEI_PORT}/v1`.

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
retriever = store.as_retriever(search_kwargs={"k": 3})
```

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
See `.env.example`. `EMBEDDING_DIMENSION` must match the model (384 for
`bge-small-en-v1.5`) **and** the dimension in
`migrations/000002_add_langchain_pgvector.up.sql`.
