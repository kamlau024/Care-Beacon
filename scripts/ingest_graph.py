import os
import sys
import json
import glob
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.graph_api.graph_store import GraphStore
from src.graph_api.ingestion import GraphIngestion
from src.ingestion.markdown_parser import MedicalArticleParser
from src.embeddings.chunking import DocumentChunker

def load_processed_articles(data_dir: str):
    """
    Load and parse articles using the standard pipeline to ensure ID consistency.
    """
    parser = MedicalArticleParser()
    chunker = DocumentChunker()
    
    articles_data = []
    files = glob.glob(os.path.join(data_dir, "**/*.md"), recursive=True)
    
    print(f"Found {len(files)} markdown files.")
    
    # Process in batches to avoid memory issues
    for i, file_path in enumerate(files):
        try:
            # Parse
            article = parser.parse_file(file_path)
            
            # Chunk
            chunks = chunker.chunk_article(article)
            
            # Convert to dictionary format expected by GraphStore
            article_dict = {
                "id": article.article_id,
                "title": article.title,
                "journal": article.journal,
                "publication_date": article.publication_date,
                "authors": article.authors,
                "chunks": []
            }
            
            for chunk in chunks:
                article_dict["chunks"].append({
                    "id": chunk.chunk_id,
                    "text": chunk.text,
                    "section": chunk.section,
                    "paragraph_index": chunk.paragraph_index
                })
                
            articles_data.append(article_dict)
            
            if (i + 1) % 100 == 0:
                print(f"Processed {i + 1} articles...")
                
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            continue
        
    return articles_data

import argparse

def main():
    parser = argparse.ArgumentParser(description="Ingest articles into Neo4j Graph")
    parser.add_argument("--extract-entities", action="store_true", help="Enable entity extraction using GLiNER")
    args = parser.parse_args()

    print("Starting Graph Ingestion...")
    if args.extract_entities:
        print("Entity Extraction ENABLED (this will be slower)")
    
    # Initialize
    store = GraphStore()
    ingestion = GraphIngestion(store, enable_extraction=args.extract_entities)
    
    # Create Schema
    store.create_schema()
    
    # Load Data
    data_dir = os.path.join(project_root, "scraped_data")
    articles = load_processed_articles(data_dir)
    
    print(f"Ingesting {len(articles)} articles into Graph...")
    
    # Ingest
    ingestion.ingest_batch(articles)
    
    print("Ingestion Complete.")
    store.close()

if __name__ == "__main__":
    main()
