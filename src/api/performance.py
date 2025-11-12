"""Performance monitoring and metrics for the API."""

import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque


@dataclass
class RequestMetrics:
    """Metrics for a single request."""

    endpoint: str
    method: str
    status_code: int
    duration_ms: float
    cached: bool
    tokens_used: int
    cost: float
    timestamp: datetime


class PerformanceMonitor:
    """Monitor and track API performance metrics."""

    def __init__(self, max_history: int = 1000):
        """Initialize performance monitor.

        Args:
            max_history: Maximum number of requests to keep in history
        """
        self.max_history = max_history
        self.request_history: deque = deque(maxlen=max_history)
        self.start_time = time.time()

        # Aggregated metrics
        self.total_requests = 0
        self.total_errors = 0
        self.total_duration_ms = 0.0
        self.total_tokens = 0
        self.total_cost = 0.0
        self.cache_hits = 0
        self.cache_misses = 0

        # Endpoint-specific metrics
        self.endpoint_metrics: Dict[str, Dict] = {}

    def record_request(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        duration_ms: float,
        cached: bool = False,
        tokens_used: int = 0,
        cost: float = 0.0
    ) -> None:
        """Record a request's metrics.

        Args:
            endpoint: API endpoint path
            method: HTTP method
            status_code: Response status code
            duration_ms: Request duration in milliseconds
            cached: Whether response was cached
            tokens_used: Number of LLM tokens used
            cost: Cost in USD
        """
        # Create metrics record
        metrics = RequestMetrics(
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            duration_ms=duration_ms,
            cached=cached,
            tokens_used=tokens_used,
            cost=cost,
            timestamp=datetime.now()
        )

        # Add to history
        self.request_history.append(metrics)

        # Update aggregated metrics
        self.total_requests += 1
        self.total_duration_ms += duration_ms
        self.total_tokens += tokens_used
        self.total_cost += cost

        if cached:
            self.cache_hits += 1
        else:
            self.cache_misses += 1

        if status_code >= 400:
            self.total_errors += 1

        # Update endpoint-specific metrics
        if endpoint not in self.endpoint_metrics:
            self.endpoint_metrics[endpoint] = {
                "count": 0,
                "total_duration_ms": 0.0,
                "min_duration_ms": float('inf'),
                "max_duration_ms": 0.0,
                "errors": 0,
                "cache_hits": 0,
                "cache_misses": 0
            }

        ep_metrics = self.endpoint_metrics[endpoint]
        ep_metrics["count"] += 1
        ep_metrics["total_duration_ms"] += duration_ms
        ep_metrics["min_duration_ms"] = min(ep_metrics["min_duration_ms"], duration_ms)
        ep_metrics["max_duration_ms"] = max(ep_metrics["max_duration_ms"], duration_ms)

        if status_code >= 400:
            ep_metrics["errors"] += 1

        if cached:
            ep_metrics["cache_hits"] += 1
        else:
            ep_metrics["cache_misses"] += 1

    def get_summary(self) -> Dict:
        """Get summary of performance metrics.

        Returns:
            Dictionary containing performance summary
        """
        uptime_seconds = time.time() - self.start_time

        # Calculate averages
        avg_duration_ms = (
            self.total_duration_ms / self.total_requests
            if self.total_requests > 0
            else 0.0
        )

        avg_cost = (
            self.total_cost / self.total_requests
            if self.total_requests > 0
            else 0.0
        )

        cache_hit_rate = (
            self.cache_hits / (self.cache_hits + self.cache_misses)
            if (self.cache_hits + self.cache_misses) > 0
            else 0.0
        )

        error_rate = (
            self.total_errors / self.total_requests
            if self.total_requests > 0
            else 0.0
        )

        requests_per_second = (
            self.total_requests / uptime_seconds
            if uptime_seconds > 0
            else 0.0
        )

        return {
            "uptime_seconds": uptime_seconds,
            "total_requests": self.total_requests,
            "total_errors": self.total_errors,
            "error_rate": error_rate,
            "requests_per_second": requests_per_second,
            "average_response_time_ms": avg_duration_ms,
            "total_tokens_used": self.total_tokens,
            "total_cost_usd": self.total_cost,
            "average_cost_per_request": avg_cost,
            "cache": {
                "hits": self.cache_hits,
                "misses": self.cache_misses,
                "hit_rate": cache_hit_rate,
                "total_queries": self.cache_hits + self.cache_misses
            }
        }

    def get_endpoint_metrics(self) -> Dict:
        """Get metrics broken down by endpoint.

        Returns:
            Dictionary of endpoint-specific metrics
        """
        result = {}

        for endpoint, metrics in self.endpoint_metrics.items():
            count = metrics["count"]
            avg_duration = (
                metrics["total_duration_ms"] / count
                if count > 0
                else 0.0
            )

            cache_rate = (
                metrics["cache_hits"] / (metrics["cache_hits"] + metrics["cache_misses"])
                if (metrics["cache_hits"] + metrics["cache_misses"]) > 0
                else 0.0
            )

            result[endpoint] = {
                "request_count": count,
                "average_duration_ms": avg_duration,
                "min_duration_ms": metrics["min_duration_ms"] if count > 0 else 0.0,
                "max_duration_ms": metrics["max_duration_ms"],
                "errors": metrics["errors"],
                "error_rate": metrics["errors"] / count if count > 0 else 0.0,
                "cache_hit_rate": cache_rate
            }

        return result

    def get_percentiles(self, percentiles: List[int] = [50, 90, 95, 99]) -> Dict:
        """Calculate response time percentiles.

        Args:
            percentiles: List of percentiles to calculate (e.g., [50, 90, 95, 99])

        Returns:
            Dictionary of percentile values
        """
        if not self.request_history:
            return {f"p{p}": 0.0 for p in percentiles}

        # Extract durations and sort
        durations = sorted([r.duration_ms for r in self.request_history])
        n = len(durations)

        result = {}
        for p in percentiles:
            index = int((p / 100.0) * n)
            index = min(index, n - 1)  # Ensure within bounds
            result[f"p{p}"] = durations[index]

        return result

    def get_recent_requests(self, limit: int = 10) -> List[Dict]:
        """Get most recent requests.

        Args:
            limit: Maximum number of requests to return

        Returns:
            List of recent request metrics
        """
        recent = list(self.request_history)[-limit:]

        return [
            {
                "endpoint": r.endpoint,
                "method": r.method,
                "status_code": r.status_code,
                "duration_ms": r.duration_ms,
                "cached": r.cached,
                "tokens_used": r.tokens_used,
                "cost": r.cost,
                "timestamp": r.timestamp.isoformat()
            }
            for r in recent
        ]

    def reset(self) -> None:
        """Reset all metrics."""
        self.request_history.clear()
        self.total_requests = 0
        self.total_errors = 0
        self.total_duration_ms = 0.0
        self.total_tokens = 0
        self.total_cost = 0.0
        self.cache_hits = 0
        self.cache_misses = 0
        self.endpoint_metrics.clear()
        self.start_time = time.time()


# Global performance monitor instance
_performance_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """Get or create the global performance monitor.

    Returns:
        Global PerformanceMonitor instance
    """
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor
