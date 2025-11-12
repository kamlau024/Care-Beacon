# Care-Beacon Test Coverage Report

**Date:** November 11, 2025
**Generated from:** Docker container test run

## Executive Summary

- **Total Tests:** 134
- **Passing:** 132 (98.5%)
- **Failing:** 2 (1.5%)
- **Overall Code Coverage:** 83%
- **Test Code:** 2,553 lines across 11 test files

## Coverage by Module

| Module | Statements | Missing | Coverage | Notes |
|--------|-----------|---------|----------|-------|
| **API** | | | | |
| `src/api/models.py` | 53 | 0 | **100%** | ✅ Excellent |
| `src/api/main.py` | 134 | 36 | **73%** | ⚠️ Missing startup/shutdown handlers |
| **Caching** | | | | |
| `src/caching/models.py` | 43 | 0 | **100%** | ✅ Excellent |
| `src/caching/redis_cache.py` | 124 | 25 | **80%** | ⚠️ Missing error handling paths |
| **Embeddings** | | | | |
| `src/embeddings/chunking.py` | 68 | 0 | **100%** | ✅ Excellent |
| `src/embeddings/embedding_generator.py` | 100 | 34 | **66%** | ⚠️ Missing error cases |
| **Generation** | | | | |
| `src/generation/models.py` | 83 | 0 | **100%** | ✅ Excellent |
| `src/generation/answer_generator.py` | 80 | 14 | **82%** | ✅ Good |
| `src/generation/llm_client.py` | 68 | 57 | **16%** | 🔴 Needs attention |
| **Ingestion** | | | | |
| `src/ingestion/markdown_parser.py` | 113 | 12 | **89%** | ✅ Good |
| **Retrieval** | | | | |
| `src/retrieval/models.py` | 59 | 1 | **98%** | ✅ Excellent |
| `src/retrieval/retrieval_engine.py` | 43 | 4 | **91%** | ✅ Good |
| **Storage** | | | | |
| `src/storage/models.py` | 87 | 9 | **90%** | ✅ Good |
| `src/storage/vector_db.py` | 108 | 11 | **90%** | ✅ Good |
| **Config** | | | | |
| `src/config_loader.py` | 48 | 8 | **83%** | ✅ Good |

## Test Files Overview

| Test File | Lines | Tests | Focus Area |
|-----------|-------|-------|------------|
| `test_api.py` | 325 | 17 | REST API endpoints, request/response validation |
| `test_caching.py` | 359 | 19 | Redis cache operations, stats tracking |
| `test_chunking.py` | 311 | 15 | Document chunking logic |
| `test_config.py` | 57 | 6 | Configuration loading |
| `test_embeddings.py` | 209 | 11 | Embedding generation, cost tracking |
| `test_generation.py` | 275 | 12 | Answer generation, citation formatting |
| `test_parser.py` | 308 | 15 | Markdown parsing, metadata extraction |
| `test_retrieval.py` | 321 | 19 | Vector search, filtering |
| `test_vector_db.py` | 316 | 20 | Chroma database operations |

## Failing Tests (Action Required)

### 1. `test_citation_response_model` ❌

**Location:** `tests/test_api.py:284`

**Issue:** Missing required fields in CitationResponse model test

**Error:**
```
ValidationError: 2 validation errors for CitationResponse
- similarity_score: Field required
- source: Field required
```

**Root Cause:** The test creates a Citation without the new required fields `similarity_score` and `source` that were added to support multiple data sources.

**Fix Required:**
```python
# Current (line 20-27)
citation = Citation(
    chunk_id="test_001",
    article_title="Breast Cancer",
    section="Symptoms",
    url="https://example.com/breast-cancer",
    paragraph_index=0,
    text_excerpt="Test excerpt about symptoms",
)

# Should be:
citation = Citation(
    chunk_id="test_001",
    article_title="Breast Cancer",
    section="Symptoms",
    url="https://example.com/breast-cancer",
    paragraph_index=0,
    text_excerpt="Test excerpt about symptoms",
    similarity_score=0.85,  # ADD THIS
    source="BC Cancer",      # ADD THIS
)
```

### 2. `test_config_retrieval_settings` ❌

**Location:** `tests/test_config.py:50`

**Issue:** Config key path changed or missing

**Error:**
```
AssertionError: assert None == 0.5
```

**Root Cause:** The config path `retrieval.min_similarity` doesn't exist or the config structure changed.

**Fix Required:** Update config.yaml or adjust test to use correct config path.

## Multiple Data Source Support

### Current Status: ⚠️ Partially Implemented

The codebase supports multiple data sources:

1. **BC Cancer** (`scraped_data/bc-cancer/`)
2. **Canadian Cancer Society** (`scraped_data/canadian-cancer-society/`)
3. Legacy **articles** folder (`scraped_data/articles/`)

### Data Source Implementation

**API Support:** ✅ Fully implemented
- `QuestionRequest` model has `source` field (line 23-27 in `src/api/models.py`)
- Supports filtering by source: `"BC Cancer"` or `"Canadian Cancer Society"`

**Database Schema:** ✅ Implemented
- `Article` and `Chunk` models have `source` field
- Defaults to `"BC Cancer"` (line 35, 79 in `src/storage/models.py`)

