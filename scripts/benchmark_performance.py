"""Performance benchmarking script for Care-Beacon API.

This script tests and measures the performance of the RAG pipeline including:
- Response times (average, median, p95, p99)
- Throughput (requests per second)
- Cache effectiveness (hit rate, cost savings)
- Resource usage patterns
"""

import argparse
import time
import json
import statistics
from typing import List, Dict
from datetime import datetime
import sys
import requests

# Sample test questions for benchmarking
TEST_QUESTIONS = [
    "What are the symptoms of breast cancer?",
    "How is chemotherapy administered?",
    "What are the side effects of radiation therapy?",
    "What is immunotherapy?",
    "How does targeted therapy work?",
    "What are the stages of lung cancer?",
    "What is a mammogram?",
    "How is melanoma diagnosed?",
    "What are the risk factors for colon cancer?",
    "What is palliative care?",
]


class PerformanceBenchmark:
    """Performance benchmarking for Care-Beacon API."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        """Initialize benchmark with API base URL.

        Args:
            base_url: Base URL of the API
        """
        self.base_url = base_url
        self.results: List[Dict] = []

    def check_health(self) -> bool:
        """Check if API is healthy and ready.

        Returns:
            True if API is healthy, False otherwise
        """
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except Exception as e:
            print(f"Health check failed: {e}")
            return False

    def reset_performance_metrics(self):
        """Reset performance metrics before benchmarking."""
        try:
            requests.post(f"{self.base_url}/api/v1/performance/reset", timeout=5)
            print("Performance metrics reset.")
        except Exception as e:
            print(f"Failed to reset performance metrics: {e}")

    def run_single_request(self, question: str) -> Dict:
        """Run a single API request and measure performance.

        Args:
            question: Question to ask

        Returns:
            Dictionary with performance metrics
        """
        start_time = time.time()

        try:
            response = requests.post(
                f"{self.base_url}/api/v1/ask",
                json={"question": question},
                timeout=30,
            )

            duration_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "duration_ms": duration_ms,
                    "status_code": response.status_code,
                    "tokens_used": data["metadata"].get("tokens_used", 0),
                    "cost": data["metadata"].get("cost", 0.0),
                    "cached": data["metadata"].get("cached", False),
                    "sources_count": data["metadata"].get("sources_count", 0),
                    "question": question,
                }
            else:
                return {
                    "success": False,
                    "duration_ms": duration_ms,
                    "status_code": response.status_code,
                    "error": response.text,
                    "question": question,
                }

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return {
                "success": False,
                "duration_ms": duration_ms,
                "error": str(e),
                "question": question,
            }

    def run_sequential_benchmark(
        self, questions: List[str], iterations: int = 1
    ) -> Dict:
        """Run sequential benchmark with list of questions.

        Args:
            questions: List of questions to ask
            iterations: Number of times to repeat the question list

        Returns:
            Dictionary with benchmark results
        """
        print(f"\nRunning sequential benchmark...")
        print(f"Questions: {len(questions)}, Iterations: {iterations}")
        print("-" * 60)

        all_results = []
        start_time = time.time()

        for iteration in range(iterations):
            print(f"Iteration {iteration + 1}/{iterations}")

            for i, question in enumerate(questions):
                result = self.run_single_request(question)
                all_results.append(result)

                if result["success"]:
                    print(
                        f"  [{i+1}/{len(questions)}] "
                        f"{result['duration_ms']:.0f}ms "
                        f"({'cached' if result.get('cached') else 'uncached'})"
                    )
                else:
                    print(f"  [{i+1}/{len(questions)}] FAILED: {result.get('error', 'Unknown error')}")

        total_duration = time.time() - start_time

        # Calculate statistics
        successful_results = [r for r in all_results if r["success"]]
        failed_count = len(all_results) - len(successful_results)

        if not successful_results:
            return {
                "total_requests": len(all_results),
                "successful_requests": 0,
                "failed_requests": failed_count,
                "error": "All requests failed",
            }

        durations = [r["duration_ms"] for r in successful_results]
        costs = [r.get("cost", 0.0) for r in successful_results]
        cached_count = sum(1 for r in successful_results if r.get("cached", False))

        return {
            "total_requests": len(all_results),
            "successful_requests": len(successful_results),
            "failed_requests": failed_count,
            "total_duration_s": total_duration,
            "throughput_rps": len(successful_results) / total_duration,
            "response_times": {
                "mean_ms": statistics.mean(durations),
                "median_ms": statistics.median(durations),
                "min_ms": min(durations),
                "max_ms": max(durations),
                "stdev_ms": statistics.stdev(durations) if len(durations) > 1 else 0,
                "p95_ms": self._percentile(durations, 95),
                "p99_ms": self._percentile(durations, 99),
            },
            "costs": {
                "total_usd": sum(costs),
                "average_usd": statistics.mean(costs) if costs else 0,
            },
            "cache": {
                "hit_count": cached_count,
                "miss_count": len(successful_results) - cached_count,
                "hit_rate": cached_count / len(successful_results) if successful_results else 0,
            },
        }

    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of data.

        Args:
            data: List of values
            percentile: Percentile to calculate (0-100)

        Returns:
            Percentile value
        """
        if not data:
            return 0.0

        sorted_data = sorted(data)
        index = int((percentile / 100.0) * len(sorted_data))
        index = min(index, len(sorted_data) - 1)
        return sorted_data[index]

    def get_api_performance_metrics(self) -> Dict:
        """Get performance metrics from the API.

        Returns:
            Performance metrics from API
        """
        try:
            response = requests.get(f"{self.base_url}/api/v1/performance", timeout=5)
            if response.status_code == 200:
                return response.json()
            return {}
        except Exception as e:
            print(f"Failed to get performance metrics: {e}")
            return {}

    def print_results(self, results: Dict):
        """Print benchmark results in a formatted way.

        Args:
            results: Benchmark results dictionary
        """
        print("\n" + "=" * 60)
        print("BENCHMARK RESULTS")
        print("=" * 60)

        print(f"\nRequests:")
        print(f"  Total:      {results['total_requests']}")
        print(f"  Successful: {results['successful_requests']}")
        print(f"  Failed:     {results['failed_requests']}")

        print(f"\nThroughput:")
        print(f"  Requests/sec: {results['throughput_rps']:.2f}")
        print(f"  Total time:   {results['total_duration_s']:.2f}s")

        rt = results["response_times"]
        print(f"\nResponse Times:")
        print(f"  Mean:   {rt['mean_ms']:.0f}ms")
        print(f"  Median: {rt['median_ms']:.0f}ms")
        print(f"  Min:    {rt['min_ms']:.0f}ms")
        print(f"  Max:    {rt['max_ms']:.0f}ms")
        print(f"  StdDev: {rt['stdev_ms']:.0f}ms")
        print(f"  P95:    {rt['p95_ms']:.0f}ms")
        print(f"  P99:    {rt['p99_ms']:.0f}ms")

        cache = results["cache"]
        print(f"\nCache Performance:")
        print(f"  Hits:     {cache['hit_count']}")
        print(f"  Misses:   {cache['miss_count']}")
        print(f"  Hit Rate: {cache['hit_rate']:.1%}")

        costs = results["costs"]
        print(f"\nCosts:")
        print(f"  Total:   ${costs['total_usd']:.6f}")
        print(f"  Average: ${costs['average_usd']:.6f}")

        print("\n" + "=" * 60)

    def save_results(self, results: Dict, filename: str):
        """Save results to JSON file.

        Args:
            results: Benchmark results
            filename: Output filename
        """
        output = {
            "timestamp": datetime.now().isoformat(),
            "benchmark_results": results,
        }

        with open(filename, "w") as f:
            json.dump(output, f, indent=2)

        print(f"\nResults saved to: {filename}")


