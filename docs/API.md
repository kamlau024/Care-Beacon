# Care-Beacon API Documentation

Complete REST API documentation for the Care-Beacon Medical RAG System.

## Table of Contents

- [Base URL](#base-url)
- [Authentication](#authentication)
- [Rate Limiting](#rate-limiting)
- [API Endpoints](#api-endpoints)
  - [Root / Health](#root--health)
  - [Question Answering](#question-answering)
  - [System Statistics](#system-statistics)
  - [Cache Management](#cache-management)
- [Data Models](#data-models)
- [Error Handling](#error-handling)
- [Code Examples](#code-examples)

---

## Base URL

**Production**: `http://localhost:8000`
**API Version**: `2.0.0`

All endpoints are prefixed with `/api/v1` unless otherwise specified.

---

## Authentication

Currently, the API does not require authentication. Authentication will be added in a future release.

---

## Rate Limiting

**Default Limits**:
- **60 requests per minute** per IP address
- Rate limiting can be disabled in `config/config.yaml`

**Rate Limit Headers** (coming soon):
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1234567890
```

**Rate Limit Exceeded Response** (HTTP 429):
```json
{
  "error": "HTTPException",
  "message": "Rate limit exceeded. Maximum 60 requests per minute.",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

## API Endpoints

### Root / Health

#### GET `/`

Get API information and available endpoints.

**Response** (HTTP 200):
```json
{
  "name": "Care-Beacon Medical RAG API",
  "version": "2.0.0",
  "description": "Retrieval-Augmented Generation API for cancer information",
  "docs": "/docs",
  "health": "/health",
  "endpoints": {
    "ask": "/api/v1/ask",
    "health": "/health",
    "stats": "/api/v1/stats"
  }
}
```

---

#### GET `/health`

Check API health and service status.

**Response** (HTTP 200):
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "timestamp": "2024-01-15T10:30:00.123456",
  "services": {
    "vector_db": true,
    "redis_cache": true,
    "llm_client": true
  }
}
```

**Service Status**:
- `true`: Service is healthy and operational
- `false`: Service is unavailable or unhealthy

---

### Question Answering

#### POST `/api/v1/ask`

Submit a medical question and receive an AI-generated answer with citations.

**Request Body**:
```json
{
  "question": "What are the symptoms of breast cancer?",
  "cancer_type": "Breast Cancer",
  "source": "BC Cancer",
  "max_results": 5,
  "min_similarity": 0.0
}
```

**Request Parameters**:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `question` | string | **Yes** | - | Patient's medical question (3-500 characters) |
| `cancer_type` | string | No | null | Filter by specific cancer type (e.g., "Breast Cancer") |
| `source` | string | No | null | Filter by source: "BC Cancer" or "Canadian Cancer Society" |
| `max_results` | integer | No | 5 | Maximum source chunks to retrieve (1-10) |
| `min_similarity` | float | No | 0.0 | Minimum similarity threshold (0.0-1.0) |

**Response** (HTTP 200):
```json
{
  "question": "What are the symptoms of breast cancer?",
  "answer": "Common symptoms of breast cancer include lumps in the breast tissue, changes in breast shape or size, skin dimpling, nipple discharge, and changes in the skin texture. Early detection through regular self-examinations is important. [1][2]",
  "sources": [
    {
      "article_title": "Breast Cancer - Signs and Symptoms",
      "section": "Common Symptoms",
      "url": "https://www.bccancer.bc.ca/health-info/types-of-cancer/breast-cancer",
      "paragraph_index": 2,
      "text_excerpt": "The most common symptom of breast cancer is a new lump or mass in the breast. A lump that is painless, hard, and has irregular edges is more likely to be cancer...",
      "similarity_score": 0.89,
      "source": "BC Cancer"
    },
    {
      "article_title": "Breast Cancer Overview",
      "section": "Warning Signs",
      "url": "https://www.bccancer.bc.ca/health-info/types-of-cancer/breast-cancer",
      "paragraph_index": 5,
      "text_excerpt": "Changes in breast size or shape, skin dimpling, nipple retraction, and unusual discharge are important warning signs that should be evaluated by a healthcare provider...",
      "similarity_score": 0.85,
      "source": "BC Cancer"
    }
  ],
  "disclaimer": "This information is for educational purposes only and does not constitute medical advice. Please consult with a qualified healthcare provider for diagnosis and treatment recommendations.",
  "model": "gpt-4o-mini",
  "metadata": {
    "tokens_used": 523,
    "cost": 0.000261,
    "generation_time_ms": 1245.67,
    "cached": false,
    "sources_count": 2
  }
}
```

**Citation Format in Answer**:
- Citations are referenced as `[1]`, `[2]`, etc.
- Each number corresponds to a source in the `sources` array
- Sources are ordered by relevance (similarity score)

**Filtering Examples**:

1. **By Cancer Type**:
```json
{
  "question": "What are treatment options?",
  "cancer_type": "Lung Cancer"
}
```

2. **By Source**:
```json
{
  "question": "How is chemotherapy given?",
  "source": "BC Cancer"
}
```

3. **Combined Filters**:
```json
{
  "question": "What is immunotherapy?",
  "cancer_type": "Melanoma",
  "source": "Canadian Cancer Society"
}
```

4. **High Confidence Only**:
```json
{
  "question": "What causes cancer?",
  "min_similarity": 0.7
}
```
*Note: When `min_similarity` > 0, `max_results` automatically increases to 50 to return all qualifying sources.*

**Error Responses**:

**Validation Error** (HTTP 422):
```json
{
  "error": "ValidationError",
  "message": "Invalid request data",
  "detail": "Field 'question': String should have at least 3 characters",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Server Error** (HTTP 500):
```json
{
  "error": "HTTPException",
  "message": "Failed to generate answer: OpenAI API error",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

### System Statistics

#### GET `/api/v1/stats`

Get system usage statistics including LLM costs, cache performance, and cost savings.

**Response** (HTTP 200):
```json
{
  "llm": {
    "total_calls": 1523,
    "total_tokens": 876543,
    "total_cost": 0.438271,
    "total_input_tokens": 654321,
    "total_output_tokens": 222222,
    "average_tokens_per_call": 575
  },
  "cache": {
    "total_queries": 2156,
    "cache_hits": 633,
    "cache_misses": 1523,
    "hit_rate": 0.2936,
    "total_cost_saved": 0.128691
  },
  "retrieval": {
    "total_cost": 0.002345
  },
  "total_cost": 0.440616,
  "total_cost_saved": 0.128691,
  "cost_reduction_percent": 22.6
}
```

**Metrics Explained**:

| Metric | Description |
|--------|-------------|
| `llm.total_calls` | Number of LLM API calls made |
| `llm.total_tokens` | Total tokens processed (input + output) |
| `llm.total_cost` | Total cost in USD for LLM API calls |
| `cache.hit_rate` | Percentage of queries served from cache (0-1) |
| `cache.total_cost_saved` | Estimated cost savings from cache hits |
| `cost_reduction_percent` | Overall cost reduction percentage |

---

#### POST `/api/v1/stats/reset`

Reset all statistics counters. **Use with caution** - this action cannot be undone.

**Response** (HTTP 200):
```json
{
  "message": "Statistics reset successfully",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

### Cache Management

#### POST `/api/v1/cache/clear`

Clear all cached query results. **Use with caution** - this will cause all subsequent queries to hit the LLM API.

**Response** (HTTP 200):
```json
{
  "message": "Cache cleared successfully",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Effects**:
- All cached question-answer pairs are deleted
- Next queries will be slower and more expensive
- Cache statistics are preserved
- Useful for testing or after data updates

---

## Data Models

### QuestionRequest

```typescript
{
  question: string;        // 3-500 characters, required
  cancer_type?: string;    // Optional filter
  source?: string;         // "BC Cancer" or "Canadian Cancer Society"
  max_results?: number;    // 1-10, default: 5
  min_similarity?: number; // 0.0-1.0, default: 0.0
}
```

### CitationResponse

```typescript
{
  article_title: string;       // Source article title
  section: string;             // Section within article
  url: string;                 // Full URL to source
  paragraph_index: number;     // 0-indexed paragraph number
  text_excerpt: string;        // Relevant text excerpt
  similarity_score: number;    // 0.0-1.0 relevance score
  source: string;              // "BC Cancer" or "Canadian Cancer Society"
}
```

### QuestionResponse

```typescript
{
  question: string;               // Original question
  answer: string;                 // Generated answer with citations
  sources: CitationResponse[];    // Source citations
  disclaimer: string;             // Medical disclaimer
  model: string;                  // LLM model used (e.g., "gpt-4o-mini")
  metadata: {
    tokens_used: number;          // Total tokens consumed
    cost: number;                 // Cost in USD
    generation_time_ms: number;   // Response time
    cached: boolean;              // Whether from cache
    sources_count: number;        // Number of sources used
  };
}
```

### ErrorResponse

```typescript
{
  error: string;        // Error type
  message: string;      // Human-readable error message
  detail?: string;      // Detailed error information
  timestamp: string;    // ISO 8601 timestamp
}
```

---

## Error Handling

### Error Types

| HTTP Code | Error Type | Description |
|-----------|------------|-------------|
| 400 | BadRequest | Invalid request format |
| 422 | ValidationError | Request validation failed |
| 429 | HTTPException | Rate limit exceeded |
| 500 | HTTPException | Internal server error |
| 500 | InternalServerError | Unexpected error occurred |

### Common Error Scenarios

1. **Question Too Short/Long**:
```json
{
  "error": "ValidationError",
  "message": "Invalid request data",
  "detail": "Field 'question': String should have at least 3 characters"
}
```

2. **Invalid max_results**:
```json
{
  "error": "ValidationError",
  "message": "Invalid request data",
  "detail": "Field 'max_results': Input should be less than or equal to 10"
}
```

3. **LLM API Error**:
```json
{
  "error": "HTTPException",
  "message": "Failed to generate answer: API rate limit exceeded",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

## Code Examples

### Python

```python
import requests

# Basic question
response = requests.post(
    "http://localhost:8000/api/v1/ask",
    json={
        "question": "What are the symptoms of breast cancer?",
        "max_results": 5
    }
)

data = response.json()
print(f"Answer: {data['answer']}")
print(f"\nSources ({len(data['sources'])}):")
for i, source in enumerate(data['sources'], 1):
    print(f"[{i}] {source['article_title']} - {source['section']}")
    print(f"    Similarity: {source['similarity_score']:.2f}")
    print(f"    {source['url']}")
```

**With Filters**:
```python
# Filter by cancer type and source
response = requests.post(
    "http://localhost:8000/api/v1/ask",
    json={
        "question": "What are treatment side effects?",
        "cancer_type": "Lung Cancer",
        "source": "BC Cancer",
        "min_similarity": 0.7
    }
)
```

### cURL

```bash
# Basic question
curl -X POST "http://localhost:8000/api/v1/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the symptoms of breast cancer?",
    "max_results": 5
  }'

# With filters
curl -X POST "http://localhost:8000/api/v1/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is radiation therapy?",
    "cancer_type": "Prostate Cancer",
    "source": "BC Cancer"
  }'

# Get statistics
curl "http://localhost:8000/api/v1/stats"

# Health check
curl "http://localhost:8000/health"
```

### JavaScript / TypeScript

```typescript
// Using fetch API
async function askQuestion(question: string, filters = {}) {
  const response = await fetch('http://localhost:8000/api/v1/ask', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      question,
      max_results: 5,
      ...filters
    })
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(`API Error: ${error.message}`);
  }

  return await response.json();
}

// Usage
try {
  const result = await askQuestion(
    "What are the symptoms of breast cancer?",
    { cancer_type: "Breast Cancer" }
  );

  console.log(result.answer);
  console.log(`Cost: $${result.metadata.cost.toFixed(6)}`);
  console.log(`Sources: ${result.sources.length}`);
} catch (error) {
  console.error('Failed to get answer:', error);
}
```

### React Hook Example

```typescript
import { useState } from 'react';

function useAskQuestion() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const askQuestion = async (
    question: string,
    options = {}
  ) => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch('http://localhost:8000/api/v1/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, ...options })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message);
      }

      return await response.json();
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  return { askQuestion, loading, error };
}

// Usage in component
function QuestionForm() {
  const { askQuestion, loading, error } = useAskQuestion();
  const [answer, setAnswer] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const question = e.target.question.value;

    try {
      const result = await askQuestion(question);
      setAnswer(result);
    } catch (err) {
      console.error('Error:', err);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <input name="question" placeholder="Ask a medical question..." />
      <button disabled={loading}>
        {loading ? 'Asking...' : 'Submit'}
      </button>
      {error && <div className="error">{error}</div>}
      {answer && <div className="answer">{answer.answer}</div>}
    </form>
  );
}
```

---

## Interactive Documentation

### Swagger UI

Access interactive API documentation at:
```
http://localhost:8000/docs
```

Features:
- Try out endpoints directly in the browser
- See request/response schemas
- Test different parameters
- View all available endpoints

### ReDoc

Alternative documentation interface:
```
http://localhost:8000/redoc
```

Features:
- Clean, professional documentation layout
- Detailed schema information
- Code samples in multiple languages
- Searchable endpoint list

---

## Best Practices

### 1. Caching

The API caches responses automatically. Identical questions return cached results:

```python
# First call - generates answer (slower, costs money)
response1 = ask_question("What is chemotherapy?")

# Second call - returns cached result (instant, free)
response2 = ask_question("What is chemotherapy?")

# Check if cached
print(response2['metadata']['cached'])  # True
```

### 2. Error Handling

Always implement proper error handling:

```python
try:
    response = requests.post(url, json=data, timeout=30)
    response.raise_for_status()
    result = response.json()
except requests.exceptions.Timeout:
    print("Request timed out")
except requests.exceptions.HTTPError as e:
    print(f"HTTP error: {e.response.status_code}")
    print(e.response.json())
except Exception as e:
    print(f"Unexpected error: {e}")
```

### 3. Source Filtering

Use filters to narrow down sources and improve response relevance:

```python
# General oncology question - use both sources
ask_question("What is cancer staging?")

# BC-specific programs - use BC Cancer only
ask_question(
    "What support programs are available?",
    source="BC Cancer"
)

# Specific cancer type - filter by type
ask_question(
    "What are treatment options?",
    cancer_type="Breast Cancer"
)
```

### 4. Response Time Optimization

```python
# Use min_similarity for high-confidence sources only
# This returns more sources but filters by quality
response = ask_question(
    "What causes lung cancer?",
    min_similarity=0.7
)

# Use fewer max_results for faster responses
response = ask_question(
    "What is a biopsy?",
    max_results=3
)
```

### 5. Cost Monitoring

```python
# Check statistics regularly
stats = requests.get("http://localhost:8000/api/v1/stats").json()

print(f"Total cost: ${stats['total_cost']:.4f}")
print(f"Cost saved: ${stats['total_cost_saved']:.4f}")
print(f"Cache hit rate: {stats['cache']['hit_rate']:.1%}")
```

---

## Performance

### Response Times

| Operation | Typical Time | Notes |
|-----------|-------------|-------|
| Cache hit | 50-100ms | Instant response from Redis |
| Cache miss | 1-3 seconds | Includes embedding + LLM generation |
| Embedding generation | 100-300ms | OpenAI API call |
| Vector search | 50-150ms | Local Chroma search |
| LLM generation | 1-2 seconds | OpenAI GPT-4o-mini |

### Optimization Tips

1. **Enable caching** - Reduces costs by 30-50%
2. **Use appropriate max_results** - Lower values are faster
3. **Filter by cancer type** - Reduces search space
4. **Batch similar questions** - Take advantage of caching

---

## Limits and Quotas

| Resource | Limit | Notes |
|----------|-------|-------|
| Request rate | 60/minute | Per IP address |
| Question length | 3-500 chars | Validation enforced |
| max_results | 1-10 | Default: 5 |
| min_similarity | 0.0-1.0 | Default: 0.0 |
| Response size | ~50KB avg | Varies by source count |
| Timeout | 30 seconds | Server-side timeout |

---

## Changelog

### Version 2.0.0 (2024-01-15)
- ✅ Migrated to FastAPI lifespan pattern
- ✅ Updated to Pydantic v2 (ConfigDict)
- ✅ Added source filtering (BC Cancer / Canadian Cancer Society)
- ✅ Improved error handling and validation
- ✅ 100% test coverage
- ✅ Zero deprecation warnings

### Version 1.0.0 (2024-01-01)
- Initial release
- Basic question answering
- Citation support
- Redis caching
- Vector search

---

## Support

For issues, questions, or feature requests:
- GitHub Issues: [github.com/care-beacon/issues](https://github.com/care-beacon/issues)
- Documentation: [docs/](../docs/)
- Email: support@care-beacon.example.com

---

**Last Updated**: 2024-01-15
**API Version**: 2.0.0
