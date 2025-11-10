"""Main FastAPI application for Care-Beacon RAG system."""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import time

from fastapi import FastAPI, HTTPException, Request, status
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

# Create FastAPI app
app = FastAPI(
    title="Care-Beacon Medical RAG API",
    description="Retrieval-Augmented Generation API for cancer information from BC Cancer",
    version=API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
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


# Simple in-memory rate limiting (for production, use Redis-based rate limiter)
_rate_limit_cache: Dict[str, list] = {}
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_REQUESTS = api_config.get("rate_limit", {}).get("requests_per_minute", 60)


def check_rate_limit(client_ip: str) -> bool:
    """Check if client has exceeded rate limit.

    Args:
        client_ip: Client IP address

    Returns:
        True if within limit, False if exceeded
    """
    if not api_config.get("rate_limit", {}).get("enabled", True):
        return True

    current_time = time.time()

    # Clean old entries
    if client_ip in _rate_limit_cache:
        _rate_limit_cache[client_ip] = [
            timestamp for timestamp in _rate_limit_cache[client_ip]
            if current_time - timestamp < RATE_LIMIT_WINDOW
        ]
    else:
        _rate_limit_cache[client_ip] = []

    # Check limit
    if len(_rate_limit_cache[client_ip]) >= RATE_LIMIT_MAX_REQUESTS:
        return False

    # Add new request
    _rate_limit_cache[client_ip].append(current_time)
    return True


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
async def ask_question(request: Request, question_request: QuestionRequest):
    """Answer a medical question using RAG.

    Args:
        request: FastAPI request object
        question_request: Question request data

    Returns:
        Generated answer with citations

    Raises:
        HTTPException: If rate limit exceeded or processing fails
    """
    # Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Maximum {RATE_LIMIT_MAX_REQUESTS} requests per minute.",
        )

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

        # When using min_similarity filtering, increase max_results to return all qualifying sources
        # Otherwise, the hard limit of 5 would prevent users from seeing all relevant results
        max_results = question_request.max_results
        if question_request.min_similarity and question_request.min_similarity > 0:
            max_results = 50  # Fetch more results when filtering by similarity

        answer = generator.generate_answer(
            question=question_request.question,
            filters=filters if filters else None,
            max_results=max_results,
            min_similarity=question_request.min_similarity,
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate answer: {str(e)}",
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


@app.post("/api/v1/cache/clear", tags=["Administration"])
async def clear_cache():
    """Clear the Redis cache.

    Returns:
        Confirmation message

    Note:
        This endpoint should be protected with authentication in production
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


@app.post("/api/v1/stats/reset", tags=["Administration"])
async def reset_stats():
    """Reset usage statistics.

    Returns:
        Confirmation message

    Note:
        This endpoint should be protected with authentication in production
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


# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    print("=" * 70)
    print("Care-Beacon Medical RAG API")
    print("=" * 70)
    print(f"Version: {API_VERSION}")
    print(f"Environment: {'Development' if api_config.get('debug', False) else 'Production'}")
    print()

    # Pre-initialize generator
    generator = get_answer_generator()
    print(f" Answer generator initialized")
    print(f" Cache status: {'Enabled' if generator.cache.enabled else 'Disabled'}")
    print(f" Cache healthy: {generator.cache.is_healthy()}")
    print()
    print("API is ready to accept requests!")
    print("=" * 70)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    print("\nShutting down Care-Beacon API...")
    print(" Cleanup complete")
