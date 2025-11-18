"""
Quick test script to verify evaluation setup with 2 sample questions.

This script tests the evaluation pipeline with just 2 questions before running
the full evaluation on all 36 questions.
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file in evaluation directory
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"Loaded environment variables from {env_path}")

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from evaluation.evaluate_rag import RAGEvaluator


def create_sample_test_file():
    """Create a small test file with just 2 questions."""
    sample_file = Path(__file__).parent / "test_questions_sample.json"

    # Load full test file
    with open(Path(__file__).parent / "test_questions.json", "r") as f:
        full_data = json.load(f)

    # Take first 2 questions (one from breast, one from lung)
    sample_data = full_data[:2]  # Just first 2 questions

    # Save sample
    with open(sample_file, "w") as f:
        json.dump(sample_data, f, indent=2)

    return sample_file


def main():
    """Run sample evaluation test."""
    print("=" * 70)
    print("Testing RAG Evaluation Setup (2 Sample Questions)")
    print("=" * 70)
    print()

    # Check OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY environment variable not set")
        print("Please set it before running evaluation:")
        print("  export OPENAI_API_KEY='your-key-here'")
        sys.exit(1)

    # Create sample test file
    print("Creating sample test file with 2 questions...")
    sample_file = create_sample_test_file()
    print(f"Sample file created: {sample_file}")
    print()

    # Run evaluation
    evaluator = RAGEvaluator(api_url="http://localhost:8000")

    output_file = Path(__file__).parent / "results" / "test_sample_results.csv"

    results = evaluator.run_evaluation(
        test_file=sample_file,
        output_file=output_file
    )

    if results is not None:
        print()
        print("=" * 70)
        print("SAMPLE TEST SUCCESSFUL!")
        print("=" * 70)
        print("The evaluation pipeline is working correctly.")
        print("You can now run the full evaluation with:")
        print("  python evaluation/evaluate_rag.py")
        print()
    else:
        print()
        print("=" * 70)
        print("SAMPLE TEST FAILED")
        print("=" * 70)
        print("Please check the error messages above and fix issues before")
        print("running the full evaluation.")
        sys.exit(1)


if __name__ == "__main__":
    main()
