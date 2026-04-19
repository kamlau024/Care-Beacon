import os
from neo4j import GraphDatabase
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class GraphStore:
    def __init__(self):
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD")
        if not self.password:
            raise ValueError(
                "NEO4J_PASSWORD environment variable is required. "
                "Set it to your Neo4j database password."
            )
        self.driver = None
        self.connect()

    def connect(self):
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            self.verify_connection()
            logger.info("Connected to Neo4j")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    def verify_connection(self):
        with self.driver.session() as session:
            session.run("RETURN 1")

    def close(self):
        if self.driver:
            self.driver.close()

    def create_schema(self):
        """Create constraints and indexes"""
        queries = [
            "CREATE CONSTRAINT article_id IF NOT EXISTS FOR (a:Article) REQUIRE a.id IS UNIQUE",
            "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE",
            "CREATE INDEX chunk_vector IF NOT EXISTS FOR (c:Chunk) ON (c.embedding)",
            "CREATE FULLTEXT INDEX chunk_text IF NOT EXISTS FOR (c:Chunk) ON EACH [c.text]"
        ]
        with self.driver.session() as session:
            for q in queries:
                session.run(q)

    def add_article(self, article_data: Dict[str, Any]):
        """
        Create Article node and structure.
        Expected data:
        {
            "id": "...",
            "title": "...",
            "authors": [...],
            "journal": "...",
            "publication_date": "...",
            "chunks": [
                {
                    "id": "...",
                    "text": "...",
                    "section": "...",
                    "paragraph_index": 0
                }
            ]
        }
        """
        query = """
        MERGE (a:Article {id: $id})
        SET a.title = $title,
            a.journal = $journal,
            a.publication_date = $date,
            a.authors = $authors
        
        WITH a
        UNWIND $chunks as chunk_data
        MERGE (c:Chunk {id: chunk_data.id})
        SET c.text = chunk_data.text,
            c.section = chunk_data.section,
            c.paragraph_index = chunk_data.paragraph_index
            
        MERGE (a)-[:HAS_CHUNK]->(c)
        
        // Link chunks sequentially
        WITH c, chunk_data
        ORDER BY chunk_data.paragraph_index
        WITH collect(c) as chunks
        FOREACH (i in range(0, size(chunks)-2) |
            FOREACH (c1 in [chunks[i]] |
                FOREACH (c2 in [chunks[i+1]] |
                    MERGE (c1)-[:NEXT]->(c2)
                )
            )
        )
        """
        with self.driver.session() as session:
            session.run(query, 
                id=article_data["id"],
                title=article_data.get("title", ""),
                journal=article_data.get("journal", ""),
                date=article_data.get("publication_date", ""),
                authors=article_data.get("authors", []),
                chunks=article_data.get("chunks", [])
            )
    def add_entities(self, chunk_id: str, entities: List[Dict[str, Any]]):
        """
        Add entities and link them to the chunk.
        entities: [{'text': '...', 'label': '...'}]
        """
        query = """
        MATCH (c:Chunk {id: $chunk_id})
        UNWIND $entities as entity
        
        // Create Entity node (dynamic label would be nice, but tricky in Cypher params)
        // We'll use a generic Entity label + a specific label property or secondary label
        MERGE (e:Entity {name: toLower(entity.text)})
        SET e.label = entity.label,
            e.original_text = entity.text
            
        // Add specific label (e.g. :Disease)
        WITH c, e, entity
        CALL apoc.create.addLabels(e, [entity.label]) YIELD node
        
        // Create relationship
        MERGE (c)-[:MENTIONS]->(e)
        """
        with self.driver.session() as session:
            session.run(query, chunk_id=chunk_id, entities=entities)
    def vector_search(self, query_embedding: List[float], limit: int = 5) -> List[Dict]:
        """
        Perform vector search on chunks (if we store embeddings in Neo4j).
        Note: Neo4j Vector Index syntax varies by version. This is for 5.x.
        """
        # First ensure index exists (should be done in create_schema)
        # For now, we might rely on Qdrant for vector search and use Neo4j for context expansion
        pass

    def get_context_for_chunks(self, chunk_ids: List[str], expansion_steps: int = 1) -> List[Dict]:
        """
        Given a list of chunk IDs (from vector search), retrieve them plus neighbors.
        """
        query = """
        MATCH (c:Chunk)
        WHERE c.id IN $chunk_ids
        
        // Get the chunk itself
        WITH c
        
        // Optional: Expand to next/prev chunks
        OPTIONAL MATCH (c)-[:NEXT*1..2]-(neighbor:Chunk)
        
        // Optional: Get parent Article
        OPTIONAL MATCH (c)<-[:HAS_CHUNK]-(a:Article)
        
        // Optional: Get connected Entities
        OPTIONAL MATCH (c)-[:MENTIONS]->(e:Entity)
        
        RETURN c.id as id, 
               c.text as text, 
               c.section as section,
               a.title as article_title,
               collect(distinct neighbor.text) as context,
               collect(distinct {name: e.name, label: e.label}) as entities
        """
        with self.driver.session() as session:
            result = session.run(query, chunk_ids=chunk_ids)
            return [record.data() for record in result]
