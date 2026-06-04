"""Embedding client factory for clawtion.

Provides a single ``create_embedding_client`` entry-point that reads the
merged application configuration and instantiates the appropriate
:class:`~clawtion.core.embedding.client.EmbeddingClient` implementation
(Gemini, OpenAI, or Ollama).
"""

from __future__ import annotations

import logging
from typing import Any

from clawtion.config.secrets import get_secret
from clawtion.core.embedding.client import EmbeddingClient, EmbeddingError

logger = logging.getLogger(__name__)

# -- Provider registry -------------------------------------------------------

_PROVIDER_REGISTRY: dict[str, str] = {
    "gemini": "clawtion.core.embedding.gemini",
    "openai": "clawtion.core.embedding.openai",
    "ollama": "clawtion.core.embedding.ollama",
}

# -- Factory -----------------------------------------------------------------


def create_embedding_client(config: dict[str, Any]) -> EmbeddingClient:
    """Create an embedding client from the merged application *config*.

    The config dict is expected to follow the structure defined in
    :mod:`clawtion.config.defaults`:

    .. code-block:: yaml

        embedding:
          provider: gemini          # gemini | openai | ollama
          # Gemini-specific options
          model: models/text-embedding-004
          output_dimensionality: 768
          use_manual_prefix_fallback: true
          # OpenAI-specific options
          openai:
            model: text-embedding-3-small
            dimensions: 1536
          # Ollama-specific options
          ollama:
            base_url: http://localhost:11434
            model: nomic-embed-text
            dimensions: 768

    API keys are resolved via :func:`clawtion.config.secrets.get_secret`
    (environment variables → OS keychain → encrypted file).

    Args:
        config: The merged application configuration dictionary.

    Returns:
        An initialised :class:`EmbeddingClient` implementation.

    Raises:
        EmbeddingError: If the provider is unknown or required configuration
            is missing.
    """
    emb_cfg: dict[str, Any] = config.get("embedding", {})

    provider: str = emb_cfg.get("provider", "gemini").lower()

    if provider == "gemini":
        return _create_gemini(emb_cfg)
    elif provider == "openai":
        return _create_openai(emb_cfg)
    elif provider == "ollama":
        return _create_ollama(emb_cfg)
    else:
        raise EmbeddingError(
            f"Unknown embedding provider: {provider!r}. Supported: {', '.join(sorted(_PROVIDER_REGISTRY))}",
        )


# -- Provider-specific constructors ------------------------------------------


def _create_gemini(emb_cfg: dict[str, Any]) -> EmbeddingClient:
    """Build a :class:`~clawtion.core.embedding.gemini.GeminiEmbeddingClient`."""
    from clawtion.core.embedding.gemini import GeminiEmbeddingClient

    api_key = get_secret("gemini_api_key")
    if not api_key:
        raise EmbeddingError(
            "Gemini API key is not configured. Run: clawtion config set-key gemini",
        )

    return GeminiEmbeddingClient(
        api_key=api_key,
        output_dimensionality=emb_cfg.get("output_dimensionality", 768),
        use_manual_prefix=emb_cfg.get("use_manual_prefix_fallback", True),
        model_name=emb_cfg.get(
            "model",
            "models/gemini-embedding-2",
        ),
    )


def _create_openai(emb_cfg: dict[str, Any]) -> EmbeddingClient:
    """Build an :class:`~clawtion.core.embedding.openai.OpenAIEmbeddingClient`."""
    from clawtion.core.embedding.openai import OpenAIEmbeddingClient

    api_key = get_secret("openai_api_key")
    if not api_key:
        raise EmbeddingError(
            "OpenAI API key is not configured. Run: clawtion config set-key openai",
        )

    openai_cfg: dict[str, Any] = emb_cfg.get("openai", {})

    return OpenAIEmbeddingClient(
        api_key=api_key,
        model=openai_cfg.get("model", "text-embedding-3-small"),
        dimensions=openai_cfg.get("dimensions"),
    )


def _create_ollama(emb_cfg: dict[str, Any]) -> EmbeddingClient:
    """Build an :class:`~clawtion.core.embedding.ollama.OllamaEmbeddingClient`."""
    from clawtion.core.embedding.ollama import OllamaEmbeddingClient

    ollama_cfg: dict[str, Any] = emb_cfg.get("ollama", {})

    return OllamaEmbeddingClient(
        base_url=ollama_cfg.get("base_url", "http://localhost:11434"),
        model=ollama_cfg.get("model", "nomic-embed-text"),
        dimensions=ollama_cfg.get("dimensions", 768),
    )
