"""Pytest configuration and fixtures for Care-Beacon tests."""

import os
from pathlib import Path

import pytest

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