**Parser:** ⚠️ Needs Enhancement
- Currently defaults source to `"BC Cancer"`
- Should derive source from directory path:
  - `bc-cancer/*` → `"BC Cancer"`
  - `canadian-cancer-society/*` → `"Canadian Cancer Society"`

### Tests Needing Updates for Multiple Sources

#### ✅ Already Handle Multiple Sources:
- `test_chunking.py` - Tests `source` field
- `test_parser.py` - Tests `source` field
- `test_vector_db.py` - Tests `source` metadata

#### ⚠️ Need Enhancement:
1. **`test_api.py`**
   - Add test for filtering by Canadian Cancer Society
   - Test with mixed sources in response
   - Example:
     ```python
     def test_ask_question_with_source_filter(client, mock_generator):
         """Test question answering with source filter."""
         request_data = {
             "question": "What are treatment options?",
             "source": "Canadian Cancer Society",
             "max_results": 3,
         }
         # ... test implementation
     ```

2. **`test_retrieval.py`**
   - Add test for retrieving from specific source
   - Test mixed source results with proper ordering

3. **`test_parser.py`**
   - Add test for auto-detecting source from file path
   - Test both BC Cancer and Canadian Cancer Society paths

## Areas Needing Attention

### 🔴 Critical (Low Coverage):

**1. `src/generation/llm_client.py` - 16% coverage**
- Missing tests for error handling
- API failure scenarios untested
- Token counting not fully tested
- **Recommendation:** Add integration tests with mocked API responses

### ⚠️ Medium Priority:

**2. `src/embeddings/embedding_generator.py` - 66% coverage**
- Missing error case tests
- API failure handling untested
- Batch splitting edge cases
- **Recommendation:** Add tests for API errors, rate limiting

**3. `src/caching/redis_cache.py` - 80% coverage**
- Connection failure paths partially tested
- Serialization edge cases missing
- **Recommendation:** Add more error scenario tests

**4. `src/api/main.py` - 73% coverage**
- Startup/shutdown handlers not tested (lines 396-410, 416-417)
- Some error paths untested
- **Recommendation:** Add lifecycle event tests

## Recommended Test Additions

### High Priority:

1. **Multi-Source Integration Tests**
   ```python
   def test_query_with_mixed_sources():
       """Test querying across BC Cancer and Canadian Cancer Society."""
       # Verify results contain both sources
       # Verify source filtering works
       # Verify proper citation of sources
   ```

2. **Source Auto-Detection Tests**
   ```python
   def test_parse_bc_cancer_file():
       """Test parsing sets source to BC Cancer."""

   def test_parse_canadian_cancer_society_file():
       """Test parsing sets source to Canadian Cancer Society."""
   ```

3. **LLM Client Error Handling**
   ```python
   def test_llm_client_api_error():
       """Test LLM client handles API errors gracefully."""

   def test_llm_client_rate_limiting():
       """Test LLM client handles rate limiting."""
   ```

### Medium Priority:

4. **Cache Edge Cases**
   ```python
   def test_cache_large_response():
       """Test caching very large responses."""

   def test_cache_concurrent_access():
       """Test cache handles concurrent requests."""
   ```

5. **Embedding Error Scenarios**
   ```python
   def test_embedding_api_timeout():
       """Test embedding generation handles timeouts."""
   ```

## Continuous Integration Recommendations

### GitHub Actions Workflow:

```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run tests with coverage
        run: |
          docker-compose build
          docker-compose run api pytest tests/ \
            --cov=src \
            --cov-report=html \
            --cov-report=term \
            --cov-fail-under=80
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

### Coverage Goals:

- **Target:** 90% overall coverage
- **Minimum:** 80% per module
- **Critical paths:** 100% (API endpoints, data models)

## Action Items

### Immediate (Sprint 1):
- [ ] Fix 2 failing tests
- [ ] Add multi-source filtering tests to `test_api.py`
- [ ] Add source auto-detection to parser
- [ ] Add tests for Canadian Cancer Society data

### Short-term (Sprint 2):
- [ ] Increase `llm_client.py` coverage to >80%
- [ ] Add error handling tests for embedding generator
- [ ] Add lifecycle event tests for API

### Medium-term (Sprint 3):
- [ ] Set up CI/CD pipeline with coverage reporting
- [ ] Add integration tests for full query flow with multiple sources
- [ ] Add performance tests for large datasets

## Testing Best Practices Observed ✅

- ✅ Comprehensive fixtures in `conftest.py`
- ✅ Good use of mocking for external dependencies
- ✅ Separate test files by module
- ✅ Clear test names following `test_<functionality>` pattern
- ✅ Good coverage of happy path scenarios
- ⚠️ Could improve error path testing
- ⚠️ Could add more integration tests

## Conclusion

The Care-Beacon project has **strong test coverage (83%)** with a solid foundation of 134 tests. The main areas for improvement are:

1. **Fix 2 failing tests** related to new multi-source functionality
2. **Add tests for Canadian Cancer Society data** to ensure both sources work correctly
3. **Improve LLM client testing** (currently only 16% coverage)
4. **Add source auto-detection** to the parser and test it

The codebase is well-positioned to support multiple data sources, but tests need to catch up with the recent additions of the Canadian Cancer Society dataset.

---

**Next Steps:**
1. Review and fix failing tests
2. Add multi-source test cases
3. Update parser to auto-detect source from file path
4. Set up CI/CD with coverage reporting
