"""Answer generator combining retrieval and LLM generation."""

import yaml
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

from src.retrieval.retrieval_engine import RetrievalEngine
from src.retrieval.models import Query, RetrievedContext
from src.generation.llm_client import LLMClient
from src.generation.models import GeneratedAnswer, Citation, GenerationConfig
from src.caching.redis_cache import RedisCache
from src.config_loader import get_config


class AnswerGenerator:
    """Generate answers to medical questions using RAG.

    This class coordinates:
    1. Retrieval of relevant context from vector database
    2. Prompt construction with context
    3. LLM generation of answers
    4. Citation formatting
    5. Cost tracking
    """

    def __init__(
        self,
        retrieval_engine: Optional[RetrievalEngine] = None,
        llm_client: Optional[LLMClient] = None,
        config: Optional[GenerationConfig] = None,
        cache: Optional[RedisCache] = None,
    ):
        """Initialize answer generator.

        Args:
            retrieval_engine: Optional RetrievalEngine instance
            llm_client: Optional LLMClient instance
            config: Optional generation configuration
            cache: Optional RedisCache instance
        """
        self.retrieval_engine = retrieval_engine or RetrievalEngine()
        self.llm_client = llm_client or LLMClient()
        self.config = config or self._load_config()
        self.cache = cache or RedisCache()

        # Load prompts
        self.prompts = self._load_prompts()

    def _load_config(self) -> GenerationConfig:
        """Load generation configuration.

        Returns:
            GenerationConfig instance
        """
        config = get_config()
        llm_config = config.get("llm", {})
        prompt_config = config.get("prompts", {})
        safety_config = config.get("safety", {})

        return GenerationConfig(
            model=llm_config.get("model", "gpt-4o-mini"),
            max_tokens=llm_config.get("max_tokens", 1000),
            temperature=llm_config.get("temperature", 0.1),
            max_context_chunks=prompt_config.get("max_context_tokens", 6000) // 200,  # Rough estimate
            require_citations=prompt_config.get("require_citations", True),
            include_disclaimer=safety_config.get("add_disclaimers", True),
            disclaimer_text=safety_config.get(
                "disclaimer_text",
                "This information is for educational purposes only."
            ),
            max_retries=llm_config.get("max_retries", 3),
            timeout=llm_config.get("timeout", 30),
        )

    def _load_prompts(self) -> Dict[str, str]:
        """Load prompt templates from config file.

        Returns:
            Dictionary of prompt templates
        """
        prompts_path = Path("config/prompts.yaml")

        if not prompts_path.exists():
            # Return default prompts if file doesn't exist
            return {
                "system_prompt": "You are a helpful medical information assistant.",
                "qa_prompt_template": "Context:\n{context}\n\nQuestion: {question}\n\nAnswer:",
            }

        with open(prompts_path, "r") as f:
            return yaml.safe_load(f)

    def _format_context(self, context: RetrievedContext) -> str:
        """Format retrieved context for LLM prompt.

        Args:
            context: Retrieved context with chunks

        Returns:
            Formatted context string
        """
        context_parts = []

        for i, result in enumerate(context.results[:self.config.max_context_chunks], 1):
            chunk = result.chunk

            # Format each source
            source_text = (
                f"[Source {i}: {chunk.article_title} - {chunk.section}]\n"
                f"{chunk.text}\n"
            )
            context_parts.append(source_text)

        return "\n".join(context_parts)

    def _extract_citations(self, context: RetrievedContext) -> List[Citation]:
        """Extract citations from retrieved context.

        Args:
            context: Retrieved context

        Returns:
            List of Citation objects
        """
        citations = []

        for result in context.results[:self.config.max_context_chunks]:
            chunk = result.chunk

            citation = Citation(
                chunk_id=chunk.chunk_id,
                article_title=chunk.article_title,
                section=chunk.section,
                url=chunk.url,
                paragraph_index=chunk.paragraph_index,
                text_excerpt=chunk.text[:100] + "..." if len(chunk.text) > 100 else chunk.text,
            )
            citations.append(citation)

        return citations

    def generate_answer(
        self,
        question: str,
        filters: Optional[Dict[str, Any]] = None,
        max_results: Optional[int] = None,
    ) -> GeneratedAnswer:
        """Generate an answer to a medical question.

        This is the main method that:
        1. Checks cache for existing answer
        2. Retrieves relevant context (if cache miss)
        3. Constructs prompts (if cache miss)
        4. Generates answer with LLM (if cache miss)
        5. Formats citations
        6. Stores result in cache
        7. Tracks costs

        Args:
            question: User's question
            filters: Optional metadata filters for retrieval
            max_results: Maximum chunks to retrieve

        Returns:
            GeneratedAnswer with answer, citations, and metadata
        """
        start_time = time.time()

        # Step 1: Check cache first
        cached_answer = self.cache.get(question, filters, max_results)
        if cached_answer:
            # Cache hit! Track savings
            elapsed_ms = (time.time() - start_time) * 1000
            saved_time_ms = 500  # Typical LLM call time
            saved_cost = cached_answer.cost  # Cost we would have incurred

            self.cache.stats.total_cost_saved += saved_cost
            self.cache.stats.total_time_saved_ms += saved_time_ms

            return cached_answer

        # Cache miss - generate new answer
        # Step 2: Retrieve relevant context
        max_results = max_results or self.config.max_context_chunks
        context = self.retrieval_engine.retrieve_text(
            query_text=question,
            max_results=max_results,
            filters=filters,
        )

        # Check if we have any results
        if not context.results:
            # No context found
            no_context_answer = self.prompts.get(
                "no_context_found",
                "I couldn't find relevant information to answer your question."
            )
            return GeneratedAnswer(
                query=question,
                answer=no_context_answer,
                citations=[],
                context_used=context,
                model=self.config.model,
                tokens_used={"input": 0, "output": 0, "total": 0},
                cost=0.0,
                generation_time_ms=0.0,
                disclaimer=self.config.disclaimer_text if self.config.include_disclaimer else None,
            )

        # Step 2: Format context and prompts
        formatted_context = self._format_context(context)

        system_prompt = self.prompts.get("system_prompt", "You are a helpful assistant.")

        # Use strict citations template if required
        if self.config.require_citations:
            user_prompt_template = self.prompts.get(
                "qa_strict_citations_template",
                self.prompts.get("qa_prompt_template")
            )
        else:
            user_prompt_template = self.prompts.get("qa_prompt_template")

        user_prompt = user_prompt_template.format(
            context=formatted_context,
            question=question,
        )

        # Step 3: Generate answer with LLM
        llm_response = self.llm_client.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
        )

        # Step 4: Extract citations
        citations = self._extract_citations(context)

        # Step 5: Create GeneratedAnswer
        answer = GeneratedAnswer(
            query=question,
            answer=llm_response["answer"],
            citations=citations,
            context_used=context,
            model=llm_response["model"],
            tokens_used=llm_response["tokens_used"],
            cost=llm_response["cost"],
            generation_time_ms=llm_response["generation_time_ms"],
            disclaimer=self.config.disclaimer_text if self.config.include_disclaimer else None,
        )

        # Step 6: Store in cache for future requests
        self.cache.set(question, answer, filters, max_results)

        return answer

    def generate_answer_for_cancer_type(
        self,
        question: str,
        cancer_type: str,
        max_results: Optional[int] = None,
    ) -> GeneratedAnswer:
        """Generate answer filtered by cancer type.

        Args:
            question: User's question
            cancer_type: Cancer type to filter by (e.g., "Breast Cancer")
            max_results: Maximum chunks to retrieve

        Returns:
            GeneratedAnswer with answer and citations
        """
        return self.generate_answer(
            question=question,
            filters={"cancer_type": cancer_type},
            max_results=max_results,
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about generation.

        Returns:
            Dictionary with statistics including cache performance
        """
        llm_stats = self.llm_client.get_stats()
        retrieval_stats = self.retrieval_engine.get_embedding_stats()
        cache_stats = self.cache.get_stats()

        total_actual_cost = llm_stats["total_cost"] + retrieval_stats.get("total_cost", 0)
        total_cost_saved = cache_stats.get("total_cost_saved", 0.0)

        return {
            "llm": llm_stats,
            "retrieval": retrieval_stats,
            "cache": cache_stats,
            "total_cost": total_actual_cost,
            "total_cost_saved": total_cost_saved,
            "total_cost_without_cache": total_actual_cost + total_cost_saved,
            "cost_reduction_percent": (
                (total_cost_saved / (total_actual_cost + total_cost_saved) * 100)
                if (total_actual_cost + total_cost_saved) > 0 else 0
            ),
        }

    def get_config_dict(self) -> Dict[str, Any]:
        """Get current configuration.

        Returns:
            Dictionary with configuration
        """
        return self.config.to_dict()
