# core/embedding パッケージ

from clawtion.core.embedding.client import (
    EmbeddingClient,
    EmbeddingError,
    EmbeddingRateLimitError,
    EmbeddingBatchError,
    EmbeddingResult,
    ExtractedContent,
    FileProcessor,
)
from clawtion.core.embedding.gemini import GeminiEmbeddingClient
from clawtion.core.embedding.openai import OpenAIEmbeddingClient
from clawtion.core.embedding.ollama import OllamaEmbeddingClient
from clawtion.core.embedding.batch import BatchEmbeddingClient, BatchConfig
from clawtion.core.embedding.factory import create_embedding_client

__all__ = [
    "EmbeddingClient",
    "EmbeddingError",
    "EmbeddingRateLimitError",
    "EmbeddingBatchError",
    "EmbeddingResult",
    "ExtractedContent",
    "FileProcessor",
    "GeminiEmbeddingClient",
    "OpenAIEmbeddingClient",
    "OllamaEmbeddingClient",
    "BatchEmbeddingClient",
    "BatchConfig",
    "create_embedding_client",
]
