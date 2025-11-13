"""LLM-based re-ranking for retrieval results."""

from typing import List
from loguru import logger
from src.storage.models import RetrievalResult
from src.generation.llm_client import LLMClient


class LLMReranker:
    """Re-rank retrieval results using LLM reasoning."""

    def __init__(self, llm_client: LLMClient = None, model: str = "gpt-4o-mini"):
        """Initialize the re-ranker.

        Args:
            llm_client: LLM client for scoring (optional)
            model: Model to use for re-ranking (default: gpt-4o-mini for speed/cost)
        """
        self.model = model
        self.llm_client = llm_client or LLMClient(model=self.model)

    def rerank(
        self,
        query: str,
        results: List[RetrievalResult],
        top_k: int = 10
    ) -> List[RetrievalResult]:
        """Re-rank results using LLM reasoning.

        Args:
            query: User's question
            results: Initial retrieval results
            top_k: Number of top results to return after re-ranking

        Returns:
            Re-ranked list of results
        """
        logger.info(f"🔄 Re-ranking {len(results)} results for query: {query[:50]}...")

        if not results:
            logger.info("No results to re-rank")
            return results

        # If we have fewer results than top_k, no need to re-rank
        if len(results) <= top_k:
            logger.info(f"Only {len(results)} results, no re-ranking needed (top_k={top_k})")
            return results

        # Create prompt for LLM to score relevance
        prompt = self._create_reranking_prompt(query, results)

        # Get LLM scores
        logger.info(f"Calling LLM for re-ranking with model: {self.model}")
        response_dict = self.llm_client.generate(
            system_prompt="You are a relevance scoring assistant. Evaluate how well medical information chunks answer a specific question.",
            user_prompt=prompt,
            max_tokens=500,
            temperature=0.0  # Deterministic scoring
        )

        # Extract the answer text from the response
        response = response_dict.get('answer', '')

        # Parse scores from LLM response
        scores = self._parse_scores(response, len(results))
        logger.info(f"Parsed LLM scores: {scores}")

        # Combine with original similarity scores (weighted)
        # 70% LLM relevance, 30% vector similarity
        logger.info("Combining LLM scores (70%) with vector similarity (30%):")
        for i, result in enumerate(results):
            llm_score = scores.get(i, 0.0)
            vector_score = result.similarity_score
            combined_score = (0.7 * llm_score) + (0.3 * vector_score)
            logger.info(f"  [{i}] LLM={llm_score:.3f}, Vector={vector_score:.3f}, Combined={combined_score:.3f} | {result.chunk.section[:30]}")
            result.similarity_score = combined_score

        # Sort by combined score
        reranked = sorted(results, key=lambda x: x.similarity_score, reverse=True)
        logger.info(f"✅ Re-ranking complete, returning top {top_k} results")

        return reranked[:top_k]

    def _create_reranking_prompt(self, query: str, results: List[RetrievalResult]) -> str:
        """Create prompt for LLM to score chunk relevance.

        Args:
            query: User's question
            results: Retrieval results to score

        Returns:
            Formatted prompt
        """
        chunks_text = ""
        for i, result in enumerate(results):
            chunks_text += f"\n[{i}] Section: {result.chunk.section}\n"
            chunks_text += f"Text: {result.chunk.text[:300]}...\n"

        prompt = f"""You are evaluating how relevant medical information chunks are to answering a specific question.

Question: {query}

Retrieved chunks:
{chunks_text}

Task: For each chunk [0] to [{len(results)-1}], rate its relevance to answering the question on a scale of 0.0 to 1.0, where:
- 1.0 = Directly answers the question with specific, relevant information
- 0.7-0.9 = Contains relevant context that helps answer the question
- 0.4-0.6 = Related information but not directly answering the question
- 0.1-0.3 = Tangentially related or background information
- 0.0 = Not relevant to the question

Consider:
1. Does the chunk directly answer what is being asked?
2. Is the context appropriate (e.g., "normal levels" vs "disease staging")?
3. Is the information specific and actionable?

Respond ONLY with scores in this exact format:
[0]: 0.X
[1]: 0.X
...
[{len(results)-1}]: 0.X"""

        return prompt

    def _parse_scores(self, llm_response: str, num_chunks: int) -> dict:
        """Parse relevance scores from LLM response.

        Args:
            llm_response: LLM's text response
            num_chunks: Expected number of chunks

        Returns:
            Dictionary mapping chunk index to score
        """
        scores = {}
        lines = llm_response.strip().split('\n')

        for line in lines:
            line = line.strip()
            # Look for pattern like "[0]: 0.8" or "[0] 0.8"
            if line.startswith('[') and ']:' in line:
                try:
                    idx_part = line.split(']:')[0]
                    idx = int(idx_part.replace('[', '').strip())
                    
                    score_part = line.split(']:')[1]
                    score = float(score_part.strip())
                    
                    scores[idx] = max(0.0, min(1.0, score))  # Clamp to [0, 1]
                except (ValueError, IndexError):
                    continue

        # Fill in missing scores with default 0.5
        for i in range(num_chunks):
            if i not in scores:
                scores[i] = 0.5

        return scores
