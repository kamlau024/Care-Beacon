# Care-Beacon Medical RAG Pipeline

## Project Overview

A Retrieval-Augmented Generation (RAG) system designed to process medical journal articles and answer patient questions with accurate, cited references. The system will provide paragraph-level citations to ensure transparency and medical accuracy.

## Key Requirements

- **Input**: Pre-parsed markdown medical journal articles
- **Scale**: 100-10,000 articles across general medicine, specific specialties, and patient education
- **Citations**: Paragraph-level granularity with article references
- **Updates**: Real-time ingestion capability for new articles
- **Vector DB**: Self-hosted solution (Chroma recommended)
- **LLM**: API-based (Claude or OpenAI)
- **Query Volume**: ~1 query/second (~86,000 queries/day, ~2.6M queries/month)

## Architecture Overview

```
[Medical Articles (Markdown)]
    ↓
[Markdown Parser & Metadata Extractor]
    ↓ (Extract structure, sections, metadata)
[Document Processor]
    ↓ (Chunk by paragraph + preserve metadata)
[Embedding Generator]
    ↓ (OpenAI or Cohere embeddings)
[Vector Database (Chroma)] ← [Built-in Metadata Store]
    ↓
[Retrieval Engine]
    ↓ (Top-k relevant paragraphs with metadata filtering)
[LLM API (Claude/OpenAI)]
    ↓ (Prompt with retrieved context)
[Answer with Paragraph-Level Citations]
```

## Technology Stack Recommendations

### LLM Platform Options (API-Based)

1. **Claude 3.5 Sonnet (Anthropic)** - RECOMMENDED
   - **Pros**:
     - Excellent reasoning and instruction following for citations
     - Large context window (200K tokens) - can fit many retrieved paragraphs
     - Strong medical knowledge and nuanced understanding
     - Good at maintaining factual accuracy (important for medical content)
   - **Cost**: $3/million input tokens, $15/million output tokens
   - **Estimated monthly cost at 1 query/sec**:
     - Assuming ~2K input tokens (10 paragraphs + prompt), ~500 output tokens
     - ~2.6M queries/month × (2K × $3/M + 500 × $15/M) = ~$35,000/month
   - **Best for**: High-accuracy medical answers where citation precision is critical

2. **Claude 3 Haiku (Anthropic)** - COST-EFFECTIVE ALTERNATIVE
   - **Pros**: Much cheaper, still good quality, faster response times
   - **Cost**: $0.25/million input tokens, $1.25/million output tokens
   - **Estimated monthly cost**: ~$2,900/month (same assumptions)
   - **Cons**: Slightly lower reasoning capability than Sonnet
   - **Best for**: Budget-conscious deployment with acceptable accuracy trade-off

3. **GPT-4o (OpenAI)**
   - **Pros**: Strong general knowledge, good API ecosystem, 128K context
   - **Cost**: $2.50/million input tokens, $10/million output tokens
   - **Estimated monthly cost**: ~$26,000/month
   - **Cons**: Smaller context window, can be less reliable with strict citation formatting
   - **Best for**: Teams already invested in OpenAI ecosystem

4. **GPT-4o-mini (OpenAI)** - BUDGET OPTION
   - **Pros**: Very cost-effective, fast, decent quality
   - **Cost**: $0.15/million input tokens, $0.60/million output tokens
   - **Estimated monthly cost**: ~$1,560/month
   - **Cons**: Lower quality for complex medical reasoning
   - **Best for**: Initial testing or less critical queries

**Recommendation**: Start with **Claude 3.5 Sonnet** for quality validation, then test **Claude 3 Haiku** or **GPT-4o-mini** to see if cost savings are worth the trade-off. Consider implementing a hybrid approach where simple queries use cheaper models.

### Vector Database

**Chroma (RECOMMENDED for this project)**
- Persistent storage with built-in metadata filtering
- Easy to set up and use with Python
- Better for real-time ingestion and updates
- Built-in document store (no separate database needed)
- Excellent performance at 10K articles, 1 query/sec
- Handles concurrent reads efficiently
- Can scale to your volume without issues

