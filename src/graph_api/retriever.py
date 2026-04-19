from typing import List, Dict, Any
import os
from qdrant_client import QdrantClient
from src.graph_api.graph_store import GraphStore
from src.embeddings.embedding_generator import EmbeddingGenerator
import logging

logger = logging.getLogger(__name__)

class GraphRetriever:
    def __init__(self, graph_store: GraphStore):
        self.graph_store = graph_store
        
        # Initialize Qdrant Client
        self.qdrant_url = os.getenv("QDRANT_URL")
        self.qdrant_api_key = os.getenv("QDRANT_API_KEY")
        
        if self.qdrant_url:
            self.qdrant_client = QdrantClient(
                url=self.qdrant_url,
                api_key=self.qdrant_api_key,
                timeout=60.0
            )
        else:
            self.qdrant_client = None
            logger.warning("Qdrant URL not set. Vector search will be disabled.")

        self.collection_name = "care-beacon-medical" # Default collection name
        
        # Initialize Embedding Generator
        self.embedding_generator = EmbeddingGenerator()

    def retrieve(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Hybrid retrieval:
        1. Vector Search -> Get Top K Chunks
        2. Graph Expansion -> Get Neighbors / Context
        """
        if not self.qdrant_client:
            return []

        try:
            # 1. Embed Query
            query_vector = self.embedding_generator.embed_text(query)
            
            # 2. Vector Search
            search_result = self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit
            )
            
            chunk_ids = [hit.payload.get("chunk_id") for hit in search_result if hit.payload]
            
            # 3. Graph Expansion
            expanded_context = self.graph_store.get_context_for_chunks(chunk_ids)
            
            # Merge scores
            # For simplicity, we just return the expanded context with original scores if possible
            # But graph store returns a list of dicts. We need to map back.
            
            # Create a map of id -> score
            score_map = {hit.payload.get("chunk_id"): hit.score for hit in search_result if hit.payload}
            
            for item in expanded_context:
                item["score"] = score_map.get(item["id"], 0.0)
                
            return expanded_context
            
        except Exception as e:
            logger.error(f"Retrieval failed: {e}")
            return []
        
    def retrieve_by_ids(self, chunk_ids: List[str]) -> List[Dict]:
        """
        Retrieve context for specific chunk IDs (e.g. from an external vector search)
        """
        return self.graph_store.get_context_for_chunks(chunk_ids)
