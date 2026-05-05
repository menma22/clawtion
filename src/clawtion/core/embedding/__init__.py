# core/embedding パッケージ

from clawtion.core.embedding.batch import BatchConfig, BatchEmbeddingClient
from clawtion.core.embedding.client import (
    EmbeddingBatchError,
    EmbeddingClient,
    EmbeddingError,
    EmbeddingRateLimitError,
    EmbeddingResult,
    ExtractedContent,
    FileProcessor,
)
from clawtion.core.embedding.factory import create_embedding_client
from clawtion.core.embedding.gemini import GeminiEmbeddingClient
from clawtion.core.embedding.ollama import OllamaEmbeddingClient
from clawtion.core.embedding.openai import OpenAIEmbeddingClient

__all__ = [
    "BatchConfig",
    "BatchEmbeddingClient",
    "EmbeddingBatchError",
    "EmbeddingClient",
    "EmbeddingError",
    "EmbeddingRateLimitError",
    "EmbeddingResult",
    "ExtractedContent",
    "FileProcessor",
    "GeminiEmbeddingClient",
    "OllamaEmbeddingClient",
    "OpenAIEmbeddingClient",
    "create_embedding_client",
]