**Performance Considerations at 1 query/sec:**
- Chroma can easily handle 1 query/sec on modest hardware
- Typical query latency: 50-200ms for vector search
- Consider running on dedicated server (2-4 CPU cores, 8GB RAM minimum)
- Add Redis cache layer for frequently asked questions to reduce costs:
  - Cache query results for 24 hours
  - Can reduce LLM API calls by 30-50% for common queries
  - Estimated savings: ~$10-17K/month on Claude Sonnet

### Embedding Model

**OpenAI text-embedding-3-small** - RECOMMENDED
- High quality semantic understanding for medical text
- 1536 dimensions, good retrieval performance
- **Cost**: $0.02 per million tokens
- **One-time indexing cost** (10K articles, avg 5K tokens each): ~$1
- **Query cost at 1 query/sec**:
  - Each query needs to embed the question (~50 tokens)
  - ~2.6M queries/month × 50 tokens = 130M tokens = **$2.60/month**
- **Total embedding cost**: Negligible compared to LLM costs

**OpenAI text-embedding-3-large** (higher quality alternative)
- 3072 dimensions, better retrieval accuracy
- **Cost**: $0.13 per million tokens
- **Monthly query cost**: ~$17/month (still negligible)
- Use if retrieval quality is critical

**Cohere embed-english-v3.0** (alternative)
- Optimized for semantic search
- $0.10 per million tokens
- Good for English medical text

**Note**: Avoid self-hosted embedding models at this volume - the cost savings are minimal compared to the operational complexity.

## Implementation Phases

### Phase 1: Foundation (Weeks 1-2)
- [ ] Set up project structure and dependencies
- [ ] Implement markdown parser with metadata extraction
- [ ] Create document preprocessing pipeline
- [ ] Build paragraph-level chunking system with section detection
- [ ] Set up Chroma vector database
- [ ] Implement embedding generation with OpenAI API
- [ ] Set up Redis cache for query results

### Phase 2: Core RAG (Weeks 3-4)
- [ ] Build retrieval engine with similarity search
- [ ] Implement metadata filtering (by specialty, date, article type)
- [ ] Create citation tracking system
- [ ] Develop LLM integration and prompt templates
- [ ] Build answer generation with citation formatting

### Phase 3: Real-time Ingestion (Week 5)
- [ ] Create article ingestion API/pipeline
- [ ] Implement duplicate detection
- [ ] Add incremental indexing
- [ ] Set up monitoring and logging

### Phase 4: Quality & Safety (Week 6)
- [ ] Implement answer validation
- [ ] Add medical disclaimer system
- [ ] Create relevance scoring
- [ ] Build evaluation framework
- [ ] User testing and refinement

## Key Components

### 1. Markdown Article Parser

```python
# Pseudo-structure
class MedicalArticleParser:
    def parse_markdown(self, markdown_content, metadata=None):
        """Extract structured content from pre-parsed markdown"""
        # Extract from markdown frontmatter or separate metadata file:
        - Article title (from # heading or metadata)
        - Authors (from metadata)
        - Publication date (from metadata)
        - Journal name (from metadata)
        - DOI/URL (from metadata)

        # Parse markdown structure:
        - Identify section headings (##, ###)
        - Extract paragraphs under each section
        - Preserve lists, tables (flatten to text)
        - Handle citations and references

        # Return structured document:
        {
            "metadata": {...},
            "sections": [
                {
                    "name": "Abstract",
                    "paragraphs": ["..."],
                    "level": 2
                },
                {
                    "name": "Introduction",
                    "paragraphs": ["..."],
                    "level": 2
                },
                ...
            ]
        }

    def identify_standard_sections(self, sections):
        """Normalize section names: Abstract, Introduction, Background,
        Methods, Results, Discussion, Conclusion, References"""
        # Handle variations: "Materials and Methods", "Study Design", etc.
```

