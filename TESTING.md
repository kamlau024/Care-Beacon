# Testing Guide for Care-Beacon

## Quick Start

Run tests using the provided shell script:

```bash
./run_tests.sh
```

## Test Script Options

### Basic Usage

```bash
# Run all tests (default)
./run_tests.sh

# Run with coverage report
./run_tests.sh -c

# Run in verbose mode (shows each test)
./run_tests.sh -v

# Quick run (minimal output)
./run_tests.sh -q

# Show help
./run_tests.sh -h
```

### Running Specific Tests

```bash
# Run specific test file
./run_tests.sh -f test_api.py

# Run specific test function
./run_tests.sh -t test_root_endpoint

# Run tests matching a pattern
./run_tests.sh -t "test_cache"
```

### Combined Options

```bash
# Run with coverage and verbose output
./run_tests.sh -c -v

# Run specific file with coverage
./run_tests.sh -f test_api.py -c
```

## Manual Test Commands

If you prefer to run tests manually:

```bash
# Run all tests
docker exec care-beacon-api pytest /app/tests/

# Run with coverage
docker exec care-beacon-api pytest /app/tests/ --cov=src --cov-report=term-missing

# Run specific test file
docker exec care-beacon-api pytest /app/tests/test_api.py

# Run in verbose mode
docker exec care-beacon-api pytest /app/tests/ -v

# Run quick mode (minimal output)
docker exec care-beacon-api pytest /app/tests/ -q
```

## Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── test_api.py              # API endpoint tests (17 tests)
├── test_caching.py          # Redis cache tests (19 tests)
├── test_chunking.py         # Document chunking tests (15 tests)
├── test_config.py           # Configuration tests (6 tests)
├── test_embeddings.py       # Embedding generation tests (11 tests)
├── test_generation.py       # Answer generation tests (12 tests)
├── test_parser.py           # Markdown parsing tests (15 tests)
├── test_retrieval.py        # Retrieval engine tests (19 tests)
└── test_vector_db.py        # Vector database tests (20 tests)
```

## Current Test Status

✅ **134 tests passing**
📊 **83% code coverage**

## Coverage by Module

| Module | Coverage |
|--------|----------|
| API Models | 100% |
| Caching Models | 100% |
| Chunking | 100% |
| Generation Models | 100% |
| Parser | 89% |
| Storage | 90% |
| Retrieval | 91-98% |
| Answer Generator | 82% |
| Config Loader | 83% |
| Caching | 80% |
| Embeddings | 66% |
| LLM Client | 16% ⚠️ |

## Running Tests in CI/CD

For continuous integration, you can use:

```yaml
# GitHub Actions example
- name: Run tests
  run: |
    docker-compose up -d
    docker-compose exec -T api pytest tests/ --cov=src --cov-report=xml

- name: Upload coverage
  uses: codecov/codecov-action@v3
```

## Troubleshooting

### Container Not Running

If you get an error that the container is not running:

```bash
# Start all services
docker-compose up -d

# Check service status
docker-compose ps

# Then run tests
./run_tests.sh
```

### Tests Failing After Code Changes

If you've made code changes and tests are failing:

1. Rebuild the Docker container:
   ```bash
   docker-compose build api
   docker-compose up -d api
   ```

2. Run tests again:
   ```bash
   ./run_tests.sh -v
   ```

### Viewing Logs

```bash
# View test output with full traceback
docker exec care-beacon-api pytest /app/tests/ -v --tb=long

# View Docker logs
docker-compose logs api
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
3. **Mock external dependencies** (APIs, databases)
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
- [Coverage Report](TEST_COVERAGE_REPORT.md)
