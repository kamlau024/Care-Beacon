
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from neo4j import GraphDatabase

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Load env vars
load_dotenv()

print("Starting debug script...", flush=True)

def debug_retrieval():
    print("--- Debugging Retrieval ---", flush=True)
    
    # 1. Check Qdrant
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")
    collection_name = "care-beacon-medical"
    
    print(f"Connecting to Qdrant: {qdrant_url}")
    try:
        client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
        collections = client.get_collections()
        print(f"Collections: {[c.name for c in collections.collections]}")
        
        # Check count
        count = client.count(collection_name=collection_name)
        print(f"Count in '{collection_name}': {count}")
        
        if count.count == 0:
            print("WARNING: Collection is empty!")
            return

        # Search
        print("\nSearching for 'lung cancer'...")
        from src.embeddings.embedding_generator import EmbeddingGenerator
        embedder = EmbeddingGenerator()
        query_vector = embedder.embed_text("lung cancer")
        
        results = client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=3
        )
        
        found_ids = []
        for hit in results:
            chunk_id = hit.payload.get("chunk_id")
            print(f"Found Chunk: {chunk_id} (Score: {hit.score})")
            found_ids.append(chunk_id)
            
    except Exception as e:
        print(f"Qdrant Error: {e}")
        return

    # 2. Check Neo4j
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
    
    print(f"\nConnecting to Neo4j: {neo4j_uri}")
    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    
    try:
        with driver.session() as session:
            # Check total chunks
            result = session.run("MATCH (c:Chunk) RETURN count(c) as count")
            print(f"Total Chunks in Neo4j: {result.single()['count']}")
            
            # Check if found IDs exist
            print("\nChecking if Qdrant IDs exist in Neo4j...")
            for chunk_id in found_ids:
                result = session.run(
                    "MATCH (c:Chunk {id: $chunk_id}) RETURN c",
                    chunk_id=chunk_id
                )
                record = result.single()
                if record:
                    print(f"✅ Chunk {chunk_id} FOUND in Neo4j")
                else:
                    print(f"❌ Chunk {chunk_id} NOT FOUND in Neo4j")
                    
    except Exception as e:
        print(f"Neo4j Error: {e}")
    finally:
        driver.close()

if __name__ == "__main__":
    debug_retrieval()