**Markdown Format Expected:**
```markdown
---
title: "Treatment Approaches for Type 2 Diabetes"
authors: ["Smith, J.", "Doe, A."]
journal: "Journal of Medicine"
publication_date: "2024-03-15"
doi: "10.xxx/xxx"
specialty: "Endocrinology"
article_type: "Research"
---

## Abstract

Diabetes management has evolved significantly...

## Introduction

Type 2 diabetes mellitus affects millions...

## Methods

We conducted a randomized controlled trial...
```

### 2. Document Chunking Strategy

**Paragraph-level chunking** with metadata:
- Each paragraph becomes a chunk
- Preserve section context (which section the paragraph belongs to)
- Add metadata: article_id, paragraph_index, section_name, article_title, authors, journal, date
- Track character positions for precise citation

**Chunk metadata structure:**
```json
{
  "chunk_id": "article123_p5",
  "article_id": "article123",
  "article_title": "Treatment Approaches for Type 2 Diabetes",
  "authors": ["Smith, J.", "Doe, A."],
  "journal": "Medical Journal",
  "publication_date": "2024-03-15",
  "section": "Results",
  "paragraph_index": 5,
  "total_paragraphs": 45,
  "text": "The paragraph content...",
  "url": "https://...",
  "doi": "10.xxx/xxx"
}
```

### 3. Retrieval Strategy

**Hybrid approach:**
1. **Vector similarity search** (semantic matching)
   - Find top-k most relevant paragraphs (k=5-10)
   - Use cosine similarity

2. **Metadata filtering** (optional pre-filtering)
   - Filter by medical specialty if specified
   - Filter by publication date range
   - Filter by article type (research, review, patient education)

3. **Re-ranking** (optional)
   - Reorder by relevance score
   - Diversity to avoid redundant paragraphs from same article

### 4. Citation System

**Citation format for LLM prompt:**
```
[Article: "Treatment Approaches for Type 2 Diabetes", Smith et al., 2024, Medical Journal]
[Section: Results, Paragraph 5]
"The paragraph content..."
```

**Citation format in answer:**
```
The recommended first-line treatment for Type 2 Diabetes is metformin [1].

References:
[1] "Treatment Approaches for Type 2 Diabetes" - Smith, J. et al. (2024)
    Medical Journal, Results section, paragraph 5
    DOI: 10.xxx/xxx
```

### 5. LLM Prompt Template

```
You are a medical information assistant. Answer the patient's question using ONLY the provided medical journal excerpts. You must:

1. Provide accurate, clear answers appropriate for patients
2. Cite specific paragraphs using [1], [2], etc.
3. If the excerpts don't contain enough information to answer confidently, say so
4. Add appropriate medical disclaimers
5. Use accessible language while maintaining medical accuracy

RETRIEVED EXCERPTS:
{retrieved_paragraphs_with_metadata}

PATIENT QUESTION:
{user_question}

REQUIREMENTS:
- Only use information from the excerpts above
- Cite every claim with [number] references
- List all references at the end with full article details and paragraph numbers
- If information is insufficient or unclear, state this explicitly
- Include disclaimer: "This information is for educational purposes only. Please consult with a healthcare provider for medical advice."

ANSWER:
```

### 6. Real-time Ingestion Pipeline

```python
# Pseudo-structure
class ArticleIngestionPipeline:
    def ingest_article(self, markdown_file_path):
        """Process new article in real-time"""
        1. Read markdown file
        2. Parse markdown → structured article with metadata
        3. Check for duplicates (by DOI, title hash)
        4. Chunk into paragraphs with section context
        5. Generate embeddings (batch API calls for efficiency)
        6. Store chunks in Chroma with metadata
        7. Invalidate related cache entries
        8. Log ingestion event

    def update_article(self, article_id):
        """Update existing article"""
        1. Query Chroma for all chunks with article_id
        2. Delete old chunks
        3. Re-process markdown file
        4. Re-index with new chunks
        5. Clear cache entries for this article

    def batch_ingest(self, markdown_directory):
        """Initial bulk ingestion of article corpus"""
        1. Scan directory for all .md files
        2. Process in parallel (10-20 threads)
        3. Batch embedding generation (100 chunks at a time)
        4. Bulk insert into Chroma
        5. Progress tracking and error handling
```

