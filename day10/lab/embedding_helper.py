"""
Helper tạo embedding function & Chroma client — dùng chung cho etl_pipeline, eval_retrieval, grading_run.

Ưu tiên ShopAIKey API nếu có SHOPAIKEY_API_KEY trong .env; nếu không → fallback SentenceTransformer local.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent


def get_chroma_client():
    """Trả về PersistentClient trỏ đến CHROMA_DB_PATH."""
    import chromadb

    db_path = os.environ.get("CHROMA_DB_PATH", str(ROOT / "chroma_db"))
    return chromadb.PersistentClient(path=db_path)


class ShopAIKeyEmbeddingFunction:
    """Custom embedding function gọi ShopAIKey API (OpenAI-compatible).

    Tương thích ChromaDB >= 1.5 (implement đủ protocol EmbeddingFunction).
    """

    def __init__(self, api_key: str | None = None, model_name: str = "text-embedding-3-small"):
        from openai import OpenAI

        self._api_key = api_key or os.environ.get("SHOPAIKEY_API_KEY", "")
        self._client = OpenAI(
            api_key=self._api_key,
            base_url="https://api.shopaikey.com/v1",
            default_headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                )
            },
        )
        self._model = model_name

    def __call__(self, input: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(input=input, model=self._model)
        return [item.embedding for item in response.data]

    def embed_query(self, input: list[str]) -> list[list[float]]:
        """Embed query — dùng cùng logic với __call__."""
        return self.__call__(input)

    @staticmethod
    def name() -> str:
        return "shopaikey_openai_compatible"

    def get_config(self) -> dict:
        return {"model_name": self._model}

    @staticmethod
    def build_from_config(config: dict) -> "ShopAIKeyEmbeddingFunction":
        return ShopAIKeyEmbeddingFunction(model_name=config.get("model_name", "text-embedding-3-small"))


def get_embedding_function():
    """
    Trả về embedding function dùng cho Chroma collection.

    - Nếu SHOPAIKEY_API_KEY tồn tại → dùng ShopAIKey API (OpenAI-compatible).
    - Ngược lại → fallback SentenceTransformerEmbeddingFunction (model local).
    """
    api_key = os.environ.get("SHOPAIKEY_API_KEY", "").strip()
    if api_key:
        model_name = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        return ShopAIKeyEmbeddingFunction(api_key=api_key, model_name=model_name)

    # Fallback: local SentenceTransformer
    from chromadb.utils import embedding_functions

    model_name = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    return embedding_functions.SentenceTransformerEmbeddingFunction(model_name=model_name)


def get_collection_name() -> str:
    """Trả về tên collection (mặc định day10_kb)."""
    return os.environ.get("CHROMA_COLLECTION", "day10_kb")
