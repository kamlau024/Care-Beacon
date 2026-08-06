# Care-Beacon Usage Examples & Tutorials

Practical examples and tutorials for using the Care-Beacon Medical RAG API.

## Table of Contents

- [Quick Start](#quick-start)
- [Basic Usage](#basic-usage)
- [Advanced Queries](#advanced-queries)
- [Integration Examples](#integration-examples)
- [Best Practices](#best-practices)
- [Common Use Cases](#common-use-cases)
- [Performance Optimization](#performance-optimization)

---

## Quick Start

### Your First Query

There is no `docker-compose.yml` in this project anymore — local development runs both Vercel Services together via `vercel dev`. The examples below use `http://localhost:8000` as a placeholder base URL; substitute the actual port `vercel dev` assigns you locally, or `https://care-beacon-health.vercel.app` for the live deployment. Note the health check path is `/api/health`, not `/health`.

```bash
# Start both services locally
vercel dev

# Wait for services to be ready
curl http://localhost:8000/api/health

# Ask your first question
curl -X POST "http://localhost:8000/api/v1/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the symptoms of breast cancer?"
  }'
```

**Response**:
```json
{
  "question": "What are the symptoms of breast cancer?",
  "answer": "Common symptoms include lumps in the breast, changes in breast shape or size, skin dimpling, nipple discharge, and changes in skin texture. [1][2]",
  "sources": [...],
  "disclaimer": "This information is for educational purposes only...",
  "metadata": {
    "cost": 0.000261,
    "generation_time_ms": 1245.67,
    "cached": false
  }
}
```

---

## Basic Usage

### 1. Simple Question

**Ask a general cancer question**:

```python
import requests

def ask_question(question):
    response = requests.post(
        "http://localhost:8000/api/v1/ask",
        json={"question": question}
    )
    return response.json()

# Example
result = ask_question("What is chemotherapy?")
print(result['answer'])
```

### 2. Filter by Cancer Type

**Get information specific to a cancer type**:

```python
result = ask_question_with_filters(
    question="What are the treatment options?",
    cancer_type="Lung Cancer"
)
```

**Full Example**:
```python
import requests

def ask_with_cancer_type(question, cancer_type):
    response = requests.post(
        "http://localhost:8000/api/v1/ask",
        json={
            "question": question,
            "cancer_type": cancer_type
        }
    )
    return response.json()

# Examples
lung_treatment = ask_with_cancer_type(
    "What are treatment options?",
    "Lung Cancer"
)

breast_symptoms = ask_with_cancer_type(
    "What are early warning signs?",
    "Breast Cancer"
)
```

### 3. Filter by Source

**Get information from specific source**:

```python
# BC Cancer specific
bc_result = ask_question_with_filters(
    question="What support programs are available?",
    source="BC Cancer"
)

# Canadian Cancer Society specific
ccs_result = ask_question_with_filters(
    question="How can I reduce my cancer risk?",
    source="Canadian Cancer Society"
)
```

---

## Advanced Queries

### 1. High-Confidence Answers Only

Use `min_similarity` to get only high-quality matches:

```python
def ask_high_confidence(question, min_similarity=0.7):
    """Get only high-confidence answers."""
    response = requests.post(
        "http://localhost:8000/api/v1/ask",
        json={
            "question": question,
            "min_similarity": min_similarity
        }
    )
    return response.json()

# This will return more sources, but only those above 0.7 similarity
result = ask_high_confidence(
    "What causes lung cancer?",
    min_similarity=0.75
)

print(f"Found {len(result['sources'])} high-quality sources")
for source in result['sources']:
    print(f"- {source['article_title']}: {source['similarity_score']:.2f}")
```

### 2. Combined Filters

**Use multiple filters for precise results**:

```python
def ask_precise_question(question, cancer_type, source, min_similarity=0.6):
    """Ask with multiple filters for precise results."""
    response = requests.post(
        "http://localhost:8000/api/v1/ask",
        json={
            "question": question,
            "cancer_type": cancer_type,
            "source": source,
            "min_similarity": min_similarity
        }
    )
    return response.json()

# Example: BC Cancer's information on breast cancer treatment
result = ask_precise_question(
    question="What are the side effects of radiation therapy?",
    cancer_type="Breast Cancer",
    source="BC Cancer",
    min_similarity=0.7
)
```

### 3. Batch Processing

**Process multiple questions efficiently**:

```python
import concurrent.futures
import requests

def ask_question_async(question):
    """Ask a question (for concurrent processing)."""
    response = requests.post(
        "http://localhost:8000/api/v1/ask",
        json={"question": question}
    )
    return question, response.json()

# List of questions to ask
questions = [
    "What are symptoms of breast cancer?",
    "What are symptoms of lung cancer?",
    "What are symptoms of prostate cancer?",
    "What are symptoms of colorectal cancer?",
]

# Process in parallel (max 5 concurrent requests to respect rate limits)
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
    future_to_question = {
        executor.submit(ask_question_async, q): q
        for q in questions
    }

    results = {}
    for future in concurrent.futures.as_completed(future_to_question):
        question, result = future.result()
        results[question] = result
        print(f"✓ Got answer for: {question[:50]}...")

print(f"\nProcessed {len(results)} questions")
```

---

## Integration Examples

### 1. Python Application

**Complete integration with error handling**:

```python
import requests
from typing import Optional, Dict, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CareBeaconClient:
    """Client for Care-Beacon API."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()

    def ask_question(
        self,
        question: str,
        cancer_type: Optional[str] = None,
        source: Optional[str] = None,
        max_results: int = 5,
        min_similarity: float = 0.0,
        timeout: int = 30
    ) -> Dict:
        """
        Ask a medical question.

        Args:
            question: The medical question to ask
            cancer_type: Optional cancer type filter
            source: Optional source filter ("BC Cancer" or "Canadian Cancer Society")
            max_results: Maximum number of sources (1-10)
            min_similarity: Minimum similarity threshold (0.0-1.0)
            timeout: Request timeout in seconds

        Returns:
            Dict containing answer, sources, and metadata

        Raises:
            requests.exceptions.RequestException: If request fails
        """
        url = f"{self.base_url}/api/v1/ask"

        payload = {
            "question": question,
            "max_results": max_results,
            "min_similarity": min_similarity
        }

        if cancer_type:
            payload["cancer_type"] = cancer_type
        if source:
            payload["source"] = source

        try:
            logger.info(f"Asking question: {question[:50]}...")
            response = self.session.post(
                url,
                json=payload,
                timeout=timeout
            )
            response.raise_for_status()

            result = response.json()
            logger.info(
                f"Got answer with {len(result['sources'])} sources "
                f"(cost: ${result['metadata']['cost']:.6f})"
            )

            return result

        except requests.exceptions.Timeout:
            logger.error(f"Request timed out after {timeout}s")
            raise
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {e.response.status_code}")
            logger.error(f"Response: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    def get_stats(self) -> Dict:
        """Get API statistics."""
        url = f"{self.base_url}/api/v1/stats"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def check_health(self) -> bool:
        """Check if API is healthy."""
        try:
            url = f"{self.base_url}/api/health"  # not /health -- that path no longer exists
            response = self.session.get(url, timeout=5)
            return response.status_code == 200
        except:
            return False

# Usage
if __name__ == "__main__":
    client = CareBeaconClient()

    # Check health
    if not client.check_health():
        print("API is not available!")
        exit(1)

    # Ask a question
    try:
        result = client.ask_question(
            "What are the symptoms of breast cancer?",
            cancer_type="Breast Cancer"
        )

        print(f"Question: {result['question']}")
        print(f"\nAnswer: {result['answer']}")
        print(f"\nSources ({len(result['sources'])}):")
        for i, source in enumerate(result['sources'], 1):
            print(f"  [{i}] {source['article_title']}")
            print(f"      Similarity: {source['similarity_score']:.2f}")

        print(f"\nCost: ${result['metadata']['cost']:.6f}")
        print(f"Time: {result['metadata']['generation_time_ms']:.0f}ms")

    except Exception as e:
        logger.error(f"Failed to get answer: {e}")
```

### 2. Web Application (Flask)

**Flask web app with Care-Beacon integration**:

```python
from flask import Flask, render_template, request, jsonify
import requests

app = Flask(__name__)
CARE_BEACON_API = "http://localhost:8000"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/ask", methods=["POST"])
def ask():
    """Handle question from frontend."""
    data = request.json
    question = data.get("question")

    if not question:
        return jsonify({"error": "Question is required"}), 400

    try:
        # Call Care-Beacon API
        response = requests.post(
            f"{CARE_BEACON_API}/api/v1/ask",
            json={
                "question": question,
                "cancer_type": data.get("cancer_type"),
                "source": data.get("source")
            },
            timeout=30
        )

        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({
                "error": "Failed to get answer",
                "details": response.json()
            }), response.status_code

    except requests.exceptions.Timeout:
        return jsonify({"error": "Request timed out"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)
```

**Frontend (index.html)**:
```html
<!DOCTYPE html>
<html>
<head>
    <title>Care-Beacon Medical Assistant</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; }
        #question { width: 100%; padding: 10px; font-size: 16px; }
        button { padding: 10px 20px; font-size: 16px; cursor: pointer; }
        #answer { margin-top: 20px; padding: 20px; background: #f5f5f5; border-radius: 5px; }
        .source { margin: 10px 0; padding: 10px; background: white; border-left: 3px solid #007bff; }
        .loading { color: #666; }
    </style>
</head>
<body>
    <h1>Care-Beacon Medical Assistant</h1>

    <input type="text" id="question" placeholder="Ask a medical question..." />
    <button onclick="askQuestion()">Ask</button>

    <div id="answer"></div>

    <script>
        async function askQuestion() {
            const question = document.getElementById('question').value;
            const answerDiv = document.getElementById('answer');

            if (!question) {
                alert('Please enter a question');
                return;
            }

            answerDiv.innerHTML = '<p class="loading">Thinking...</p>';

            try {
                const response = await fetch('/api/ask', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ question })
                });

                const data = await response.json();

                if (response.ok) {
                    let html = `<h3>Answer:</h3><p>${data.answer}</p>`;
                    html += `<h4>Sources:</h4>`;

                    data.sources.forEach((source, i) => {
                        html += `
                            <div class="source">
                                <strong>[${i + 1}] ${source.article_title}</strong><br>
                                Section: ${source.section}<br>
                                Similarity: ${(source.similarity_score * 100).toFixed(0)}%<br>
                                <a href="${source.url}" target="_blank">View Source</a>
                            </div>
                        `;
                    });

                    html += `<p><small>Cost: $${data.metadata.cost.toFixed(6)} |
                             Time: ${data.metadata.generation_time_ms.toFixed(0)}ms</small></p>`;

                    answerDiv.innerHTML = html;
                } else {
                    answerDiv.innerHTML = `<p style="color: red;">Error: ${data.error}</p>`;
                }
            } catch (error) {
                answerDiv.innerHTML = `<p style="color: red;">Error: ${error.message}</p>`;
            }
        }

        // Allow Enter key to submit
        document.getElementById('question').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') askQuestion();
        });
    </script>
</body>
</html>
```

---

## Best Practices

### 1. Caching Strategy

**Leverage caching for cost savings**:

```python
def ask_with_cache_awareness(question):
    """Check if answer is likely cached before asking."""
    # First request - will be cached
    result1 = ask_question(question)
    print(f"First request - Cached: {result1['metadata']['cached']}")
    print(f"Cost: ${result1['metadata']['cost']:.6f}")

    # Identical second request - returns from cache
    result2 = ask_question(question)
    print(f"Second request - Cached: {result2['metadata']['cached']}")
    print(f"Cost: ${result2['metadata']['cost']:.6f}")  # Will be 0.0

    # Slightly different question - new request
    result3 = ask_question(question + "?")
    print(f"Modified request - Cached: {result3['metadata']['cached']}")

# Example output:
# First request - Cached: False, Cost: $0.000261
# Second request - Cached: True, Cost: $0.000000
# Modified request - Cached: False, Cost: $0.000261
```

### 2. Error Handling

**Implement robust error handling**:

```python
def ask_with_retry(question, max_retries=3):
    """Ask question with retry logic."""
    for attempt in range(max_retries):
        try:
            response = requests.post(
                "http://localhost:8000/api/v1/ask",
                json={"question": question},
                timeout=30
            )

            if response.status_code == 429:  # Rate limit
                wait_time = 60 / 60  # 1 second
                logger.warning(f"Rate limited, waiting {wait_time}s...")
                time.sleep(wait_time)
                continue

            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                logger.warning(f"Timeout, retry {attempt + 1}/{max_retries}")
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                logger.error("Max retries reached")
                raise

        except requests.exceptions.HTTPError as e:
            if e.response.status_code >= 500:  # Server error
                if attempt < max_retries - 1:
                    logger.warning(f"Server error, retry {attempt + 1}/{max_retries}")
                    time.sleep(2 ** attempt)
                else:
                    raise
            else:  # Client error - don't retry
                raise
```

### 3. Cost Monitoring

**Track API usage and costs**:

```python
class CostTracker:
    """Track API costs over time."""

    def __init__(self):
        self.total_cost = 0.0
        self.total_questions = 0
        self.cache_hits = 0

    def record_query(self, result):
        """Record a query result."""
        self.total_questions += 1
        self.total_cost += result['metadata']['cost']

        if result['metadata']['cached']:
            self.cache_hits += 1

    def get_stats(self):
        """Get cost statistics."""
        cache_rate = (
            self.cache_hits / self.total_questions
            if self.total_questions > 0
            else 0
        )

        return {
            "total_questions": self.total_questions,
            "total_cost": self.total_cost,
            "average_cost": self.total_cost / self.total_questions if self.total_questions > 0 else 0,
            "cache_hit_rate": cache_rate,
            "cache_savings": cache_rate * self.total_cost
        }

# Usage
tracker = CostTracker()

questions = [
    "What is cancer?",
    "What are symptoms of breast cancer?",
    "What is chemotherapy?",
]

for question in questions:
    result = ask_question(question)
    tracker.record_query(result)

stats = tracker.get_stats()
print(f"Total questions: {stats['total_questions']}")
print(f"Total cost: ${stats['total_cost']:.4f}")
print(f"Average cost: ${stats['average_cost']:.6f}")
print(f"Cache hit rate: {stats['cache_hit_rate']:.1%}")
print(f"Estimated savings: ${stats['cache_savings']:.4f}")
```

---

## Common Use Cases

### 1. Patient Education Portal

```python
def patient_portal_query(patient_question, patient_cancer_type=None):
    """
    Handle patient questions in a portal interface.

    Returns formatted, patient-friendly response.
    """
    result = ask_question_with_filters(
        question=patient_question,
        cancer_type=patient_cancer_type,
        source="BC Cancer"  # Use trusted source
    )

    # Format for patient display
    return {
        "answer": result['answer'],
        "sources": [
            {
                "title": s['article_title'],
                "url": s['url'],
                "relevance": f"{s['similarity_score']*100:.0f}%"
            }
            for s in result['sources']
        ],
        "disclaimer": result['disclaimer']
    }
```

### 2. Healthcare Provider Tool

```python
def provider_query(clinical_question, cancer_type, min_confidence=0.7):
    """
    Handle provider queries requiring high-confidence answers.
    """
    result = ask_precise_question(
        question=clinical_question,
        cancer_type=cancer_type,
        source="BC Cancer",  # Clinical source
        min_similarity=min_confidence
    )

    # Include detailed source information
    return {
        "clinical_answer": result['answer'],
        "evidence": [
            {
                "source": s['article_title'],
                "section": s['section'],
                "excerpt": s['text_excerpt'],
                "confidence": s['similarity_score'],
                "url": s['url']
            }
            for s in result['sources']
        ],
        "evidence_quality": "high" if min_confidence >= 0.7 else "moderate"
    }
```

### 3. Research Assistant

```python
def research_query(topic, collect_all_sources=True):
    """
    Gather comprehensive information on a topic.
    """
    # Get maximum sources with minimal filtering
    result = ask_question_with_filters(
        question=topic,
        max_results=10,
        min_similarity=0.5  # Cast wider net
    )

    # Organize by source
    by_source = {}
    for s in result['sources']:
        source_name = s['source']
        if source_name not in by_source:
            by_source[source_name] = []
        by_source[source_name].append(s)

    return {
        "topic": topic,
        "summary": result['answer'],
        "sources_by_organization": by_source,
        "total_sources": len(result['sources'])
    }
```

---

## Performance Optimization

### 1. Connection Pooling

```python
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

def create_optimized_session():
    """Create session with connection pooling and retries."""
    session = requests.Session()

    # Retry strategy
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504]
    )

    # Connection pooling
    adapter = HTTPAdapter(
        pool_connections=10,
        pool_maxsize=20,
        max_retries=retry
    )

    session.mount('http://', adapter)
    session.mount('https://', adapter)

    return session

# Use throughout application
session = create_optimized_session()

def ask_optimized(question):
    response = session.post(
        "http://localhost:8000/api/v1/ask",
        json={"question": question}
    )
    return response.json()
```

### 2. Async Processing

```python
import asyncio
import aiohttp

async def ask_async(session, question):
    """Async question asking."""
    async with session.post(
        "http://localhost:8000/api/v1/ask",
        json={"question": question}
    ) as response:
        return await response.json()

async def ask_many_async(questions):
    """Ask multiple questions asynchronously."""
    async with aiohttp.ClientSession() as session:
        tasks = [ask_async(session, q) for q in questions]
        return await asyncio.gather(*tasks)

# Usage
questions = ["Question 1?", "Question 2?", "Question 3?"]
results = asyncio.run(ask_many_async(questions))
```

---

## Next Steps

- **Explore API Documentation**: [API.md](./API.md)
- **Set up development environment**: [DEVELOPER_GUIDE.md](./DEVELOPER_GUIDE.md)
- **Understand architecture**: [ARCHITECTURE.md](./ARCHITECTURE.md)
- **Try interactive docs**: `/docs` is only served when `api.debug: true` in `api/config/config.yaml` — disabled by default, including in production

---

**Last Updated**: 2024-01-15
**Version**: 2.0.0