## Safety and Compliance Considerations

### Medical Accuracy
- **Source verification**: Only ingest from reputable medical journals
- **Date awareness**: Include publication dates in citations for medical currency
- **Confidence thresholds**: Don't answer if confidence is below threshold
- **Contradiction detection**: Flag if retrieved paragraphs contradict each other

### Disclaimers
Always include:
- "This information is for educational purposes only"
- "Not a substitute for professional medical advice"
- "Consult healthcare provider for diagnosis and treatment"

### Privacy
- No storage of patient-specific information in queries
- Anonymize logs if storing for improvement
- HIPAA compliance if handling any protected health information

### Quality Control
- Regular audits of answers for accuracy
- Feedback mechanism for incorrect information
- Version tracking of article corpus
- Monitor for hallucinations (claims not in source material)

## Evaluation and Testing

### Metrics to Track

1. **Retrieval Quality**
   - Precision@k: Are retrieved paragraphs relevant?
   - Recall: Are all relevant paragraphs retrieved?
   - MRR (Mean Reciprocal Rank): Position of first relevant result

2. **Answer Quality**
   - Citation accuracy: Are all claims cited?
   - Faithfulness: Does answer match source content?
   - Completeness: Does answer address the question?
   - Clarity: Is answer understandable to patients?

3. **System Performance**
   - Query latency (target: < 5 seconds)
   - Ingestion speed (articles per minute)
   - Vector DB size and query performance

### Test Set Creation
- Curate 50-100 common patient questions across medical domains
- Have medical professionals create ground truth answers with citations
- Evaluate system outputs against ground truth
- Iterate on prompts and retrieval parameters

## Project Structure

```
care-beacon/
├── src/
│   ├── ingestion/
│   │   ├── markdown_parser.py         # Parse markdown with frontmatter
│   │   ├── document_processor.py      # Section detection, normalization
│   │   └── ingestion_pipeline.py      # End-to-end ingestion orchestration
│   ├── embeddings/
│   │   ├── embedding_generator.py     # OpenAI embeddings API wrapper
│   │   └── chunking.py                # Paragraph-level chunking logic
│   ├── storage/
│   │   ├── vector_db.py               # Chroma wrapper with metadata filtering
│   │   ├── cache.py                   # Redis cache for query results
│   │   └── models.py                  # Data models for articles, chunks
│   ├── retrieval/
│   │   ├── retriever.py               # Vector search + metadata filtering
│   │   └── reranker.py                # Optional re-ranking logic
│   ├── generation/
│   │   ├── llm_client.py              # Claude/OpenAI API client
│   │   ├── prompt_templates.py        # Prompt engineering for medical Q&A
│   │   └── citation_formatter.py      # Format paragraph-level citations
│   └── api/
│       ├── query_endpoint.py          # POST /query endpoint
│       ├── ingestion_endpoint.py      # POST /ingest endpoint
│       └── health_check.py            # System health and metrics
├── tests/
│   ├── test_parser.py
│   ├── test_chunking.py
│   ├── test_retrieval.py
│   ├── test_generation.py
│   ├── test_citation.py
│   └── test_end_to_end.py
├── data/
│   ├── markdown_articles/             # Source markdown files
│   ├── vector_db/                     # Chroma persistent storage
│   └── cache/                         # Redis dump (if using persistence)
├── evaluation/
│   ├── test_questions.json            # Curated test questions
│   ├── ground_truth_answers.json      # Human-verified answers
│   ├── evaluation_scripts.py          # Automated evaluation
│   └── results/                       # Evaluation results and metrics
├── notebooks/
│   ├── data_exploration.ipynb         # Explore article corpus
│   ├── retrieval_tuning.ipynb         # Tune retrieval parameters
│   └── evaluation_analysis.ipynb      # Analyze quality metrics
├── config/
│   ├── config.yaml                    # System configuration
│   ├── prompts.yaml                   # LLM prompt templates
│   └── api_keys.env                   # API keys (not in git)
├── docs/
│   ├── api_documentation.md           # API endpoint docs
│   └── deployment.md                  # Deployment guide
├── requirements.txt
├── README.md
├── Claude.md (this file)
└── .env.example                       # Example environment variables
```

