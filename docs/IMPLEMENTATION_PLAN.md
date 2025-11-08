# Care-Beacon RAG Implementation Plan

## Data Assessment

### Current Data Structure ✅
- **Source**: BC Cancer (bccancer.bc.ca) - reputable medical source
- **Format**: 94 markdown files with YAML frontmatter
- **Location**: `scraped_data/articles/`
- **Content Type**: Patient education materials on various cancer types
- **Structure**:
  ```yaml
  ---
  title: "Cancer Type"
  url: https://www.bccancer.bc.ca/...
  date_scraped: 2025-11-07T...
  breadcrumbs: ["Health Info", "Types Of Cancer", "Specific Cancer"]
  images: [...]
  ---
  # Main content with headers and sections
  ```

### Data Quality Assessment ✅
- ✅ **Good**: Pre-parsed markdown (no HTML parsing needed)
- ✅ **Good**: Consistent YAML frontmatter structure
- ✅ **Good**: Clear hierarchical organization (breadcrumbs)
- ✅ **Good**: Patient-focused language (ideal for patient Q&A)
- ✅ **Good**: Comprehensive coverage of cancer types
- ⚠️ **Note**: Not research articles, but authoritative patient education
- ⚠️ **Note**: Single source (BC Cancer) - consider adding more sources later

### Recommended Metadata Enrichment
For each article, we'll extract/add:
- `article_id`: Unique identifier (from filename or title slug)
- `cancer_type`: Primary cancer type (from breadcrumbs)
- `specialty`: Medical specialty (Oncology subcategories)
- `source`: "BC Cancer"
- `last_updated`: Extract from content if available
- `article_category`: "patient_education"

---

## Phase 1: Foundation (Weeks 1-2)

### Checkpoint 1.1: Project Setup ⬜
**Goal**: Set up development environment and project structure

**Tasks**:
- [ ] Create project directory structure
- [ ] Set up Python virtual environment (Python 3.10+)
- [ ] Create requirements.txt with initial dependencies
- [ ] Install core dependencies
- [ ] Set up configuration management (config.yaml)
- [ ] Create .env.example for API keys

**Files to Create**:
- `requirements.txt`
- `config/config.yaml`
- `.env.example`
- `src/` directory structure

**Testing**:
- Verify Python environment activated
- All packages install without errors
- Configuration file loads correctly

**Time Estimate**: 2-3 hours

---

### Checkpoint 1.2: Markdown Parser ⬜
**Goal**: Parse markdown files and extract structured content

