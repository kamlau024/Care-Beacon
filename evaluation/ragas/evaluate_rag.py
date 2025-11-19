"""
RAG Evaluation Script using Ragas

This script evaluates the Care-Beacon RAG system using the ragas framework.
It loads test questions from test_questions.json, queries the RAG API,
and evaluates the responses using multiple metrics.

Metrics evaluated:
- Faithfulness: How factually accurate is the answer based on the retrieved context?
- Answer Relevancy: How relevant is the answer to the question?
- Context Precision: How relevant are the retrieved contexts?
- Context Recall: How well do the retrieved contexts cover the ground truth?

Usage:
    python evaluation/evaluate_rag.py [--api-url http://localhost:8000] [--output results.csv]
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

import requests
import pandas as pd
from tqdm import tqdm
from dotenv import load_dotenv

# Load environment variables from project root .env file
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"Loaded environment variables from {env_path}")

# Add project root to path for imports
sys.path.insert(0, str(project_root))

try:
    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import (
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
    )
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
except ImportError as e:
    print(f"Error: Missing required dependencies. Please install them first:")
    print("  pip install ragas datasets langchain-openai")
    print(f"\nOriginal error: {e}")
    sys.exit(1)


class RAGEvaluator:
    """Evaluate RAG system performance using ragas metrics."""

    def __init__(self, api_url: str = "http://localhost:8000", openai_api_key: str | None = None):
        """Initialize evaluator.

        Args:
            api_url: Base URL of Care-Beacon API
            openai_api_key: OpenAI API key for ragas evaluation (uses env var if not provided)
        """
        self.api_url = api_url.rstrip("/")
        self.ask_endpoint = f"{self.api_url}/api/v1/ask"

        # Set up OpenAI API key for ragas
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError("OpenAI API key required for ragas evaluation. Set OPENAI_API_KEY env var.")

        # Initialize ragas evaluator models
        # Using GPT-4o-mini for cost-effective evaluation
        self.eval_llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            api_key=self.openai_api_key
        )
        self.eval_embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=self.openai_api_key
        )

    def load_test_questions(self, test_file: Path) -> List[Dict[str, Any]]:
        """Load test questions from JSON file.

        Args:
            test_file: Path to test_questions.json

        Returns:
            List of test question dictionaries
        """
        with open(test_file, "r") as f:
            data = json.load(f)
        # Handle both formats: array of questions or {metadata, questions} dict
        if isinstance(data, list):
            return data
        else:
            return data.get("questions", [])

    def query_rag_api(self, question: str, source: str | None = None) -> Dict[str, Any]:
        """Query the RAG API with a question.

        Args:
            question: User question
            source: Optional source filter (e.g., "BC Cancer")

        Returns:
            API response dictionary
        """
        payload = {
            "question": question,
            "max_results": 5,  # Use default
            # Don't pass min_similarity - use config default (0.7)
            "include_full_text": True,  # Request full text for ragas evaluation
        }

        if source:
            payload["source"] = source

        try:
            response = requests.post(
                self.ask_endpoint,
                json=payload,
                timeout=60,  # 60 second timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error querying API: {e}")
            return None

    def prepare_ragas_dataset(
        self,
        test_questions: List[Dict[str, Any]],
        api_responses: List[Dict[str, Any]]
    ) -> Dataset:
        """Prepare dataset in ragas format.

        Ragas expects:
        - question: The user question
        - answer: The generated answer
        - contexts: List of retrieved context strings
        - ground_truth: Reference answer (optional, for context_recall)

        Args:
            test_questions: List of test questions with ground truth
            api_responses: List of API responses

        Returns:
            Dataset ready for ragas evaluation
        """
        data = {
            "question": [],
            "answer": [],
            "contexts": [],
            "ground_truth": [],
        }

        for test_q, response in zip(test_questions, api_responses):
            if response is None:
                continue

            # Extract question and answer
            data["question"].append(test_q["question"])
            data["answer"].append(response["answer"])

            # Extract contexts from sources (retrieved chunks)
            # Use full_text if available (for evaluation), otherwise fall back to text_excerpt
            contexts = [source.get("full_text") or source.get("text_excerpt", "") for source in response.get("sources", [])]
            data["contexts"].append(contexts)

            # Add ground truth
            data["ground_truth"].append(test_q["ground_truth"])

        return Dataset.from_dict(data)

    def run_evaluation(
        self,
        test_file: Path,
        output_file: Path | None = None,
        detailed_output: bool = True
    ) -> pd.DataFrame:
        """Run full evaluation pipeline.

        Args:
            test_file: Path to test_questions.json
            output_file: Optional path to save results CSV
            detailed_output: If True, save detailed per-question results

        Returns:
            DataFrame with evaluation results
        """
        print("=" * 70)
        print("Care-Beacon RAG Evaluation with Ragas")
        print("=" * 70)
        print(f"Test file: {test_file}")
        print(f"API URL: {self.api_url}")
        print()

        # Load test questions
        print("Loading test questions...")
        test_questions = self.load_test_questions(test_file)
        print(f"Loaded {len(test_questions)} test questions")
        print()

        # Query RAG API for each question
        print("Querying RAG API...")
        api_responses = []
        failed_queries = []

        for i, test_q in enumerate(tqdm(test_questions, desc="Querying API")):
            response = self.query_rag_api(
                question=test_q["question"],
                source=test_q.get("expected_source")
            )
            api_responses.append(response)

            if response is None:
                failed_queries.append(i)

            # Rate limiting - avoid overwhelming API
            time.sleep(0.5)

        if failed_queries:
            print(f"\nWarning: {len(failed_queries)} queries failed:")
            for idx in failed_queries:
                print(f"  - {test_questions[idx]['id']}: {test_questions[idx]['question']}")
        print()

        # Prepare dataset for ragas
        print("Preparing dataset for ragas evaluation...")
        dataset = self.prepare_ragas_dataset(test_questions, api_responses)
        print(f"Dataset size: {len(dataset)} samples")

        # Check if dataset is empty
        if len(dataset) == 0:
            print("\n" + "=" * 70)
            print("ERROR: Dataset is empty - no valid samples to evaluate")
            print("=" * 70)
            print("\nPossible causes:")
            print("1. All API requests failed")
            print("2. All API responses have empty sources (no chunks passed min_similarity threshold)")
            print("\nDiagnostics:")

            # Count successful vs failed responses
            successful_responses = [r for r in api_responses if r is not None]
            print(f"  - Total questions: {len(test_questions)}")
            print(f"  - Successful API responses: {len(successful_responses)}")
            print(f"  - Failed API responses: {len(api_responses) - len(successful_responses)}")

            # Check if successful responses have sources
            if successful_responses:
                empty_sources = sum(1 for r in successful_responses if len(r.get("sources", [])) == 0)
                print(f"  - Responses with empty sources: {empty_sources} / {len(successful_responses)}")

                if empty_sources == len(successful_responses):
                    print("\n⚠️  All responses have empty sources!")
                    print("This suggests the min_similarity threshold (0.7) is filtering out all chunks.")
                    print("\nRecommendations:")
                    print("1. Check API logs to see retrieval scores")
                    print("2. Consider lowering min_similarity_threshold in config.yaml (e.g., 0.5 or 0.6)")
                    print("3. Ensure vector database has relevant content for test questions")

            print()
            return None

        print()

        # Run ragas evaluation
        print("Running ragas evaluation...")
        print("Metrics: faithfulness, answer_relevancy, context_precision, context_recall")
        print()

        try:
            result = evaluate(
                dataset,
                metrics=[
                    faithfulness,
                    answer_relevancy,
                    context_precision,
                    context_recall,
                ],
                llm=self.eval_llm,
                embeddings=self.eval_embeddings,
            )

            print("Evaluation complete!")
            print()

            # Convert results to DataFrame
            results_df = result.to_pandas()

            # Add metadata from test questions
            metadata_cols = []
            for i, test_q in enumerate(test_questions):
                if i < len(results_df):  # Only add metadata for successful evaluations
                    metadata_cols.append({
                        "question_id": test_q.get("id", f"Q{i+1}"),
                        "cancer_type": test_q.get("cancer_type", "N/A"),
                        "question_type": test_q.get("question_type", "N/A"),
                        "difficulty": test_q.get("difficulty", "N/A"),
                        "expected_source": test_q.get("expected_source", ""),
                    })

            if metadata_cols:
                metadata_df = pd.DataFrame(metadata_cols)
                results_df = pd.concat([metadata_df, results_df], axis=1)

            # Print summary statistics
            print("=" * 70)
            print("EVALUATION RESULTS SUMMARY")
            print("=" * 70)
            print()
            print("Overall Metrics (Mean ± Std):")
            print("-" * 70)
            for metric in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
                if metric in results_df.columns:
                    mean = results_df[metric].mean()
                    std = results_df[metric].std()
                    print(f"  {metric:20s}: {mean:.3f} ± {std:.3f}")
            print()

            # Breakdown by cancer type
            if "cancer_type" in results_df.columns:
                print("Breakdown by Cancer Type:")
                print("-" * 70)
                for cancer_type in results_df["cancer_type"].unique():
                    subset = results_df[results_df["cancer_type"] == cancer_type]
                    print(f"\n  {cancer_type}:")
                    for metric in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
                        if metric in subset.columns:
                            mean = subset[metric].mean()
                            print(f"    {metric:20s}: {mean:.3f}")
            print()

            # Breakdown by question type
            if "question_type" in results_df.columns:
                print("Breakdown by Question Type:")
                print("-" * 70)
                for q_type in results_df["question_type"].unique():
                    subset = results_df[results_df["question_type"] == q_type]
                    print(f"\n  {q_type}:")
                    for metric in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
                        if metric in subset.columns:
                            mean = subset[metric].mean()
                            print(f"    {metric:20s}: {mean:.3f}")
            print()

            # Save results
            if output_file:
                results_df.to_csv(output_file, index=False)
                print(f"Results saved to: {output_file}")
                print()

                # Also save a summary report
                summary_file = output_file.parent / f"{output_file.stem}_summary.txt"
                with open(summary_file, "w") as f:
                    f.write("Care-Beacon RAG Evaluation Summary\n")
                    f.write("=" * 70 + "\n")
                    f.write(f"Date: {datetime.now().isoformat()}\n")
                    f.write(f"Test file: {test_file}\n")
                    f.write(f"Total questions: {len(test_questions)}\n")
                    f.write(f"Successful evaluations: {len(results_df)}\n")
                    f.write(f"Failed queries: {len(failed_queries)}\n")
                    f.write("\n")
                    f.write("Overall Metrics:\n")
                    f.write("-" * 70 + "\n")
                    for metric in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
                        if metric in results_df.columns:
                            mean = results_df[metric].mean()
                            std = results_df[metric].std()
                            f.write(f"  {metric:20s}: {mean:.3f} ± {std:.3f}\n")

                print(f"Summary report saved to: {summary_file}")
                print()

            return results_df

        except Exception as e:
            print(f"Error during ragas evaluation: {e}")
            import traceback
            traceback.print_exc()
            return None


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Evaluate Care-Beacon RAG system using ragas"
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default="http://localhost:8000",
        help="Base URL of Care-Beacon API (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--test-file",
        type=Path,
        default=Path(__file__).parent / "test_questions.json",
        help="Path to test questions JSON file"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent / "results" / f"evaluation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        help="Path to save evaluation results CSV"
    )
    parser.add_argument(
        "--openai-api-key",
        type=str,
        default=None,
        help="OpenAI API key for ragas (uses OPENAI_API_KEY env var if not provided)"
    )

    args = parser.parse_args()

    # Create output directory if needed
    args.output.parent.mkdir(parents=True, exist_ok=True)

    # Run evaluation
    evaluator = RAGEvaluator(
        api_url=args.api_url,
        openai_api_key=args.openai_api_key
    )

    results = evaluator.run_evaluation(
        test_file=args.test_file,
        output_file=args.output
    )

    if results is not None:
        print("=" * 70)
        print("Evaluation completed successfully!")
        print("=" * 70)
    else:
        print("Evaluation failed. Check logs for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
