"""Main FastAPI application for Care-Beacon RAG system."""

import os
import sys
from datetime import datetime
from typing import Dict, Any
from contextlib import asynccontextmanager
import time

from fastapi import FastAPI, HTTPException, Request, status, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

# Disable ChromaDB telemetry before importing our modules
os.environ["ANONYMIZED_TELEMETRY"] = "False"

# Filter ChromaDB warnings
class FilteredStderr:
    """Filter out ChromaDB telemetry warnings from stderr."""

    def __init__(self, original_stderr):
        self.original_stderr = original_stderr

    def write(self, message):
        if "telemetry" not in message.lower() and "capture()" not in message:
            self.original_stderr.write(message)

    def flush(self):
        self.original_stderr.flush()


sys.stderr = FilteredStderr(sys.stderr)

from src.generation.answer_generator import AnswerGenerator
from src.caching.redis_cache import RedisCache
from src.config_loader import get_config
from src.api.models import (
    QuestionRequest,
    QuestionResponse,
    CitationResponse,
    HealthResponse,
    StatsResponse,
    ErrorResponse,
)

# API Version
API_VERSION = "2.0.0"

# Load configuration
config = get_config()
api_config = config.get("api", {})

# Admin API key for protected endpoints
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")


async def require_admin_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    """Require a valid admin API key.

    Raises:
        HTTPException: 503 if no key is configured, 403 if the supplied key is wrong.
    """
    import hmac

    configured_key = ADMIN_API_KEY
    if not configured_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin endpoints disabled",
        )
    if not x_api_key or not hmac.compare_digest(x_api_key, configured_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )


# Lifespan context manager for startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan (startup and shutdown)."""
    # Startup
    print("=" * 70)
    print("Care-Beacon Medical RAG API")
    print("=" * 70)
    print(f"Version: {API_VERSION}")
    print(f"Environment: {'Development' if api_config.get('debug', False) else 'Production'}")
    print()

    # Pre-initialize generator
    generator = get_answer_generator()
    print(f" Answer generator initialized")
    print(f" Cache status: {'Enabled' if generator.cache.enabled else 'Disabled'}")
    print(f" Cache healthy: {generator.cache.is_healthy()}")
    print()
    print("API is ready to accept requests!")
    print("=" * 70)

    yield

    # Shutdown
    print("\nShutting down Care-Beacon API...")
    print(" Cleanup complete")


# Disable docs in production
_is_debug = api_config.get("debug", False)

# Create FastAPI app with lifespan
app = FastAPI(
    title="Care-Beacon Medical RAG API",
    description="Retrieval-Augmented Generation API for cancer information from BC Cancer",
    version=API_VERSION,
    docs_url="/docs" if _is_debug else None,
    redoc_url="/redoc" if _is_debug else None,
    openapi_url="/openapi.json" if _is_debug else None,
    lifespan=lifespan,
)

# CORS Configuration
cors_origins = api_config.get("cors_origins", ["http://localhost:3000"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,  # Must be False when using "*" for origins
    allow_methods=["*"],
    allow_headers=["*"],
)


# Initialize answer generator (lazy loaded on first request)
_answer_generator: AnswerGenerator | None = None


def get_answer_generator() -> AnswerGenerator:
    """Get or initialize the answer generator (singleton pattern)."""
    global _answer_generator
    if _answer_generator is None:
        _answer_generator = AnswerGenerator()
    return _answer_generator


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "ValidationError",
            "message": "Invalid request data",
            "detail": str(exc),
            "timestamp": datetime.now().isoformat(),
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTPException",
            "message": exc.detail,
            "timestamp": datetime.now().isoformat(),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    # Always log the full error to console for debugging
    import traceback
    from loguru import logger

    logger.error("=" * 70)
    logger.error("UNHANDLED EXCEPTION IN API")
    logger.error("=" * 70)
    logger.error(f"Exception type: {type(exc).__name__}")
    logger.error(f"Exception message: {str(exc)}")
    logger.error(f"Request: {request.method} {request.url}")
    logger.error("Full traceback:")
    logger.error(traceback.format_exc())
    logger.error("=" * 70)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": "An internal server error occurred",
            "detail": str(exc) if api_config.get("debug", False) else None,
            "timestamp": datetime.now().isoformat(),
        },
    )


