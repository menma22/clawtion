"""Default configuration for clawtion.

This module defines the complete default configuration dictionary,
matching the config.yaml specification in the design document (section 15.2).
Values here are overridden by user config files and environment variables.
"""

from __future__ import annotations

from typing import Any

DEFAULT_CONFIG: dict[str, Any] = {
    # ===== Vault settings =====
    "vault": {
        "path": "~/Documents/clawtion-vault",
        "watch_folders": ["."],
        "exclude_folders": [".trash", "drafts", "private"],
    },
    # ===== UI language =====
    "ui": {
        "language": "auto",  # auto | en | ja
    },
    # ===== Embedding settings =====
    "embedding": {
        "provider": "gemini",  # gemini | openai | ollama
        "model": "gemini-embedding-2-preview",
        "output_dimensionality": 768,  # 768 | 1536 | 3072
        "task_type": {
            "document": "RETRIEVAL_DOCUMENT",
            "query": "RETRIEVAL_QUERY",
        },
        "use_manual_prefix_fallback": True,
        "use_batch_api": True,
        "batch_threshold": 100,
        "batch_max_wait_hours": 24,
        "retry": {
            "max_attempts": 5,
            "initial_wait_seconds": 4,
            "max_wait_seconds": 60,
        },
        # ===== OpenAI provider settings =====
        "openai": {
            "model": "text-embedding-3-small",
            "dimensions": 1536,
        },
        # ===== Ollama provider settings =====
        "ollama": {
            "base_url": "http://localhost:11434",
            "model": "nomic-embed-text",
            "dimensions": 768,
        },
    },
    # ===== Chunking settings =====
    "chunking": {
        "multi_resolution": {
            "enabled": True,  # Phase 2: multi-resolution chunking
        },
        "levels": {
            "file": {
                "enabled": True,
                "max_tokens": 1500,
            },
            "coarse": {
                "enabled": True,  # Phase 2: enabled by default
                "strategy": "heading-based",
                "target_tokens": 800,
                "max_tokens": 1500,
                "merge_short_sections": True,
            },
            "fine": {
                "enabled": True,  # Phase 2: enabled by default
                "strategy": "sentence-based",
                "target_tokens": 100,
                "respect_paragraph_boundary": True,
            },
        },
        "preserve": {
            "code_blocks": True,
            "tables": True,
            "list_items": True,
        },
        "language_detection": "auto",
        "fallback_language": "ja",
        "context_format": (
            "folder: {folder_path} | file: {title} | "
            "section: {heading_path} | text: {content}"
        ),
    },
    # ===== Indexing settings =====
    "indexing": {
        "triggers": {
            "on_pc_startup": {
                "enabled": True,
            },
            "hourly_check": {
                "enabled": True,
                "interval_minutes": 60,
            },
            "on_app_open": {
                "enabled": True,
            },
        },
        "worker": {
            "max_concurrent_jobs": 4,
            "queue_polling_interval_seconds": 5,
        },
        "snapshot": {
            "enabled": True,
        },
    },
    # ===== Trash settings =====
    "trash": {
        "enabled": True,
        "auto_purge_after_days": 7,
    },
    # ===== Logging settings =====
    "logging": {
        "level": "INFO",
        "file_path": "~/.clawtion/logs/",
        "rotation": "daily",
        "retention_days": 30,
        "format": "json",
        "claude_context_verbosity": "high",
    },
    # ===== Service settings =====
    "service": {
        "mode": "manual",  # manual | scheduled | background
    },
    # ===== Backup settings =====
    "backup": {
        "enabled": False,
        "schedule": "daily",
        "retention_days": 7,
        "path": "~/.clawtion/backups/",
    },
    # ===== Phase 2+ optional features =====
    "graphrag": {
        "enabled": False,
        "llm_model": "claude-haiku-4-5",
        "extract_on_index": True,
    },
    "contextual_retrieval": {
        "enabled": False,
        "llm_model": "claude-haiku-4-5",
        "use_prompt_caching": True,
    },
}
