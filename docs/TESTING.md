# Testing Guide for Care-Beacon

Docker, docker-compose, and the container-based test workflow this document used to describe are gone. `scripts/run_tests.sh` (which shelled out to `docker exec care-beacon-api ...`) is stale and should not be used — it no longer has a container to run tests in. Tests run directly against the local conda environment instead.

## Quick Start

Always invoke pytest through the pinned interpreter, from `api/`. A bare `pytest` (or `python`) can resolve to the Anaconda base environment instead of the `care-beacon` env and fail outright.

```bash
cd api && /opt/anaconda3/envs/care-beacon/bin/python -m pytest tests/ -q --continue-on-collection-errors
```

Or via the Makefile from the repo root:

```bash
make test        # cd api && $(PY) -m pytest tests/ -v
make test-cov    # same, with an HTML + terminal coverage report
```

`$(PY)` in the Makefile is already pinned to `/opt/anaconda3/envs/care-beacon/bin/python`.

## Running Specific Tests

```bash
cd api
/opt/anaconda3/envs/care-beacon/bin/python -m pytest tests/test_api.py -v

# Single test function
/opt/anaconda3/envs/care-beacon/bin/python -m pytest tests/ -k "test_root_endpoint"

# Pattern match
/opt/anaconda3/envs/care-beacon/bin/python -m pytest tests/ -k "cache"
```

## Test Structure

This reflects the actual files in `api/tests/` (test counts per file are not tracked here — see "Current Test Status" below for the only numbers that matter):

```
api/tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── test_api.py              # API endpoint tests
├── test_caching.py          # Redis cache tests
├── test_chunking.py         # Document chunking tests
├── test_config.py           # Configuration tests
├── test_embeddings.py       # Embedding generation tests
├── test_generation.py       # Answer generation tests
├── test_llm_client.py       # LLM client tests
├── test_models.py           # Data model tests
├── test_parser.py           # Markdown parsing tests
├── test_retrieval.py        # Retrieval engine tests
├── test_stats_store.py      # Redis-backed cost/usage counter tests
└── test_vector_db.py        # Qdrant vector database tests
```

## Current Test Status

**The suite is not fully green, and never has been.** Current baseline:

**6 failed, 239 passed, 0 errors**

The 6 failures are pre-existing and unrelated to the Vercel migration. Do not report this suite as passing, and do not cite older figures that may appear elsewhere in this repo's history (e.g. "134 tests passing," "83% coverage," "100% coverage") — none of those numbers are current. If this baseline changes (for better or worse), update this file rather than letting it go stale again.

No per-module coverage percentages are recorded here, because they were not re-verified after the migration and would otherwise just be repeating unverified numbers. Run `make test-cov` locally if you need current figures.

## Running Tests in CI/CD

There is no CI test workflow in this repository at the time of writing (`.github/workflows/` contains only `keepalive.yml`, which pings `/api/health` — it does not run the test suite). If you add one, it needs to install `api/requirements.txt` + `api/requirements-dev.txt` and invoke pytest the same way as `make test`, not through Docker.

## Troubleshooting

### `pytest` not found / wrong Python picked up

Use the full interpreter path rather than relying on `PATH`:

```bash
/opt/anaconda3/envs/care-beacon/bin/python -m pytest tests/ --version
```

### Tests failing after code changes

1. Re-install dependencies if `requirements.txt` or `requirements-dev.txt` changed:
   ```bash
   cd api && /opt/anaconda3/envs/care-beacon/bin/python -m pip install -r requirements.txt -r requirements-dev.txt
   ```
2. Re-run: `make test` or the direct pytest command above.

### Viewing full tracebacks

```bash
cd api && /opt/anaconda3/envs/care-beacon/bin/python -m pytest tests/ -v --tb=long
```

## Writing New Tests

### Test File Template

```python
"""Tests for <module_name>."""

import pytest
from unittest.mock import Mock, patch

from src.<module> import <YourClass>


@pytest.fixture
def sample_data():
    """Create sample test data."""
    return {
        "field": "value"
    }


def test_basic_functionality(sample_data):
    """Test basic functionality."""
    result = function_to_test(sample_data)
    assert result is not None
    assert result["field"] == "expected"
```

### Best Practices

1. **Use descriptive test names**: `test_<what>_<condition>_<expected_result>`
2. **Use fixtures** for common test data
3. **Mock external dependencies** (OpenAI, Qdrant, Redis)
4. **Test both happy paths and error cases**
5. **Keep tests isolated** - no dependencies between tests
6. **Use parametrize** for testing multiple scenarios

### Example Test

```python
import pytest

@pytest.mark.parametrize("input,expected", [
    ("BC Cancer", "BC Cancer"),
    ("Canadian Cancer Society", "Canadian Cancer Society"),
])
def test_source_filtering(input, expected):
    """Test filtering by different sources."""
    result = filter_by_source(input)
    assert result.source == expected
```

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest-Cov Documentation](https://pytest-cov.readthedocs.io/)
- `docs/TEST_COVERAGE_REPORT.md` — a historical snapshot; not re-verified against the current 6-failed/239-passed baseline
