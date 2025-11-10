"""API request and response models."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class QuestionRequest(BaseModel):
    """Request model for question answering."""

    question: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="User's medical question",
        example="What are the symptoms of breast cancer?"
    )
    cancer_type: Optional[str] = Field(
        None,
        description="Filter by specific cancer type",
        example="Breast Cancer"
    )
    source: Optional[str] = Field(
        None,
        description="Filter by information source",
        example="BC Cancer"
    )
    max_results: Optional[int] = Field(
        5,
        ge=1,
        le=10,
        description="Maximum number of source chunks to use"
    )
    min_similarity: Optional[float] = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score (0-1) for sources to be included"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "question": "What are the symptoms of breast cancer?",
                "cancer_type": "Breast Cancer",
                "source": "BC Cancer",
                "max_results": 5
            }
        }


class CitationResponse(BaseModel):
    """Citation/source reference in response."""

    article_title: str = Field(..., description="Title of source article")
    section: str = Field(..., description="Section within article")
    url: str = Field(..., description="URL to source article")
    paragraph_index: int = Field(..., description="Paragraph number (0-indexed)")
    text_excerpt: str = Field(..., description="Excerpt from source text")
    similarity_score: float = Field(..., description="Similarity/confidence score (0-1)")
    source: str = Field(..., description="Information source (e.g., BC Cancer, Canadian Cancer Society)")

    class Config:
        json_schema_extra = {
            "example": {
                "article_title": "Breast Cancer",
                "section": "Symptoms",
                "url": "https://www.bccancer.bc.ca/health-info/types-of-cancer/breast",
                "paragraph_index": 0,
                "text_excerpt": "Common symptoms include lumps in the breast...",
                "similarity_score": 0.89
            }
        }


class QuestionResponse(BaseModel):
    """Response model for question answering."""

    question: str = Field(..., description="Original question")
    answer: str = Field(..., description="Generated answer")
    sources: List[CitationResponse] = Field(
        default_factory=list,
        description="Source citations"
    )
    disclaimer: Optional[str] = Field(
        None,
        description="Medical disclaimer"
    )
    model: str = Field(..., description="LLM model used")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "question": "What are the symptoms of breast cancer?",
                "answer": "Common symptoms of breast cancer include lumps in the breast, changes in breast shape or size, and skin changes. [Source: Breast Cancer - Symptoms]",
                "sources": [
                    {
                        "article_title": "Breast Cancer",
                        "section": "Symptoms",
                        "url": "https://www.bccancer.bc.ca/health-info/types-of-cancer/breast",
                        "paragraph_index": 0,
                        "text_excerpt": "Common symptoms include lumps..."
                    }
                ],
                "disclaimer": "This information is for educational purposes only...",
                "model": "gpt-4o-mini",
                "metadata": {
                    "tokens_used": 200,
                    "cost": 0.0002,
                    "generation_time_ms": 500,
                    "cached": False
                }
            }
        }


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    timestamp: datetime = Field(..., description="Current server time")
    services: Dict[str, bool] = Field(
        default_factory=dict,
        description="Status of dependent services"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "version": "2.0.0",
                "timestamp": "2024-01-15T10:30:00Z",
                "services": {
                    "vector_db": True,
                    "redis_cache": True,
                    "llm_client": True
                }
            }
        }


class StatsResponse(BaseModel):
    """System statistics response."""

    llm: Dict[str, Any] = Field(..., description="LLM usage statistics")
    cache: Dict[str, Any] = Field(..., description="Cache statistics")
    retrieval: Dict[str, Any] = Field(..., description="Retrieval statistics")
    total_cost: float = Field(..., description="Total cost (USD)")
    total_cost_saved: float = Field(..., description="Cost saved by cache (USD)")
    cost_reduction_percent: float = Field(..., description="Cost reduction percentage")

    class Config:
        json_schema_extra = {
            "example": {
                "llm": {
                    "total_calls": 100,
                    "total_tokens": 50000,
                    "total_cost": 0.05
                },
                "cache": {
                    "total_queries": 200,
                    "cache_hits": 100,
                    "hit_rate": 0.5
                },
                "retrieval": {
                    "total_cost": 0.001
                },
                "total_cost": 0.051,
                "total_cost_saved": 0.025,
                "cost_reduction_percent": 32.9
            }
        }


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "error": "ValidationError",
                "message": "Question must be between 3 and 500 characters",
                "detail": "Field: question, Value length: 2",
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }
