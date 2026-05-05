"""Shared fixtures for all clawtion tests."""

import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory that is cleaned up after the test."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def sample_markdown_content():
    """Return a simple markdown document."""
    return """# Test Document

## Introduction

This is a test document for clawtion.

## Features

- Vector search with pgvector
- Hybrid search with RRF
- Markdown chunking

### Details

The document has multiple sections and paragraphs.

## Conclusion

This is the end of the test document."""


@pytest.fixture
def sample_markdown_with_code():
    """Return markdown with a code block."""
    return """# Code Example

Here is some Python code:

```python
def hello():
    print("Hello, World!")
    return True
```

And here is more text after the code block."""


@pytest.fixture
def sample_markdown_with_table():
    """Return markdown with a table."""
    return """# Table Example

| Name | Value | Description |
|------|-------|-------------|
| k    | 60    | RRF constant |
| m    | 16    | HNSW parameter |
| ef   | 128   | HNSW construction ef |"""


@pytest.fixture(autouse=True)
def setup_env():
    """Set up test environment variables."""
    os.environ.setdefault("CLAWTION_VAULT", str(Path.home() / ".clawtion" / "test-vault"))
    os.environ.setdefault("CLAWTION_DB_URL", "postgresql+asyncpg://clawtion:clawtion@localhost:5432/clawtion")
    os.environ.setdefault("CLAWTION_LOG_LEVEL", "DEBUG")
    yield