# Endpoints
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Care-Beacon Medical RAG API",
        "version": API_VERSION,
        "description": "Retrieval-Augmented Generation API for cancer information",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "ask": "/api/v1/ask",
            "health": "/health",
            "stats": "/api/v1/stats",
        }
    }


@app.get("/health", response_model=HealthResponse, tags=["Monitoring"])
async def health_check():
    """Health check endpoint.

    Returns:
        Health status of API and dependent services
    """
    generator = get_answer_generator()

    # Check service health
    services = {
        "vector_db": True,  # Would need actual health check
        "redis_cache": generator.cache.is_healthy(),
        "llm_client": True,  # Would need actual health check
    }

    overall_status = "healthy" if all(services.values()) else "degraded"

    return HealthResponse(
        status=overall_status,
        version=API_VERSION,
        timestamp=datetime.now(),
        services=services,
    )


@app.post(
    "/api/v1/ask",
    response_model=QuestionResponse,
    tags=["Question Answering"],
    summary="Ask a medical question",
    description="Submit a question and receive an AI-generated answer with citations from BC Cancer materials",
)
async def ask_question(question_request: QuestionRequest):
    """Answer a medical question using RAG.

    Args:
        question_request: Question request data

    Returns:
        Generated answer with citations

    Raises:
        HTTPException: If processing fails
    """
    try:
        # Get generator
        generator = get_answer_generator()

        # Build filters
        filters = {}
        if question_request.cancer_type:
            filters["cancer_type"] = question_request.cancer_type
        if question_request.source:
            filters["source"] = question_request.source

        # Generate answer
        start_time = time.time()

        # Use the requested max_results directly
        # Re-ranking will automatically fetch more results (2x) for better quality
        max_results = question_request.max_results

        answer = generator.generate_answer(
            question=question_request.question,
            filters=filters if filters else None,
            max_results=max_results,
            min_similarity=question_request.min_similarity,
            include_full_text=question_request.include_full_text,
        )

        # Check if answer was cached
        cache_stats = generator.cache.get_stats()
        was_cached = cache_stats.get("cache_hits", 0) > 0

        # Convert citations
        sources = [
            CitationResponse(
                article_title=citation.article_title,
                section=citation.section,
                url=citation.url,
                paragraph_index=citation.paragraph_index,
                text_excerpt=citation.text_excerpt,
                similarity_score=citation.similarity_score,
                source=citation.source,
                full_text=citation.full_text,
            )
            for citation in answer.citations
        ]

        # Build response
        return QuestionResponse(
            question=answer.query,
            answer=answer.answer,
            sources=sources,
            disclaimer=answer.disclaimer,
            model=answer.model,
            metadata={
                "tokens_used": answer.tokens_used.get("total", 0),
                "cost": answer.cost,
                "generation_time_ms": answer.generation_time_ms,
                "cached": was_cached,
                "sources_count": len(answer.citations),
            },
        )

    except Exception as e:
        # Log the full error with traceback
        import traceback
        from loguru import logger

        logger.error("=" * 70)
        logger.error("ERROR IN /api/v1/ask ENDPOINT")
        logger.error("=" * 70)
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Exception message: {str(e)}")
        logger.error(f"Question: {question_request.question}")
        logger.error(f"min_similarity: {question_request.min_similarity}")
        logger.error("Full traceback:")
        logger.error(traceback.format_exc())
        logger.error("=" * 70)

        detail = "Failed to generate answer"
        if api_config.get("debug", False):
            detail += f": {str(e)}"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
        )


@app.get(
    "/api/v1/stats",
    response_model=StatsResponse,
    tags=["Monitoring"],
    summary="Get system statistics",
    description="Retrieve usage statistics including costs, cache performance, and token usage",
)
async def get_stats():
    """Get system statistics.

    Returns:
        System usage statistics
    """
    try:
        generator = get_answer_generator()
        stats = generator.get_stats()

        return StatsResponse(
            llm=stats["llm"],
            cache=stats["cache"],
            retrieval=stats["retrieval"],
            total_cost=stats["total_cost"],
            total_cost_saved=stats.get("total_cost_saved", 0.0),
            cost_reduction_percent=stats.get("cost_reduction_percent", 0.0),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve statistics: {str(e)}",
        )


