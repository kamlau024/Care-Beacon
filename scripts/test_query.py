"""Interactive test script to query the vector database.

This script allows you to:
1. Check database statistics
2. Run sample queries
3. Enter custom queries
4. Test metadata filtering
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.embeddings.embedding_generator import EmbeddingGenerator
from src.storage.vector_db import VectorDatabase


def show_database_stats(db: VectorDatabase):
    """Display database statistics."""
    print("=" * 70)
    print("Database Statistics")
    print("=" * 70)
    print()

    stats = db.get_stats()
    print(f"Collection: {stats['collection_name']}")
    print(f"Total chunks: {stats['total_chunks']:,}")
    print(f"Unique articles (sample): {stats.get('unique_articles_sample', 'N/A')}")
    print(f"Distance metric: {stats['distance_metric']}")
    print(f"Storage: {stats['persist_directory']}")
    print()


def show_sample_chunks(db: VectorDatabase, limit: int = 5):
    """Show sample chunks from the database."""
    print("=" * 70)
    print(f"Sample Chunks (showing {limit})")
    print("=" * 70)
    print()

    samples = db.peek(limit=limit)

    for i, chunk in enumerate(samples, 1):
        text_preview = chunk.text[:100] + "..." if len(chunk.text) > 100 else chunk.text
        print(f"{i}. [{chunk.chunk_id}]")
        print(f"   Article: {chunk.article_title}")
        print(f"   Section: {chunk.section}")
        print(f"   Cancer Type: {chunk.cancer_type or 'N/A'}")
        print(f"   Text: \"{text_preview}\"")
        print()


def run_query(query: str, db: VectorDatabase, generator: EmbeddingGenerator, n_results: int = 5):
    """Run a query and display results."""
    print("=" * 70)
    print(f"Query: \"{query}\"")
    print("=" * 70)
    print()

    # Generate query embedding
    print("Generating query embedding...")
    query_embedding = generator.embed_text(query)

    # Search
    print(f"Searching database for top {n_results} results...")
    results = db.search(query_embedding, n_results=n_results)

    if not results:
        print("❌ No results found")
        return

    print(f"✅ Found {len(results)} results:")
    print()

    for result in results:
        chunk = result.chunk
        text_preview = chunk.text[:150] + "..." if len(chunk.text) > 150 else chunk.text

        print(f"[{result.rank}] Similarity Score: {result.similarity_score:.4f}")
        print(f"    Article: {chunk.article_title}")
        print(f"    Section: {chunk.section}")
        if chunk.cancer_type:
            print(f"    Cancer Type: {chunk.cancer_type}")
        print(f"    URL: {chunk.url}")
        print(f"    Text: \"{text_preview}\"")
        print()


def run_filtered_query(query: str, filter_field: str, filter_value: str,
                      db: VectorDatabase, generator: EmbeddingGenerator, n_results: int = 5):
    """Run a query with metadata filtering."""
    print("=" * 70)
    print(f"Filtered Query: \"{query}\"")
    print(f"Filter: {filter_field} = {filter_value}")
    print("=" * 70)
    print()

    # Generate query embedding
    query_embedding = generator.embed_text(query)

    # Search with filter
    results = db.search(
        query_embedding,
        n_results=n_results,
        where={filter_field: filter_value}
    )

    if not results:
        print(f"❌ No results found with filter {filter_field}={filter_value}")
        return

    print(f"✅ Found {len(results)} results:")
    print()

    for result in results:
        chunk = result.chunk
        text_preview = chunk.text[:150] + "..." if len(chunk.text) > 150 else chunk.text

        print(f"[{result.rank}] Similarity Score: {result.similarity_score:.4f}")
        print(f"    Article: {chunk.article_title}")
        print(f"    Section: {chunk.section}")
        print(f"    Text: \"{text_preview}\"")
        print()


def run_sample_queries(db: VectorDatabase, generator: EmbeddingGenerator):
    """Run predefined sample queries."""
    print("=" * 70)
    print("Running Sample Queries")
    print("=" * 70)
    print()

    sample_queries = [
        "What are the symptoms of breast cancer?",
        "How is lung cancer diagnosed?",
        "What are treatment options for pancreatic cancer?",
        "Can I prevent colorectal cancer?",
        "What are the side effects of chemotherapy?",
    ]

    for i, query in enumerate(sample_queries, 1):
        print(f"\n[Query {i}/{len(sample_queries)}]")
        run_query(query, db, generator, n_results=3)

        if i < len(sample_queries):
            input("Press Enter to continue to next query...")


def interactive_mode(db: VectorDatabase, generator: EmbeddingGenerator):
    """Interactive query mode."""
    print("=" * 70)
    print("Interactive Query Mode")
    print("=" * 70)
    print()
    print("Enter your questions about cancer. Type 'quit' to exit.")
    print()

    while True:
        try:
            query = input("\nYour question: ").strip()

            if not query:
                continue

            if query.lower() in ['quit', 'exit', 'q']:
                print("Exiting interactive mode.")
                break

            # Ask for number of results
            try:
                n_results = input("Number of results (default 5): ").strip()
                n_results = int(n_results) if n_results else 5
            except ValueError:
                n_results = 5

            print()
            run_query(query, db, generator, n_results=n_results)

        except KeyboardInterrupt:
            print("\n\nExiting interactive mode.")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")


def main():
    """Main test menu."""
    print()
    print("=" * 70)
    print("Care-Beacon Vector Database - Query Test")
    print("=" * 70)
    print()

    # Initialize components
    print("Initializing components...")
    try:
        generator = EmbeddingGenerator()
        db = VectorDatabase()
        print("✅ Components initialized")
        print()
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        return

    # Check if database has data
    count = db.count()
    if count == 0:
        print("❌ Database is empty. Run ingest_all_articles.py first.")
        return

    # Main menu
    while True:
        print("=" * 70)
        print("What would you like to do?")
        print("=" * 70)
        print()
        print("1. Show database statistics")
        print("2. View sample chunks")
        print("3. Run predefined sample queries")
        print("4. Enter custom query")
        print("5. Test metadata filtering")
        print("6. Interactive query mode")
        print("7. Exit")
        print()

        try:
            choice = input("Enter your choice (1-7): ").strip()
            print()

            if choice == "1":
                show_database_stats(db)

            elif choice == "2":
                try:
                    limit = input("Number of samples to show (default 5): ").strip()
                    limit = int(limit) if limit else 5
                except ValueError:
                    limit = 5
                print()
                show_sample_chunks(db, limit=limit)

            elif choice == "3":
                run_sample_queries(db, generator)

            elif choice == "4":
                query = input("Enter your question: ").strip()
                if query:
                    try:
                        n_results = input("Number of results (default 5): ").strip()
                        n_results = int(n_results) if n_results else 5
                    except ValueError:
                        n_results = 5
                    print()
                    run_query(query, db, generator, n_results=n_results)

            elif choice == "5":
                print("Available filters:")
                print("  - cancer_type (e.g., 'Breast Cancer', 'Lung Cancer')")
                print("  - article_id (e.g., 'breast-cancer', 'lung')")
                print()

                query = input("Enter your question: ").strip()
                filter_field = input("Filter field: ").strip()
                filter_value = input("Filter value: ").strip()

                if query and filter_field and filter_value:
                    try:
                        n_results = input("Number of results (default 5): ").strip()
                        n_results = int(n_results) if n_results else 5
                    except ValueError:
                        n_results = 5
                    print()
                    run_filtered_query(query, filter_field, filter_value, db, generator, n_results)

            elif choice == "6":
                interactive_mode(db, generator)

            elif choice == "7":
                print("Goodbye!")
                break

            else:
                print("Invalid choice. Please enter 1-7.")

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
