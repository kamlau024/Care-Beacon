"""Profile the RAG pipeline to identify performance bottlenecks.

This script profiles individual components of the RAG pipeline:
- Vector database search
- LLM generation
- Cache operations
- Embedding generation

It helps identify which components are taking the most time and where
optimizations can be made.
"""

import argparse
import time
import statistics
from typing import List, Dict, Tuple
from datetime import datetime

from src.generation.answer_generator import AnswerGenerator
from src.config_loader import get_config


class RAGProfiler:
    """Profile RAG pipeline components."""

    def __init__(self):
        """Initialize profiler with answer generator."""
        self.generator = AnswerGenerator()
        self.config = get_config()

    def profile_component(self, name: str, func, *args, **kwargs) -> Tuple[float, any]:
        """Profile a single component execution.

        Args:
            name: Component name
            func: Function to profile
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Tuple of (duration_ms, result)
        """
        start_time = time.time()
        result = func(*args, **kwargs)
        duration_ms = (time.time() - start_time) * 1000
        return duration_ms, result

    def profile_full_pipeline(
        self, question: str, iterations: int = 5
    ) -> Dict:
        """Profile the full RAG pipeline with detailed component timing.

        Args:
            question: Question to process
            iterations: Number of iterations for averaging

        Returns:
            Dictionary with profiling results
        """
        print(f"\nProfiling question: '{question}'")
        print(f"Iterations: {iterations}")
        print("-" * 60)

        total_times = []
        retrieval_times = []
        generation_times = []
        cache_check_times = []

        for i in range(iterations):
            print(f"Iteration {i + 1}/{iterations}...", end=" ")

            # Profile full pipeline
            start_time = time.time()

            # Check cache first
            cache_start = time.time()
            cache_key = self.generator._get_cache_key(question, None, 5, None)
            cached_result = self.generator.cache.get(cache_key)
            cache_time = (time.time() - cache_start) * 1000
            cache_check_times.append(cache_time)

            if cached_result:
                total_time = (time.time() - start_time) * 1000
                total_times.append(total_time)
                retrieval_times.append(0)
                generation_times.append(0)
                print(f"{total_time:.0f}ms (cached)")
                continue

            # Profile retrieval
            retrieval_start = time.time()
            results = self.generator.retrieval_engine.search(
                query=question,
                top_k=5,
                filters=None,
            )
            retrieval_time = (time.time() - retrieval_start) * 1000
            retrieval_times.append(retrieval_time)

            # Profile generation
            generation_start = time.time()
            answer = self.generator.llm_client.generate_answer(
                query=question,
                retrieved_contexts=results,
            )
            generation_time = (time.time() - generation_start) * 1000
            generation_times.append(generation_time)

            total_time = (time.time() - start_time) * 1000
            total_times.append(total_time)

            print(f"{total_time:.0f}ms (uncached)")

        # Calculate statistics
        cache_check_only = [t for t, r in zip(total_times, retrieval_times) if r == 0]
        full_pipeline_only = [t for t, r in zip(total_times, retrieval_times) if r > 0]

        results = {
            "question": question,
            "iterations": iterations,
            "cache_check": {
                "mean_ms": statistics.mean(cache_check_times) if cache_check_times else 0,
                "median_ms": statistics.median(cache_check_times) if cache_check_times else 0,
                "count": len(cache_check_only),
            },
            "retrieval": {
                "mean_ms": statistics.mean([t for t in retrieval_times if t > 0]) if any(t > 0 for t in retrieval_times) else 0,
                "median_ms": statistics.median([t for t in retrieval_times if t > 0]) if any(t > 0 for t in retrieval_times) else 0,
                "count": len([t for t in retrieval_times if t > 0]),
            },
            "generation": {
                "mean_ms": statistics.mean([t for t in generation_times if t > 0]) if any(t > 0 for t in generation_times) else 0,
                "median_ms": statistics.median([t for t in generation_times if t > 0]) if any(t > 0 for t in generation_times) else 0,
                "count": len([t for t in generation_times if t > 0]),
            },
            "total_cached": {
                "mean_ms": statistics.mean(cache_check_only) if cache_check_only else 0,
                "median_ms": statistics.median(cache_check_only) if cache_check_only else 0,
                "count": len(cache_check_only),
            },
            "total_uncached": {
                "mean_ms": statistics.mean(full_pipeline_only) if full_pipeline_only else 0,
                "median_ms": statistics.median(full_pipeline_only) if full_pipeline_only else 0,
                "count": len(full_pipeline_only),
            },
        }

        return results

    def profile_cache_operations(self, iterations: int = 100) -> Dict:
        """Profile cache read/write performance.

        Args:
            iterations: Number of iterations

        Returns:
            Dictionary with cache profiling results
        """
        print(f"\nProfiling cache operations ({iterations} iterations)...")
        print("-" * 60)

        write_times = []
        read_times = []
        test_key = "test_profile_key"
        test_value = {"data": "test" * 100}  # Moderate size object

        for i in range(iterations):
            # Profile write
            start = time.time()
            self.generator.cache.set(test_key, test_value, ttl=60)
            write_times.append((time.time() - start) * 1000)

            # Profile read
            start = time.time()
            self.generator.cache.get(test_key)
            read_times.append((time.time() - start) * 1000)

            if (i + 1) % 20 == 0:
                print(f"Completed {i + 1}/{iterations} iterations")

        # Clean up
        self.generator.cache.delete(test_key)

        return {
            "iterations": iterations,
            "write": {
                "mean_ms": statistics.mean(write_times),
                "median_ms": statistics.median(write_times),
                "min_ms": min(write_times),
                "max_ms": max(write_times),
                "p95_ms": self._percentile(write_times, 95),
            },
            "read": {
                "mean_ms": statistics.mean(read_times),
                "median_ms": statistics.median(read_times),
                "min_ms": min(read_times),
                "max_ms": max(read_times),
                "p95_ms": self._percentile(read_times, 95),
            },
        }

    def profile_vector_search(self, query: str, iterations: int = 50) -> Dict:
        """Profile vector database search performance.

        Args:
            query: Search query
            iterations: Number of iterations

        Returns:
            Dictionary with search profiling results
        """
        print(f"\nProfiling vector search ({iterations} iterations)...")
        print(f"Query: '{query}'")
        print("-" * 60)

        search_times = []

        for i in range(iterations):
            start = time.time()
            results = self.generator.retrieval_engine.search(
                query=query,
                top_k=5,
                filters=None,
            )
            search_times.append((time.time() - start) * 1000)

            if (i + 1) % 10 == 0:
                print(f"Completed {i + 1}/{iterations} iterations")

        return {
            "iterations": iterations,
            "query": query,
            "results_per_query": len(results) if results else 0,
            "search_time": {
                "mean_ms": statistics.mean(search_times),
                "median_ms": statistics.median(search_times),
                "min_ms": min(search_times),
                "max_ms": max(search_times),
                "p95_ms": self._percentile(search_times, 95),
                "p99_ms": self._percentile(search_times, 99),
            },
        }

    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile.

        Args:
            data: List of values
            percentile: Percentile (0-100)

        Returns:
            Percentile value
        """
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int((percentile / 100.0) * len(sorted_data))
        index = min(index, len(sorted_data) - 1)
        return sorted_data[index]

    def print_results(self, results: Dict):
        """Print profiling results.

        Args:
            results: Profiling results dictionary
        """
        print("\n" + "=" * 60)
        print("PROFILING RESULTS")
        print("=" * 60)

        if "question" in results:
            # Full pipeline results
            print(f"\nQuestion: {results['question']}")
            print(f"Iterations: {results['iterations']}")

            print(f"\nCache Check:")
            print(f"  Mean:   {results['cache_check']['mean_ms']:.2f}ms")
            print(f"  Median: {results['cache_check']['median_ms']:.2f}ms")
            print(f"  Count:  {results['cache_check']['count']}")

            if results['retrieval']['count'] > 0:
                print(f"\nRetrieval:")
                print(f"  Mean:   {results['retrieval']['mean_ms']:.0f}ms")
                print(f"  Median: {results['retrieval']['median_ms']:.0f}ms")
                print(f"  Count:  {results['retrieval']['count']}")

            if results['generation']['count'] > 0:
                print(f"\nGeneration:")
                print(f"  Mean:   {results['generation']['mean_ms']:.0f}ms")
                print(f"  Median: {results['generation']['median_ms']:.0f}ms")
                print(f"  Count:  {results['generation']['count']}")

            if results['total_cached']['count'] > 0:
                print(f"\nTotal (Cached):")
                print(f"  Mean:   {results['total_cached']['mean_ms']:.0f}ms")
                print(f"  Median: {results['total_cached']['median_ms']:.0f}ms")
                print(f"  Count:  {results['total_cached']['count']}")

            if results['total_uncached']['count'] > 0:
                print(f"\nTotal (Uncached):")
                print(f"  Mean:   {results['total_uncached']['mean_ms']:.0f}ms")
                print(f"  Median: {results['total_uncached']['median_ms']:.0f}ms")
                print(f"  Count:  {results['total_uncached']['count']}")

                # Calculate breakdown
                if results['retrieval']['mean_ms'] > 0 and results['generation']['mean_ms'] > 0:
                    total = results['total_uncached']['mean_ms']
                    retrieval_pct = (results['retrieval']['mean_ms'] / total) * 100
                    generation_pct = (results['generation']['mean_ms'] / total) * 100
                    other_pct = 100 - retrieval_pct - generation_pct

                    print(f"\nTime Breakdown (Uncached):")
                    print(f"  Retrieval:  {retrieval_pct:.1f}% ({results['retrieval']['mean_ms']:.0f}ms)")
                    print(f"  Generation: {generation_pct:.1f}% ({results['generation']['mean_ms']:.0f}ms)")
                    print(f"  Other:      {other_pct:.1f}%")

        elif "write" in results and "read" in results:
            # Cache results
            print(f"\nCache Operations ({results['iterations']} iterations):")

            print(f"\nWrite Performance:")
            w = results['write']
            print(f"  Mean:   {w['mean_ms']:.3f}ms")
            print(f"  Median: {w['median_ms']:.3f}ms")
            print(f"  Min:    {w['min_ms']:.3f}ms")
            print(f"  Max:    {w['max_ms']:.3f}ms")
            print(f"  P95:    {w['p95_ms']:.3f}ms")

            print(f"\nRead Performance:")
            r = results['read']
            print(f"  Mean:   {r['mean_ms']:.3f}ms")
            print(f"  Median: {r['median_ms']:.3f}ms")
            print(f"  Min:    {r['min_ms']:.3f}ms")
            print(f"  Max:    {r['max_ms']:.3f}ms")
            print(f"  P95:    {r['p95_ms']:.3f}ms")

        elif "search_time" in results:
            # Vector search results
            print(f"\nVector Search ({results['iterations']} iterations):")
            print(f"Query: '{results['query']}'")
            print(f"Results per query: {results['results_per_query']}")

            s = results['search_time']
            print(f"\nSearch Performance:")
            print(f"  Mean:   {s['mean_ms']:.0f}ms")
            print(f"  Median: {s['median_ms']:.0f}ms")
            print(f"  Min:    {s['min_ms']:.0f}ms")
            print(f"  Max:    {s['max_ms']:.0f}ms")
            print(f"  P95:    {s['p95_ms']:.0f}ms")
            print(f"  P99:    {s['p99_ms']:.0f}ms")

        print("\n" + "=" * 60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Profile Care-Beacon RAG pipeline performance"
    )
    parser.add_argument(
        "--mode",
        choices=["full", "cache", "search", "all"],
        default="full",
        help="Profiling mode (default: full)",
    )
    parser.add_argument(
        "--question",
        default="What are the symptoms of breast cancer?",
        help="Question for full pipeline profiling",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=5,
        help="Number of iterations (default: 5)",
    )

    args = parser.parse_args()

    profiler = RAGProfiler()

    if args.mode in ["full", "all"]:
        # Clear cache to ensure uncached runs
        profiler.generator.cache.clear_all()
        results = profiler.profile_full_pipeline(args.question, args.iterations)
        profiler.print_results(results)

    if args.mode in ["cache", "all"]:
        results = profiler.profile_cache_operations(iterations=100)
        profiler.print_results(results)

    if args.mode in ["search", "all"]:
        results = profiler.profile_vector_search(args.question, iterations=50)
        profiler.print_results(results)


if __name__ == "__main__":
    main()
