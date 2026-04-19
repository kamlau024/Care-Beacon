import os
import json
from typing import List, Dict
from src.graph_api.graph_store import GraphStore
import logging

logger = logging.getLogger(__name__)

from src.graph_api.extractor import EntityExtractor

class GraphIngestion:
    def __init__(self, graph_store: GraphStore, enable_extraction: bool = False):
        self.graph_store = graph_store
        self.enable_extraction = enable_extraction
        self.extractor = EntityExtractor() if enable_extraction else None

    def ingest_article_from_json(self, article_data: Dict):
        """
        Ingest a single article into the graph.
        """
        try:
            # 1. Add Article and Chunks structure
            self.graph_store.add_article(article_data)
            
            # 2. Extract and Add Entities (if enabled)
            if self.enable_extraction and self.extractor:
                for chunk in article_data.get("chunks", []):
                    text = chunk.get("text", "")
                    if text:
                        entities = self.extractor.extract_entities(text)
                        if entities:
                            self.graph_store.add_entities(chunk.get("id"), entities)
                            
            logger.info(f"Ingested article: {article_data.get('id')}")
        except Exception as e:
            logger.error(f"Error ingesting article {article_data.get('id')}: {e}")

    def ingest_batch(self, articles: List[Dict]):
        for article in articles:
            self.ingest_article_from_json(article)