**Tasks**:
- [ ] Create `src/ingestion/markdown_parser.py`
- [ ] Implement YAML frontmatter parsing (using python-frontmatter)
- [ ] Extract markdown sections by headers (##, ###)
- [ ] Extract paragraphs under each section
- [ ] Handle edge cases (nested lists, tables, code blocks)
- [ ] Create data models for articles and sections

**Files to Create**:
- `src/ingestion/markdown_parser.py`
- `src/storage/models.py`
- `tests/test_parser.py`

**Testing**:
- Test on 3-5 sample articles with varying structures
- Verify frontmatter extraction
- Verify section detection
- Verify paragraph extraction

**Success Criteria**:
```python
# Should be able to do:
parser = MarkdownParser()
article = parser.parse_file("scraped_data/articles/.../breast-cancer.md")
print(article.title)  # "Breast Cancer"
print(article.url)  # "https://..."
print(len(article.sections))  # Number of sections
print(article.sections[0].name)  # "Diagnosis & Staging"
print(len(article.sections[0].paragraphs))  # Number of paragraphs
```

**Time Estimate**: 4-6 hours

---

### Checkpoint 1.3: Document Processing & Chunking ⬜
**Goal**: Convert parsed articles into chunks suitable for embedding

**Tasks**:
- [ ] Create `src/embeddings/chunking.py`
- [ ] Implement paragraph-level chunking
- [ ] Generate unique chunk IDs (article_id + paragraph_index)
- [ ] Preserve metadata with each chunk
- [ ] Handle section context (track which section each paragraph belongs to)
- [ ] Create chunk data model

**Files to Create**:
- `src/embeddings/chunking.py`
- `tests/test_chunking.py`

**Chunk Structure**:
```python
{
    "chunk_id": "breast-cancer_diagnosis-staging_p3",
    "article_id": "breast-cancer",
    "article_title": "Breast Cancer",
    "url": "https://...",
    "breadcrumbs": ["Health Info", "Types Of Cancer", "Breast Cancer"],
    "cancer_type": "Breast Cancer",
    "source": "BC Cancer",
    "date_scraped": "2025-11-07",
    "section": "Diagnosis & Staging",
    "paragraph_index": 3,
    "text": "The earlier a breast cancer is found...",
}
```

**Testing**:
- Process breast-cancer.md and verify chunk count
- Verify metadata preservation
- Verify section assignment
- Test on articles with different structures

**Success Criteria**:
- All 94 articles can be chunked without errors
- Each chunk has complete metadata
- Chunks are appropriately sized (50-500 words per paragraph)

**Time Estimate**: 3-4 hours

---

### Checkpoint 1.4: Embedding Generation ⬜
**Goal**: Generate embeddings using OpenAI API

**Tasks**:
- [ ] Set up OpenAI API credentials
- [ ] Create `src/embeddings/embedding_generator.py`
- [ ] Implement single text embedding
- [ ] Implement batch embedding (process multiple chunks efficiently)
- [ ] Add error handling and retry logic
- [ ] Add rate limiting to stay within API limits
- [ ] Log embedding costs

**Files to Create**:
- `src/embeddings/embedding_generator.py`
- `tests/test_embeddings.py`

**API Setup**:
- Create OpenAI account if needed
- Generate API key
- Add to .env: `OPENAI_API_KEY=sk-...`

**Testing**:
- Test single embedding generation
- Test batch embedding (10 chunks)
- Verify embedding dimensions (1536 for text-embedding-3-small)
- Test error handling (invalid API key, rate limits)

**Success Criteria**:
```python
generator = EmbeddingGenerator(api_key=os.getenv("OPENAI_API_KEY"))
embedding = generator.embed_text("Test medical text")
assert len(embedding) == 1536

chunks = [{"text": "..."}, {"text": "..."}, ...]
embeddings = generator.embed_batch(chunks)
assert len(embeddings) == len(chunks)
```

**Time Estimate**: 3-4 hours

---

### Checkpoint 1.5: Vector Database Setup ⬜
**Goal**: Set up Chroma database and store embeddings

**Tasks**:
- [ ] Install and configure Chroma
- [ ] Create `src/storage/vector_db.py`
- [ ] Initialize Chroma collection with proper configuration
- [ ] Implement chunk insertion with embeddings
- [ ] Implement metadata filtering support
- [ ] Implement similarity search
- [ ] Set up persistent storage location

**Files to Create**:
- `src/storage/vector_db.py`
- `tests/test_vector_db.py`

**Chroma Configuration**:
- Collection name: "care-beacon-medical"
- Embedding function: Manual (we'll provide embeddings)
- Metadata fields: article_id, cancer_type, section, etc.
- Distance metric: Cosine similarity

**Testing**:
- Insert 10 test chunks with embeddings
- Perform similarity search
- Test metadata filtering
- Verify persistence (restart and reload)

**Success Criteria**:
```python
db = VectorDatabase()
db.add_chunks(chunks, embeddings)
results = db.search("breast cancer symptoms", k=5)
assert len(results) == 5
assert "text" in results[0]
assert "metadata" in results[0]
```

**Time Estimate**: 4-5 hours

---

### Checkpoint 1.6: Complete Data Ingestion ⬜
**Goal**: Process all 94 articles and load into vector database

**Tasks**:
- [ ] Create `src/ingestion/ingestion_pipeline.py`
- [ ] Implement end-to-end ingestion workflow
- [ ] Add progress tracking (tqdm progress bar)
- [ ] Add error handling and logging
- [ ] Process all 94 markdown files
- [ ] Generate embeddings for all chunks
- [ ] Store in Chroma database
- [ ] Generate ingestion report (statistics)

**Files to Create**:
- `src/ingestion/ingestion_pipeline.py`
- `scripts/ingest_all_articles.py`

**Workflow**:
1. Scan `scraped_data/articles/` for all .md files
2. Parse each file
3. Chunk into paragraphs
4. Generate embeddings (batch process)
5. Insert into Chroma
6. Log progress and errors

**Testing**:
- Run on 5 test articles first
- Then run on all 94 articles
- Verify no errors
- Check Chroma database size
- Query a few test questions

**Success Criteria**:
- All 94 articles processed successfully
- Estimated 2,000-5,000 chunks total in database
- Database responds to queries
- Ingestion report shows:
  - Total articles processed
  - Total chunks created
  - Total embedding API cost (~$1-2)
  - Processing time

**Time Estimate**: 3-4 hours

---

### Checkpoint 1.7: Redis Cache Setup ⬜
**Goal**: Set up Redis for caching query results

**Tasks**:
- [ ] Install Redis (local or Docker)
- [ ] Create `src/storage/cache.py`
- [ ] Implement cache key generation (hash of query + parameters)
- [ ] Implement cache get/set operations
- [ ] Add TTL configuration (24 hours default)
- [ ] Add cache statistics tracking

**Files to Create**:
- `src/storage/cache.py`
- `tests/test_cache.py`
- `docker-compose.yml` (optional, for Redis)

**Redis Setup**:
- Option 1: Install Redis locally (`brew install redis` on Mac)
- Option 2: Use Docker: `docker run -d -p 6379:6379 redis:alpine`

**Testing**:
- Test cache set and get
- Test cache expiration
- Test cache key collisions
- Test cache miss scenario

**Success Criteria**:
```python
cache = Cache()
cache.set("test_query", {"answer": "...", "sources": [...]})
result = cache.get("test_query")
assert result is not None
```

**Time Estimate**: 2-3 hours

---

## Phase 1 Summary

**Total Estimated Time**: 21-29 hours (~3-4 working days)

**Deliverables**:
- ✅ Working markdown parser
- ✅ Chunking system with metadata
- ✅ Embedding generation with OpenAI
- ✅ Chroma vector database with all articles indexed
- ✅ Redis cache infrastructure
- ✅ Complete test suite for Phase 1 components

**At End of Phase 1, You Will Have**:
- ~94 articles processed into 2,000-5,000 chunks
- All chunks embedded and stored in Chroma
- Ability to perform similarity search on medical content
- Cache infrastructure ready for query optimization
- Foundation ready for Phase 2 (LLM integration)

---

## Phase 2: Core RAG (Weeks 3-4)

### Checkpoint 2.1: Retrieval Engine ⬜
**Goal**: Build robust retrieval system with metadata filtering

**Tasks**:
- [ ] Create `src/retrieval/retriever.py`
- [ ] Implement basic similarity search
- [ ] Add metadata filtering (by cancer type, section, etc.)
- [ ] Implement result ranking
- [ ] Add diversity filtering (avoid too many chunks from same article)
- [ ] Configure optimal k value (number of results)

**Time Estimate**: 4-5 hours

---

### Checkpoint 2.2: LLM Client Integration ⬜
**Goal**: Integrate Claude or OpenAI API for answer generation

**Tasks**:
- [ ] Choose LLM (Claude 3.5 Sonnet, Haiku, or GPT-4o)
- [ ] Create `src/generation/llm_client.py`
- [ ] Implement API client with retry logic
- [ ] Add token counting and cost tracking
- [ ] Test basic prompt/response

**Time Estimate**: 3-4 hours

---

### Checkpoint 2.3: Prompt Engineering ⬜
**Goal**: Design prompts for accurate, cited medical answers

**Tasks**:
- [ ] Create `src/generation/prompt_templates.py`
- [ ] Design system prompt for medical Q&A
- [ ] Design user prompt with retrieved context
- [ ] Add citation requirements
- [ ] Add disclaimer requirements
- [ ] Test and iterate on prompt quality

**Time Estimate**: 4-6 hours

---

### Checkpoint 2.4: Citation Formatting ⬜
**Goal**: Format paragraph-level citations properly

**Tasks**:
- [ ] Create `src/generation/citation_formatter.py`
- [ ] Parse LLM response for citations
- [ ] Map citation numbers to source chunks
- [ ] Format reference list with article details
- [ ] Handle missing or incorrect citations

**Time Estimate**: 3-4 hours

---

### Checkpoint 2.5: End-to-End Query Pipeline ⬜
**Goal**: Complete query flow from question to cited answer

**Tasks**:
- [ ] Create `src/api/query_pipeline.py`
- [ ] Integrate retrieval + LLM + citations
- [ ] Add cache layer (check cache first, then query)
- [ ] Add error handling
- [ ] Add response time tracking
- [ ] Test with sample questions

**Time Estimate**: 4-5 hours

---

### Checkpoint 2.6: API Endpoints ⬜
**Goal**: Create REST API for querying the system

**Tasks**:
- [ ] Set up FastAPI or Flask
- [ ] Create POST /query endpoint
- [ ] Add request validation
- [ ] Add response formatting
- [ ] Add health check endpoint
- [ ] Add metrics endpoint
- [ ] Create API documentation

**Time Estimate**: 4-5 hours

---

### Checkpoint 2.7: Testing & Evaluation ⬜
**Goal**: Test system with real medical questions

**Tasks**:
- [ ] Create test question set (20-30 questions)
- [ ] Test each question manually
- [ ] Evaluate answer quality
- [ ] Check citation accuracy
- [ ] Measure response times
- [ ] Calculate costs per query
- [ ] Iterate on prompts and parameters

**Time Estimate**: 6-8 hours

---

## Phase 2 Summary

**Total Estimated Time**: 28-37 hours (~5-6 working days)

**Deliverables**:
- ✅ Complete RAG pipeline
- ✅ LLM integration with citations
- ✅ REST API endpoints
- ✅ Tested with medical questions
- ✅ Performance metrics

---

## Quick Start: Running Each Checkpoint

### Before Starting
1. Create conda environment: `conda create -n care-beacon python=3.10 -y`
2. Activate: `conda activate care-beacon`
3. Install dependencies: `pip install -r requirements.txt`

### Checkpoint Commands (will be updated as we build)
```bash
# 1.2: Test parser
python -m pytest tests/test_parser.py -v

# 1.3: Test chunking
python -m pytest tests/test_chunking.py -v

# 1.4: Test embeddings
python -m pytest tests/test_embeddings.py -v

# 1.5: Test vector database
python -m pytest tests/test_vector_db.py -v

# 1.6: Run full ingestion
python scripts/ingest_all_articles.py

# 2.7: Test query
python scripts/test_query.py "What are the symptoms of breast cancer?"
```

---

## Next Immediate Steps

1. **Checkpoint 1.1**: Set up project structure
2. **Review and approve**: This implementation plan
3. **Get API keys**: OpenAI API key for embeddings
4. **Decide on LLM**: Which model for Phase 2? (Haiku recommended to start)

---

**Document Version**: 1.0
**Created**: 2025-11-07
**Last Updated**: 2025-11-07