def main():
    """Main entry point for benchmark script."""
    parser = argparse.ArgumentParser(
        description="Benchmark Care-Beacon API performance"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="Number of times to repeat question list (default: 1)",
    )
    parser.add_argument(
        "--questions",
        type=int,
        default=10,
        help="Number of questions to use (default: 10, max: 10)",
    )
    parser.add_argument(
        "--output",
        default="benchmark_results.json",
        help="Output JSON file (default: benchmark_results.json)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset performance metrics before benchmarking",
    )

    args = parser.parse_args()

    # Initialize benchmark
    benchmark = PerformanceBenchmark(base_url=args.url)

    # Check API health
    print(f"Checking API health at {args.url}...")
    if not benchmark.check_health():
        print("ERROR: API is not healthy. Please start the API first.")
        sys.exit(1)

    print("API is healthy!")

    # Reset metrics if requested
    if args.reset:
        benchmark.reset_performance_metrics()

    # Select questions
    num_questions = min(args.questions, len(TEST_QUESTIONS))
    questions = TEST_QUESTIONS[:num_questions]

    # Run benchmark
    results = benchmark.run_sequential_benchmark(questions, args.iterations)

    # Print results
    benchmark.print_results(results)

    # Get and print API metrics
    api_metrics = benchmark.get_api_performance_metrics()
    if api_metrics:
        print("\nAPI Performance Metrics:")
        summary = api_metrics.get("summary", {})
        print(f"  Total API requests: {summary.get('total_requests', 0)}")
        print(f"  Average response:   {summary.get('average_response_time_ms', 0):.0f}ms")
        cache_stats = summary.get("cache", {})
        print(f"  Cache hit rate:     {cache_stats.get('hit_rate', 0):.1%}")

    # Save results
    benchmark.save_results(results, args.output)

    print("\nBenchmark complete!")


if __name__ == "__main__":
    main()
