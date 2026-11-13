"""Pytest configuration and fixtures for Care-Beacon tests."""

import os
from pathlib import Path

import dotenv
import pytest

# Tests must behave the same on a developer machine and in CI, which has no .env.
# Block python-dotenv before any src module imports it, and drop variables a
# developer's .env or shell would otherwise leak into config. Tests that need a
# value set it themselves (monkeypatch.setenv). TEST_DATABASE_URL is kept: it
# opts in to the Postgres tests.
dotenv.load_dotenv = lambda *args, **kwargs: False
_LEAKY_ENV = (
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
    "REDIS_URL", "REDIS_HOST", "REDIS_PORT", "REDIS_PASSWORD", "REDIS_DB",
    "QDRANT_URL", "QDRANT_API_KEY", "VECTOR_DB_PROVIDER", "CONFIG_PATH",
    "EMBEDDING_BATCH_SIZE", "INGESTION_CHUNK_BATCH_SIZE", "INGESTION_ARTICLE_BATCH_SIZE",
    "ADMIN_API_KEY", "DATABASE_URL", "DATABASE_URL_UNPOOLED",
    "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST",
)
for _name in _LEAKY_ENV:
    os.environ.pop(_name, None)

# Set test environment
os.environ["ENVIRONMENT"] = "test"


@pytest.fixture
def test_data_dir():
    """Get the test data directory path."""
    return Path(__file__).parent / "test_data"


@pytest.fixture
def sample_markdown_content():
    """Sample markdown content for testing."""
    return """---
title: "Test Cancer Article"
url: https://example.com/test-cancer
date_scraped: 2025-11-07T00:00:00
breadcrumbs:
  - Health Info
  - Types Of Cancer
  - Test Cancer
---

# Test Cancer

This is a test article about cancer.

## Diagnosis & Staging

### What are the signs and symptoms?

Some symptoms of test cancer include:

  * Symptom one
  * Symptom two
  * Symptom three

If you have any symptoms that you are worried about, please talk to your family doctor.

### How is it diagnosed?

Tests that may help diagnose test cancer include:

  * Physical examination
  * Blood tests
  * Imaging scans

## Treatment

Treatment options depend on the stage and type of cancer.

### Surgery

Surgery may be an option for early-stage cancers.

### Chemotherapy

Chemotherapy uses drugs to kill cancer cells.
"""


@pytest.fixture
def config_path():
    """Get the configuration file path."""
    return Path(__file__).parent.parent / "config" / "config.yaml"
