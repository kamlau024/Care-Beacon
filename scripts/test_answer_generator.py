"""Test script for answer generation with real queries.

WARNING: This script makes actual OpenAI API calls and will incur costs!
Estimated cost per query: ~$0.0002-0.0005 (very small)
"""

import sys
from pathlib import Path
import os
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file
load_dotenv(project_root / ".env")

# Disable ChromaDB telemetry (before importing ChromaDB dependencies)
os.environ["ANONYMIZED_TELEMETRY"] = "False"


class FilteredStderr:
    """Filter out ChromaDB telemetry warnings from stderr."""

    def __init__(self, original_stderr):
        self.original_stderr = original_stderr

    def write(self, message):
        # Filter out telemetry warnings
        if "telemetry" not in message.lower() and "capture()" not in message:
            self.original_stderr.write(message)

    def flush(self):
        self.original_stderr.flush()


# Install stderr filter to hide ChromaDB telemetry warnings
sys.stderr = FilteredStderr(sys.stderr)

from src.generation.answer_generator import AnswerGenerator


def print_divider(title: str = ""):
    """Print a formatted divider."""
    if title:
        print()
        print("=" * 70)
        print(title)
        print("=" * 70)
        print()
    else:
        print("-" * 70)


def print_answer(answer):
    """Print a generated answer in a formatted way."""
    print(f"Query: \"{answer.query}\"")
    print()

    print("Answer:")
    print_divider()
    print(answer.answer)
    print_divider()

    if answer.citations:
        print()
        print("Sources Used:")
        for i, citation in enumerate(answer.citations, 1):
            print(f"  {i}. {citation.to_reference()}")
            print(f"     URL: {citation.url}")

    print()
    print("Generation Stats:")
    print(f"  Model: {answer.model}")
    print(f"  Input tokens: {answer.tokens_used['input']}")
    print(f"  Output tokens: {answer.tokens_used['output']}")
    print(f"  Total tokens: {answer.tokens_used['total']}")
    print(f"  Cost: ${answer.cost:.6f}")
    print(f"  Time: {answer.generation_time_ms:.0f}ms")
    print(f"  Chunks used: {len(answer.citations)}")

    if answer.disclaimer:
        print()
        print("Disclaimer:")
        print(f"  {answer.disclaimer}")


def test_basic_question(generator: AnswerGenerator):
    """Test a basic medical question."""
    print_divider("Test 1: Basic Medical Question")

    question = "What are the symptoms of breast cancer?"

    print(f"Generating answer for: \"{question}\"")
    print("(This will call OpenAI API...)")
    print()

    answer = generator.generate_answer(question, max_results=5)
    print_answer(answer)


def test_filtered_question(generator: AnswerGenerator):
    """Test a question with cancer type filtering."""
    print_divider("Test 2: Filtered Question (Lung Cancer Only)")

    question = "What are treatment options?"
    cancer_type = "Lung Cancer"

    print(f"Question: \"{question}\"")
    print(f"Filter: {cancer_type}")
    print("(This will call OpenAI API...)")
    print()

    answer = generator.generate_answer_for_cancer_type(question, cancer_type, max_results=3)
    print_answer(answer)


def test_diagnostic_question(generator: AnswerGenerator):
    """Test a question about diagnosis."""
    print_divider("Test 3: Diagnostic Question")

    question = "How is colorectal cancer diagnosed?"

    print(f"Generating answer for: \"{question}\"")
    print("(This will call OpenAI API...)")
    print()

    answer = generator.generate_answer(question, max_results=5)
    print_answer(answer)


def test_prevention_question(generator: AnswerGenerator):
    """Test a question about prevention."""
    print_divider("Test 4: Prevention Question")

    question = "How can I reduce my risk of skin cancer?"

    print(f"Generating answer for: \"{question}\"")
    print("(This will call OpenAI API...)")
    print()

    answer = generator.generate_answer(question, max_results=5)
    print_answer(answer)


