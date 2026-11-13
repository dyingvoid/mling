from __future__ import annotations

from langchain_openai import OpenAIEmbeddings

from mling.config import Settings


class LocalEmbeddings(OpenAIEmbeddings):
    query_instruction: str = ""

    def embed_query(self, text: str) -> list[float]:
        return super().embed_query(self.query_instruction + text)

    async def aembed_query(self, text: str) -> list[float]:
        return await super().aembed_query(self.query_instruction + text)


def build_embeddings(settings: Settings) -> LocalEmbeddings:
    return LocalEmbeddings(
        model=settings.embedding_model,
        base_url=settings.embedding_base_url,
        api_key=settings.embedding_api_key,
        check_embedding_ctx_length=False,
        chunk_size=settings.embedding_batch_size,
        timeout=settings.embedding_timeout,
        query_instruction=settings.embedding_query_instruction,
    )