## Next Steps

1. ✅ **LLM Platform**: Use API-based (Claude or OpenAI)
2. ✅ **Input Format**: Parsed markdown articles
3. ✅ **Query Volume**: 1 query/second (~86K/day)
4. ✅ **Vector DB**: Chroma (self-hosted)
5. **TO DO: Examine sample markdown files** - Review structure and metadata format
6. **TO DO: Set up development environment**:
   - Python 3.10+
   - Install Chroma, Redis, OpenAI/Anthropic SDKs
   - Configure API keys
7. **TO DO: Initial data ingestion** - Process first batch of markdown articles
8. **TO DO: Build MVP** - Implement phases 1-2 (foundation + core RAG)
9. **TO DO: Evaluate quality** - Test retrieval and generation with sample queries
10. **TO DO: Add caching layer** - Implement Redis to reduce API costs
11. **TO DO: Production hardening** - Add monitoring, error handling, rate limiting

## Questions to Address Before Production

- [x] LLM platform choice (API-based)
- [x] Input format (markdown)
- [x] Query volume (1 query/sec)
- [ ] **Budget for LLM API costs**: Can you afford $35K/month (Sonnet) or prefer $2.9K/month (Haiku)?
- [ ] **End users**: Patients directly, or medical staff answering patient questions?
- [ ] **Medical specialties to prioritize first**: Which specialties in your markdown corpus?
- [ ] **Markdown structure**: Do articles have YAML frontmatter? What metadata is available?
- [ ] **Medical review process**: How will answers be validated before going to patients?
- [ ] **Legal/compliance**: HIPAA requirements? Medical disclaimers? Jurisdiction-specific rules?
- [ ] **Deployment environment**: Cloud (AWS/GCP/Azure) or on-premises?
- [ ] **Monitoring and observability**: What metrics and alerting do you need?

## Cost Summary (1 query/second, ~2.6M queries/month)

### Option 1: Claude 3.5 Sonnet (Premium Quality)
- **LLM API**: ~$35,000/month
- **Embeddings**: ~$3/month
- **Infrastructure** (Chroma + Redis on dedicated server): ~$200-500/month
- **Total**: **~$35,500/month** (~$426K/year)
- **With 40% cache hit rate**: ~$21,500/month (~$258K/year)

### Option 2: Claude 3 Haiku (Balanced)
- **LLM API**: ~$2,900/month
- **Embeddings**: ~$3/month
- **Infrastructure**: ~$200-500/month
- **Total**: **~$3,400/month** (~$41K/year)
- **With 40% cache hit rate**: ~$2,000/month (~$24K/year)

### Option 3: GPT-4o-mini (Budget)
- **LLM API**: ~$1,560/month
- **Embeddings**: ~$3/month
- **Infrastructure**: ~$200-500/month
- **Total**: **~$2,100/month** (~$25K/year)
- **With 40% cache hit rate**: ~$1,400/month (~$17K/year)

**Recommendation**: Start with **GPT-4o-mini** (most cost-effective at ~$1,560/month) for MVP. If you need higher quality, upgrade to GPT-4o (~$6,500/month) or Claude Haiku (~$2,900/month). GPT-4o-mini offers excellent value and uses the same OpenAI API as embeddings (simpler integration).

---

**Document Version**: 2.0
**Last Updated**: 2025-11-07
**Project Owner**: Care-Beacon Team