@app.get("/api/v1/vector-db/stats", tags=["Monitoring"])
async def get_vector_db_stats():
    """Get vector database statistics.

    Returns:
        Vector database statistics including source breakdown
    """
    try:
        generator = get_answer_generator()

        # Check cache first
        cached_stats = generator.cache.get_vector_db_stats()
        if cached_stats is not None:
            return cached_stats

        # Cache miss - compute stats
        from src.storage.vector_db import create_vector_database

        vector_db = create_vector_database()

        # Get stats using the database's get_stats method
        stats = vector_db.get_stats()
        total_chunks = stats.get('total_chunks', 0)

        # Get source breakdown by scrolling through all points (Qdrant)
        sources = []
        unique_articles = set()
        source_stats = {}  # Track stats per source: {source_name: {articles: set(), chunks: count, text_bytes: int}}

        # Constants for storage calculation
        BYTES_PER_FLOAT32 = 4
        EMBEDDING_DIMENSIONS = stats.get('vector_size', 1536)
        METADATA_OVERHEAD_PER_CHUNK = 200  # Approximate bytes for metadata (article_id, section, etc.)

        try:
            # Scroll through all points to gather statistics
            offset = None
            batch_size = 10000  # Increased for better performance (fewer API calls)

            while True:
                scroll_result = vector_db.client.scroll(
                    collection_name=vector_db.collection_name,
                    limit=batch_size,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False
                )

                points, next_offset = scroll_result

                if not points:
                    break

                # Process this batch
                for point in points:
                    payload = point.payload
                    source = payload.get('source', 'Unknown')
                    article_id = payload.get('article_id', '')

                    # Track unique articles globally
                    if article_id:
                        unique_articles.add(article_id)

                    # Track per-source statistics
                    if source not in source_stats:
                        source_stats[source] = {
                            'articles': set(),
                            'chunks': 0
                        }

                    source_stats[source]['chunks'] += 1
                    if article_id:
                        source_stats[source]['articles'].add(article_id)

                # Check if we've reached the end
                if next_offset is None:
                    break

                offset = next_offset

            # Convert source_stats to the output format
            # Use average text size estimate to avoid expensive encoding calculation
            AVERAGE_TEXT_BYTES = 350  # Most medical chunks are 200-500 bytes

            for source_name, data in source_stats.items():
                # Calculate total storage size in MB
                text_bytes = data['chunks'] * AVERAGE_TEXT_BYTES  # Estimate instead of measuring
                embedding_bytes = data['chunks'] * EMBEDDING_DIMENSIONS * BYTES_PER_FLOAT32
                metadata_bytes = data['chunks'] * METADATA_OVERHEAD_PER_CHUNK
                total_bytes = text_bytes + embedding_bytes + metadata_bytes
                storage_mb = total_bytes / (1024 * 1024)  # Convert to MB

                sources.append({
                    "name": source_name,
                    "articles": len(data['articles']),
                    "chunks": data['chunks'],
                    "storage_mb": round(storage_mb, 2)  # Round to 2 decimal places
                })

            # Sort sources by name for consistent ordering
            sources.sort(key=lambda x: x['name'])

        except Exception as e:
            # If scrolling fails, fall back to basic stats
            logger.warning(f"Failed to get source breakdown: {e}")
            unique_articles = set()

        # Prepare the response
        result = {
            "total_documents": len(unique_articles) if unique_articles else stats.get('unique_articles_sample', 0),
            "total_chunks": total_chunks,
            "sources": sources,
            "collection_name": stats.get('collection_name', ''),
            "distance_metric": stats.get('distance_metric', ''),
            "vector_size": stats.get('vector_size', 0)
        }

        # Cache the computed stats
        generator.cache.set_vector_db_stats(result)

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve vector DB statistics: {str(e)}",
        )


@app.post(
    "/api/v1/cache/clear",
    tags=["Administration"],
    dependencies=[Depends(require_admin_api_key)],
)
async def clear_cache():
    """Clear the Redis cache.

    Returns:
        Confirmation message
    """
    try:
        generator = get_answer_generator()
        generator.cache.clear_all()

        return {
            "message": "Cache cleared successfully",
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear cache: {str(e)}",
        )


@app.post(
    "/api/v1/stats/reset",
    tags=["Administration"],
    dependencies=[Depends(require_admin_api_key)],
)
async def reset_stats():
    """Reset usage statistics.

    Returns:
        Confirmation message
    """
    try:
        generator = get_answer_generator()
        generator.llm_client.reset_stats()
        generator.cache.reset_stats()

        return {
            "message": "Statistics reset successfully",
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset statistics: {str(e)}",
        )
