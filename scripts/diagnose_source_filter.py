#!/usr/bin/env python
"""Diagnostic script to test source filtering on Render.

This script tests the full pipeline with BC Cancer source filter
to help diagnose why queries are returning no results.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.vector_db import VectorDatabase
from src.embeddings.embedding_generator import EmbeddingGenerator
from src.retrieval.retrieval_engine import RetrievalEngine
from src.retrieval.models import Query


def main():
    """Run diagnostics on source filtering."""

    print("=" * 70)
    print("BC CANCER SOURCE FILTER DIAGNOSTIC")
    print("=" * 70)
    print()

    # Step 1: Check database has BC Cancer data
    print("Step 1: Checking database for BC Cancer articles...")
    vdb = VectorDatabase()

    bc_results = vdb.collection.get(
        where={"source": "BC Cancer"},
        limit=5,
        include=["metadatas"]
    )

    bc_count = len(bc_results.get("ids", [])) if bc_results else 0
    print(f"✅ Found {bc_count} BC Cancer chunks")

    if bc_count == 0:
        print("❌ ERROR: No BC Cancer articles found!")
        print("   The BC Cancer articles may not have been ingested.")
        print("   Run: python scripts/validate_ingestion.sh stats")
        return

    # Show sample article
    if bc_results and bc_results.get("metadatas"):
        sample = bc_results["metadatas"][0]
        print(f"   Sample article: {sample.get('article_title')}")
        print(f"   Source value: '{sample.get('source')}'")
    print()

    # Step 2: Test vector search with BC Cancer filter
    print("Step 2: Testing vector search with BC Cancer filter...")
    query_text = "What is a normal PSA level?"
    print(f"   Query: {query_text}")

    emb_gen = EmbeddingGenerator()
    query_embedding = emb_gen.embed_text(query_text)

    search_results = vdb.search(
        query_embedding=query_embedding,
        n_results=10,
        where={"source": "BC Cancer"}
    )

    print(f"✅ Vector search returned {len(search_results)} results")

    if not search_results:
        print("❌ ERROR: Vector search returned no results!")
        print("   This suggests the source filter is not working correctly.")
        return

    # Show top 3 results with similarity scores
    print("   Top 3 results:")
    for i, result in enumerate(search_results[:3]):
        print(f"      {i+1}. {result.chunk.article_title} (similarity: {result.similarity_score:.3f})")
    print()

    # Step 3: Test with min_similarity filter (0.5 like web UI)
    print("Step 3: Testing with min_similarity=0.5 (web UI default)...")

    retrieval_engine = RetrievalEngine(vector_db=vdb)
    query_obj = Query(
        text=query_text,
        max_results=5,
        min_similarity=0.5,
        filters={"source": "BC Cancer"}
    )

    context = retrieval_engine.retrieve(query_obj)

    print(f"✅ Retrieved {len(context.results)} results after filtering")

    if not context.results:
        print("❌ ERROR: No results passed the min_similarity=0.5 threshold!")
        print("   This means BC Cancer results have similarity scores below 0.5")
        print("   for this particular query.")
        print()
        print("   Try lowering the similarity threshold in the web UI slider,")
        print("   or try a different query.")
        return

    # Show results that passed
    print("   Results that passed 0.5 threshold:")
    for i, result in enumerate(context.results):
        print(f"      {i+1}. {result.chunk.article_title}")
        print(f"         Section: {result.chunk.section}")
        print(f"         Similarity: {result.similarity_score:.3f}")
        print(f"         Text: {result.chunk.text[:100]}...")
    print()

    # Step 4: Test full answer generation
    print("Step 4: Testing full answer generation...")
    try:
        from src.generation.answer_generator import AnswerGenerator

        generator = AnswerGenerator()
        answer = generator.generate_answer(
            question=query_text,
            filters={"source": "BC Cancer"},
            max_results=5,
            min_similarity=0.5
        )

        print(f"✅ Answer generated successfully")
        print(f"   Answer length: {len(answer.answer)} characters")
        print(f"   Citations: {len(answer.citations)}")
        print(f"   Model: {answer.model}")
        print(f"   Cost: ${answer.cost:.6f}")
        print()
        print(f"   Answer preview: {answer.answer[:200]}...")
        print()

        if not answer.citations:
            print("⚠️  WARNING: Answer has no citations!")
            print("   This might indicate an issue with citation extraction.")

    except Exception as e:
        print(f"❌ ERROR during answer generation: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 5: Final summary
    print()
    print("=" * 70)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 70)
    print("✅ Database has BC Cancer articles")
    print("✅ Vector search with BC Cancer filter works")
    print(f"✅ {len(context.results)} results pass min_similarity=0.5")
    print("✅ Answer generation works")
    print()
    print("🎉 All checks passed! The source filtering should be working.")
    print()
    print("If you're still seeing 'no answer' in the web UI:")
    print("1. Check browser console for JavaScript errors")
    print("2. Try clearing browser cache and cookies")
    print("3. Verify the API URL in web UI is correct")
    print("4. Check Render logs for any API errors")


if __name__ == "__main__":
    main()