def test_formatted_output(generator: AnswerGenerator):
    """Test formatted answer output."""
    print_divider("Test 5: Formatted Output with Citations")

    question = "What are the side effects of chemotherapy?"

    print(f"Generating answer for: \"{question}\"")
    print()

    answer = generator.generate_answer(question, max_results=3)

    print("Formatted Answer (as patient would see it):")
    print_divider()
    print(answer.get_formatted_answer(include_disclaimer=True))
    print_divider()


def test_statistics(generator: AnswerGenerator):
    """Test getting statistics."""
    print_divider("Test 6: Generation Statistics")

    # Generate a few answers
    questions = [
        "What causes pancreatic cancer?",
        "What are symptoms of lung cancer?",
    ]

    print(f"Generating answers for {len(questions)} questions...")
    print()

    for question in questions:
        print(f"  - {question}")
        generator.generate_answer(question, max_results=3)

    print()
    print("Getting cumulative statistics...")
    print()

    stats = generator.get_stats()

    print("LLM Statistics:")
    print(f"  Total calls: {stats['llm']['total_calls']}")
    print(f"  Total tokens: {stats['llm']['total_tokens']:,}")
    print(f"  Input tokens: {stats['llm']['total_input_tokens']:,}")
    print(f"  Output tokens: {stats['llm']['total_output_tokens']:,}")
    print(f"  Total cost: ${stats['llm']['total_cost']:.6f}")
    print(f"  Avg cost per call: ${stats['llm']['avg_cost_per_call']:.6f}")
    print()

    print("Retrieval Statistics:")
    print(f"  Total tokens: {stats['retrieval'].get('total_tokens_used', 0):,}")
    print(f"  Total cost: ${stats['retrieval'].get('total_cost', 0):.6f}")
    print()

    print(f"Total System Cost: ${stats['total_cost']:.6f}")


def main():
    """Main test function."""
    print()
    print("=" * 70)
    print("Answer Generator Test - Full RAG System")
    print("=" * 70)
    print()
    print("⚠️  WARNING: This script makes real OpenAI API calls!")
    print("   Estimated cost for all tests: ~$0.002-0.005 (less than 1 cent)")
    print()

    # Check for API key
    import os
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY not found in environment")
        print("   Please set your OpenAI API key:")
        print("   export OPENAI_API_KEY='your-key-here'")
        return

    # Initialize generator
    print("Initializing answer generator...")
    try:
        generator = AnswerGenerator()
        print("✅ Answer generator initialized")
        print()

        # Show configuration
        config = generator.get_config_dict()
        print("Configuration:")
        print(f"  Model: {config['model']}")
        print(f"  Max tokens: {config['max_tokens']}")
        print(f"  Temperature: {config['temperature']}")
        print(f"  Max context chunks: {config['max_context_chunks']}")
        print(f"  Require citations: {config['require_citations']}")
        print()

    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        import traceback
        traceback.print_exc()
        return

    # Run tests
    try:
        test_basic_question(generator)
        test_filtered_question(generator)
        test_diagnostic_question(generator)
        test_prevention_question(generator)
        test_formatted_output(generator)
        test_statistics(generator)

        # Final summary
        print_divider("Summary")
        print("✅ All answer generation tests completed successfully!")
        print()

        final_stats = generator.get_stats()
        print("Final Cost Summary:")
        print(f"  LLM cost: ${final_stats['llm']['total_cost']:.6f}")
        print(f"  Retrieval cost: ${final_stats['retrieval'].get('total_cost', 0):.6f}")
        print(f"  Total cost: ${final_stats['total_cost']:.6f}")
        print()
        print("Key Features Demonstrated:")
        print("  1. ✅ End-to-end RAG pipeline working")
        print("  2. ✅ Context retrieval from vector database")
        print("  3. ✅ LLM answer generation with citations")
        print("  4. ✅ Metadata filtering (cancer type)")
        print("  5. ✅ Cost tracking")
        print("  6. ✅ Formatted output with disclaimers")
        print()
        print("Next Steps:")
        print("  - Add Redis caching (Checkpoint 2.3)")
        print("  - Build REST API (Checkpoint 2.4)")
        print("  - Deploy system")
        print()

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
