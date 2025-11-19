"""BM25 index for keyword-based retrieval.

This module provides BM25 (Best Match 25) ranking for keyword-based search,
which complements vector similarity search in hybrid retrieval scenarios.
"""

import pickle
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from rank_bm25 import BM25Okapi
from loguru import logger

from src.storage.models import Chunk


class BM25Index:
    """BM25 index for keyword-based retrieval.

    BM25 (Best Match 25) is a ranking function used for keyword-based search.
    It excels at finding exact term matches and is particularly useful for:
    - Medical terminology (drug names, procedures, tests)
    - Technical terms and acronyms
    - Specific phrases and keywords

    This index works alongside vector similarity search to provide hybrid retrieval.

    Example:
        >>> index = BM25Index()
        >>> chunks = [...]  # List of Chunk objects
        >>> index.build(chunks)
        >>> results = index.search("breast cancer symptoms", n_results=5)
        >>> for chunk_id, score in results:
        ...     print(f"{chunk_id}: {score:.4f}")
    """

    def __init__(self):
        """Initialize the BM25 index."""
        self.bm25: Optional[BM25Okapi] = None
        self.chunk_ids: List[str] = []
        self.tokenized_corpus: List[List[str]] = []

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text for BM25 indexing.

        This tokenizer:
        - Converts to lowercase
        - Splits on whitespace and punctuation
        - Preserves alphanumeric tokens
        - Filters out very short tokens (< 2 chars)

        Args:
            text: Text to tokenize

        Returns:
            List of tokens
        """
        # Convert to lowercase
        text = text.lower()

        # Split on whitespace and punctuation, keeping alphanumeric tokens
        # This regex splits on non-alphanumeric characters
        tokens = re.findall(r'\b\w+\b', text)

        # Filter out very short tokens (less than 2 characters)
        tokens = [token for token in tokens if len(token) >= 2]

        return tokens

    def build(self, chunks: List[Chunk], show_progress: bool = True) -> None:
        """Build BM25 index from chunks.

        Args:
            chunks: List of Chunk objects to index
            show_progress: Whether to show progress updates
        """
        if not chunks:
            logger.warning("No chunks provided to build BM25 index")
            return

        if show_progress:
            logger.info(f"Building BM25 index for {len(chunks)} chunks...")

        # Reset index
        self.chunk_ids = []
        self.tokenized_corpus = []

        # Tokenize all chunks
        for chunk in chunks:
            self.chunk_ids.append(chunk.chunk_id)
            tokens = self._tokenize(chunk.text)
            self.tokenized_corpus.append(tokens)

        # Build BM25 index
        self.bm25 = BM25Okapi(self.tokenized_corpus)

        if show_progress:
            logger.info(f"✅ BM25 index built with {len(self.chunk_ids)} documents")

    def search(self, query_text: str, n_results: int = 10) -> List[Tuple[str, float]]:
        """Search the BM25 index.

        Args:
            query_text: Query text
            n_results: Number of results to return

        Returns:
            List of (chunk_id, score) tuples, sorted by score (descending)

        Raises:
            RuntimeError: If index hasn't been built yet
        """
        if self.bm25 is None:
            raise RuntimeError("BM25 index not built. Call build() first.")

        # Tokenize query
        query_tokens = self._tokenize(query_text)

        if not query_tokens:
            logger.warning(f"Query tokenization resulted in no tokens: '{query_text}'")
            return []

        # Get BM25 scores for all documents
        scores = self.bm25.get_scores(query_tokens)

        # Get top n_results
        # Sort by score descending and get indices
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n_results]

        # Create results list with chunk_ids and scores
        results = [
            (self.chunk_ids[idx], float(scores[idx]))
            for idx in top_indices
            if scores[idx] > 0  # Only include non-zero scores
        ]

        return results

    def save(self, file_path: str) -> None:
        """Save BM25 index to disk.

        Args:
            file_path: Path to save the index
        """
        if self.bm25 is None:
            raise RuntimeError("Cannot save: BM25 index not built yet")

        # Create directory if it doesn't exist
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)

        # Save index data
        index_data = {
            'bm25': self.bm25,
            'chunk_ids': self.chunk_ids,
            'tokenized_corpus': self.tokenized_corpus
        }

        with open(file_path, 'wb') as f:
            pickle.dump(index_data, f)

        logger.info(f"✅ BM25 index saved to {file_path}")

    def load(self, file_path: str) -> None:
        """Load BM25 index from disk.

        Args:
            file_path: Path to load the index from

        Raises:
            FileNotFoundError: If index file doesn't exist
        """
        if not Path(file_path).exists():
            raise FileNotFoundError(f"BM25 index not found at {file_path}")

        # Load index data
        with open(file_path, 'rb') as f:
            index_data = pickle.load(f)

        self.bm25 = index_data['bm25']
        self.chunk_ids = index_data['chunk_ids']
        self.tokenized_corpus = index_data['tokenized_corpus']

        logger.info(f"✅ BM25 index loaded from {file_path} ({len(self.chunk_ids)} documents)")

    def get_stats(self) -> Dict[str, any]:
        """Get statistics about the BM25 index.

        Returns:
            Dictionary with index statistics
        """
        if self.bm25 is None:
            return {
                'status': 'not_built',
                'num_documents': 0,
                'avg_doc_length': 0
            }

        # Calculate average document length
        doc_lengths = [len(doc) for doc in self.tokenized_corpus]
        avg_doc_length = sum(doc_lengths) / len(doc_lengths) if doc_lengths else 0

        return {
            'status': 'ready',
            'num_documents': len(self.chunk_ids),
            'avg_doc_length': avg_doc_length,
            'total_tokens': sum(doc_lengths)
        }
