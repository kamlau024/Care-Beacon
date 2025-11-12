"""Validate what files have been ingested into the vector database.

This script helps you check:
- If a specific file has been ingested
- What chunks exist for a given article
- Search for specific content in the database
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.vector_db import VectorDatabase
from src.config_loader import get_config


def list_all_chunks(vector_db: VectorDatabase, limit: int = 100):
    """List all chunks in the database.

    Args:
        vector_db: Vector database instance
        limit: Maximum number of chunks to display
    """
    print(f"\n{'='*70}")
    print(f"LISTING ALL CHUNKS (limit: {limit})")
    print(f"{'='*70}\n")

    # Get all chunks by searching with empty query (or using get_all if available)
    try:
        # Try to get collection directly
        collection = vector_db.collection
        results = collection.get(limit=limit, include=["metadatas", "documents"])

        if not results or not results.get("ids"):
            print("❌ No chunks found in database")
            return

        total = len(results["ids"])
        print(f"✅ Found {total} chunks\n")

        # Group by article
        articles = {}
        for i, chunk_id in enumerate(results["ids"]):
            metadata = results["metadatas"][i] if results.get("metadatas") else {}
            article_title = metadata.get("article_title", "Unknown")
            source = metadata.get("source", "Unknown")

            key = f"{article_title} ({source})"
            if key not in articles:
                articles[key] = []
            articles[key].append(chunk_id)

        print(f"📊 Articles in database: {len(articles)}\n")
        for article, chunks in sorted(articles.items()):
            print(f"  • {article}: {len(chunks)} chunks")

    except Exception as e:
        print(f"❌ Error listing chunks: {e}")


def search_by_article_title(vector_db: VectorDatabase, title: str):
    """Search for chunks by article title.

    Args:
        vector_db: Vector database instance
        title: Article title to search for (case-insensitive partial match)
    """
    print(f"\n{'='*70}")
    print(f"SEARCHING FOR ARTICLE: '{title}'")
    print(f"{'='*70}\n")

    try:
        collection = vector_db.collection

        # Get all chunks (ChromaDB doesn't support $contains, so we filter in Python)
        # First try exact match
        results = collection.get(
            where={"article_title": {"$eq": title}},
            include=["metadatas", "documents"]
        )

        # If no exact match, get all and filter by partial match
        if not results or not results.get("ids"):
            print(f"No exact match found. Searching for partial matches...")
            all_results = collection.get(include=["metadatas", "documents"])

            # Filter by title (case-insensitive partial match)
            matching_ids = []
            matching_metadatas = []
            matching_documents = []

            if all_results and all_results.get("ids"):
                title_lower = title.lower()
                for i, metadata in enumerate(all_results.get("metadatas", [])):
                    article_title = metadata.get("article_title", "")
                    if title_lower in article_title.lower():
                        matching_ids.append(all_results["ids"][i])
                        matching_metadatas.append(metadata)
                        matching_documents.append(all_results.get("documents", [])[i] if all_results.get("documents") else "")

            results = {
                "ids": matching_ids,
                "metadatas": matching_metadatas,
                "documents": matching_documents
            }

        if not results or not results.get("ids"):
            print(f"❌ No chunks found for article containing '{title}'")
            print(f"\n💡 Try searching with a different title or check if the file was ingested.")
            return

        total = len(results["ids"])
        print(f"✅ Found {total} chunks\n")

        # Display first few chunks
        for i in range(min(5, total)):
            chunk_id = results["ids"][i]
            metadata = results["metadatas"][i] if results.get("metadatas") else {}
            doc = results["documents"][i] if results.get("documents") else ""

            print(f"Chunk {i+1}/{total}:")
            print(f"  ID: {chunk_id}")
            print(f"  Article: {metadata.get('article_title', 'Unknown')}")
            print(f"  Section: {metadata.get('section', 'Unknown')}")
            print(f"  Source: {metadata.get('source', 'Unknown')}")
            print(f"  Text preview: {doc[:200]}...")
            print()

        if total > 5:
            print(f"... and {total - 5} more chunks")

    except Exception as e:
        print(f"❌ Error searching: {e}")


def search_by_content(vector_db: VectorDatabase, query: str, top_k: int = 5, source_filter: str = None):
    """Search for chunks by content using semantic search.

    Args:
        vector_db: Vector database instance
        query: Search query
        top_k: Number of results to return
        source_filter: Optional source filter (e.g., "BC Cancer", "Canadian Cancer Society")
    """
    print(f"\n{'='*70}")
    print(f"SEMANTIC SEARCH: '{query}'")
    if source_filter:
        print(f"SOURCE FILTER: '{source_filter}'")
    print(f"{'='*70}\n")

    try:
        from src.retrieval.retrieval_engine import RetrievalEngine
        from src.retrieval.models import Query

        retrieval = RetrievalEngine(vector_db=vector_db)

        # Add source filter if specified
        filters = None
        if source_filter:
            filters = {"source": source_filter}

        query_obj = Query(text=query, max_results=top_k, filters=filters)
        context = retrieval.retrieve(query=query_obj)

        if not context.results:
            print(f"❌ No results found for query: '{query}'")
            return

        print(f"✅ Found {len(context.results)} results\n")

        for i, result in enumerate(context.results, 1):
            print(f"Result {i}:")
            print(f"  Article: {result.chunk.article_title}")
            print(f"  Section: {result.chunk.section}")
            print(f"  Source: {result.chunk.source}")
            print(f"  Similarity: {result.similarity_score:.3f}")
            print(f"  Text preview: {result.chunk.text[:200]}...")
            print()

    except Exception as e:
        print(f"❌ Error during semantic search: {e}")


def search_by_source(vector_db: VectorDatabase, source: str):
    """Search for chunks by source.

    Args:
        vector_db: Vector database instance
        source: Source to filter by (e.g., "BC Cancer", "Canadian Cancer Society")
    """
    print(f"\n{'='*70}")
    print(f"SEARCHING BY SOURCE: '{source}'")
    print(f"{'='*70}\n")

    try:
        collection = vector_db.collection
        results = collection.get(
            where={"source": source},
            include=["metadatas"]
        )

        if not results or not results.get("ids"):
            print(f"❌ No chunks found for source: '{source}'")
            print(f"\n💡 Available sources might be:")
            print(f"   - BC Cancer")
            print(f"   - Canadian Cancer Society")
            return

        total = len(results["ids"])
        print(f"✅ Found {total} chunks from '{source}'\n")

        # Group by article
        articles = {}
        for i, chunk_id in enumerate(results["ids"]):
            metadata = results["metadatas"][i] if results.get("metadatas") else {}
            article_title = metadata.get("article_title", "Unknown")

            if article_title not in articles:
                articles[article_title] = 0
            articles[article_title] += 1

        print(f"📊 Articles from '{source}': {len(articles)}\n")
        for article, count in sorted(articles.items()):
            print(f"  • {article}: {count} chunks")

    except Exception as e:
        print(f"❌ Error searching by source: {e}")


def check_specific_file(vector_db: VectorDatabase, file_path: str):
    """Check if a specific markdown file has been ingested.

    Args:
        vector_db: Vector database instance
        file_path: Path to the markdown file
    """
    from src.ingestion.markdown_parser import MarkdownParser

    file_path = Path(file_path)

    print(f"\n{'='*70}")
    print(f"CHECKING FILE: {file_path.name}")
    print(f"{'='*70}\n")

    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return

    print(f"📄 File exists: {file_path}")
    print(f"   Path: {file_path}")

    # Parse the file to get the title
    try:
        parser = MarkdownParser()
        article = parser.parse_file(file_path)

        print(f"\n📋 File Metadata:")
        print(f"   Title: {article.title}")
        print(f"   URL: {article.url}")
        print(f"   Sections: {len(article.sections)}")

        # Search for this article in the database
        search_by_article_title(vector_db, article.title)

    except Exception as e:
        print(f"❌ Error parsing file: {e}")


def get_database_stats(vector_db: VectorDatabase):
    """Get overall statistics about the database.

    Args:
        vector_db: Vector database instance
    """
    print(f"\n{'='*70}")
    print(f"DATABASE STATISTICS")
    print(f"{'='*70}\n")

    try:
        stats = vector_db.get_stats()
        collection = vector_db.collection

        # Count total unique documents (articles)
        all_results = collection.get(include=["metadatas"])
        unique_articles = set()
        if all_results and all_results.get("metadatas"):
            for metadata in all_results.get("metadatas", []):
                article_id = metadata.get("article_id", "")
                if article_id:
                    unique_articles.add(article_id)

        print(f"📊 Total documents (unique articles): {len(unique_articles):,}")
        print(f"📊 Total chunks: {stats.get('total_chunks', 0):,}")

        # Get breakdown by source
        # BC Cancer
        bc_results = collection.get(where={"source": "BC Cancer"}, include=["metadatas"])
        bc_count = len(bc_results.get("ids", [])) if bc_results else 0

        # Count unique BC Cancer articles
        bc_articles = set()
        if bc_results and bc_results.get("metadatas"):
            for metadata in bc_results.get("metadatas", []):
                article_id = metadata.get("article_id", "")
                if article_id:
                    bc_articles.add(article_id)

        # Canadian Cancer Society
        ccs_results = collection.get(where={"source": "Canadian Cancer Society"}, include=["metadatas"])
        ccs_count = len(ccs_results.get("ids", [])) if ccs_results else 0

        # Count unique CCS articles
        ccs_articles = set()
        if ccs_results and ccs_results.get("metadatas"):
            for metadata in ccs_results.get("metadatas", []):
                article_id = metadata.get("article_id", "")
                if article_id:
                    ccs_articles.add(article_id)

        print(f"\n📚 By Source:")
        print(f"   BC Cancer: {bc_count:,} chunks ({len(bc_articles)} articles)")
        print(f"   Canadian Cancer Society: {ccs_count:,} chunks ({len(ccs_articles)} articles)")

    except Exception as e:
        print(f"❌ Error getting stats: {e}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate Care-Beacon vector database ingestion",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Get database statistics
  python scripts/validate_ingestion.py --stats

  # List all chunks
  python scripts/validate_ingestion.py --list

  # Search for a specific article
  python scripts/validate_ingestion.py --article "Prostate"

  # Check if a specific file was ingested
  python scripts/validate_ingestion.py --file scraped_data/articles/health-info/types-of-cancer/pelvic-area/prostate.md

  # Semantic search
  python scripts/validate_ingestion.py --search "What is a normal PSA level?"

  # Search by source
  python scripts/validate_ingestion.py --source "BC Cancer"
        """
    )

    parser.add_argument("--stats", action="store_true", help="Show database statistics")
    parser.add_argument("--list", action="store_true", help="List all chunks")
    parser.add_argument("--article", type=str, help="Search for article by title")
    parser.add_argument("--file", type=str, help="Check if a specific file was ingested")
    parser.add_argument("--search", type=str, help="Semantic search for content")
    parser.add_argument("--source", type=str, help="Filter by source (can be used with --list or standalone)")
    parser.add_argument("--source-filter", type=str, help="Filter search results by source (use with --search)")
    parser.add_argument("--limit", type=int, default=100, help="Limit for list command")
    parser.add_argument("--top-k", type=int, default=5, help="Number of search results")

    args = parser.parse_args()

    # Initialize vector database
    config = get_config()
    vector_db = VectorDatabase()

    # Execute commands
    if args.stats:
        get_database_stats(vector_db)

    if args.list:
        list_all_chunks(vector_db, limit=args.limit)

    if args.article:
        search_by_article_title(vector_db, args.article)

    if args.file:
        check_specific_file(vector_db, args.file)

    if args.search:
        search_by_content(vector_db, args.search, top_k=args.top_k, source_filter=args.source_filter)

    if args.source:
        search_by_source(vector_db, args.source)

    # If no arguments provided, show stats by default
    if not any([args.stats, args.list, args.article, args.file, args.search, args.source]):
        get_database_stats(vector_db)
        print("\n💡 Use --help to see all available options")


if __name__ == "__main__":
    main()
