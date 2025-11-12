"""Tests for performance monitoring functionality."""

import time
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from src.api.performance import (
    PerformanceMonitor,
    RequestMetrics,
    get_performance_monitor,
)


@pytest.fixture
def monitor():
    """Create a fresh PerformanceMonitor instance."""
    return PerformanceMonitor(max_history=100)


class TestRequestMetrics:
    """Tests for RequestMetrics dataclass."""

    def test_request_metrics_creation(self):
        """Test creating RequestMetrics instance."""
        timestamp = datetime.now()
        metrics = RequestMetrics(
            endpoint="/api/v1/ask",
            method="POST",
            status_code=200,
            duration_ms=150.5,
            cached=True,
            tokens_used=500,
            cost=0.001,
            timestamp=timestamp,
        )

        assert metrics.endpoint == "/api/v1/ask"
        assert metrics.method == "POST"
        assert metrics.status_code == 200
        assert metrics.duration_ms == 150.5
        assert metrics.cached is True
        assert metrics.tokens_used == 500
        assert metrics.cost == 0.001
        assert metrics.timestamp == timestamp


class TestPerformanceMonitor:
    """Tests for PerformanceMonitor class."""

    def test_monitor_initialization(self, monitor):
        """Test monitor initializes with correct defaults."""
        assert monitor.max_history == 100
        assert monitor.total_requests == 0
        assert monitor.total_errors == 0
        assert monitor.total_duration_ms == 0.0
        assert monitor.total_tokens == 0
        assert monitor.total_cost == 0.0
        assert monitor.cache_hits == 0
        assert monitor.cache_misses == 0
        assert len(monitor.endpoint_metrics) == 0
        assert len(monitor.request_history) == 0

    def test_record_request_basic(self, monitor):
        """Test recording a basic request."""
        monitor.record_request(
            endpoint="/api/v1/ask",
            method="POST",
            status_code=200,
            duration_ms=100.0,
            cached=False,
            tokens_used=500,
            cost=0.001,
        )

        assert monitor.total_requests == 1
        assert monitor.total_duration_ms == 100.0
        assert monitor.total_tokens == 500
        assert monitor.total_cost == 0.001
        assert monitor.cache_misses == 1
        assert monitor.cache_hits == 0
        assert len(monitor.request_history) == 1

    def test_record_request_cached(self, monitor):
        """Test recording a cached request."""
        monitor.record_request(
            endpoint="/api/v1/ask",
            method="POST",
            status_code=200,
            duration_ms=50.0,
            cached=True,
        )

        assert monitor.cache_hits == 1
        assert monitor.cache_misses == 0

    def test_record_request_error(self, monitor):
        """Test recording a request with error status code."""
        monitor.record_request(
            endpoint="/api/v1/ask",
            method="POST",
            status_code=500,
            duration_ms=100.0,
        )

        assert monitor.total_errors == 1

    def test_record_multiple_requests(self, monitor):
        """Test recording multiple requests."""
        # Record 5 successful requests
        for i in range(5):
            monitor.record_request(
                endpoint="/api/v1/ask",
                method="POST",
                status_code=200,
                duration_ms=100.0 + i * 10,
                tokens_used=500,
                cost=0.001,
            )

        assert monitor.total_requests == 5
        assert monitor.total_duration_ms == 600.0  # 100 + 110 + 120 + 130 + 140
        assert monitor.total_tokens == 2500
        assert monitor.total_cost == 0.005

    def test_endpoint_metrics_tracking(self, monitor):
        """Test endpoint-specific metrics tracking."""
        # Record requests to different endpoints
        monitor.record_request("/api/v1/ask", "POST", 200, 100.0)
        monitor.record_request("/api/v1/ask", "POST", 200, 150.0)
        monitor.record_request("/health", "GET", 200, 10.0)

        assert len(monitor.endpoint_metrics) == 2
        assert "/api/v1/ask" in monitor.endpoint_metrics
        assert "/health" in monitor.endpoint_metrics

        ask_metrics = monitor.endpoint_metrics["/api/v1/ask"]
        assert ask_metrics["count"] == 2
        assert ask_metrics["total_duration_ms"] == 250.0
        assert ask_metrics["min_duration_ms"] == 100.0
        assert ask_metrics["max_duration_ms"] == 150.0

    def test_get_summary(self, monitor):
        """Test get_summary returns correct metrics."""
        # Record some requests
        monitor.record_request("/api/v1/ask", "POST", 200, 100.0, cached=False)
        monitor.record_request("/api/v1/ask", "POST", 200, 200.0, cached=True)
        monitor.record_request("/api/v1/ask", "POST", 500, 150.0, cached=False)

        summary = monitor.get_summary()

        assert summary["total_requests"] == 3
        assert summary["total_errors"] == 1
        assert summary["error_rate"] == 1 / 3
        assert summary["average_response_time_ms"] == 150.0  # (100 + 200 + 150) / 3
        assert summary["cache"]["hits"] == 1
        assert summary["cache"]["misses"] == 2
        assert summary["cache"]["hit_rate"] == 1 / 3
        assert "uptime_seconds" in summary
        assert "requests_per_second" in summary

    def test_get_summary_empty(self, monitor):
        """Test get_summary with no requests."""
        summary = monitor.get_summary()

        assert summary["total_requests"] == 0
        assert summary["total_errors"] == 0
        assert summary["error_rate"] == 0.0
        assert summary["average_response_time_ms"] == 0.0
        assert summary["cache"]["hit_rate"] == 0.0

    def test_get_endpoint_metrics(self, monitor):
        """Test get_endpoint_metrics returns correct data."""
        # Record requests to multiple endpoints
        monitor.record_request("/api/v1/ask", "POST", 200, 100.0, cached=False)
        monitor.record_request("/api/v1/ask", "POST", 200, 200.0, cached=True)
        monitor.record_request("/health", "GET", 200, 10.0, cached=False)
        monitor.record_request("/api/v1/ask", "POST", 500, 150.0, cached=False)

        endpoint_metrics = monitor.get_endpoint_metrics()

        assert len(endpoint_metrics) == 2

        ask_metrics = endpoint_metrics["/api/v1/ask"]
        assert ask_metrics["request_count"] == 3
        assert ask_metrics["average_duration_ms"] == 150.0  # (100 + 200 + 150) / 3
        assert ask_metrics["min_duration_ms"] == 100.0
        assert ask_metrics["max_duration_ms"] == 200.0
        assert ask_metrics["errors"] == 1
        assert ask_metrics["error_rate"] == 1 / 3
        assert ask_metrics["cache_hit_rate"] == 1 / 3

        health_metrics = endpoint_metrics["/health"]
        assert health_metrics["request_count"] == 1
        assert health_metrics["errors"] == 0

    def test_get_percentiles(self, monitor):
        """Test percentile calculations."""
        # Record requests with known durations
        durations = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        for duration in durations:
            monitor.record_request("/test", "GET", 200, duration)

        percentiles = monitor.get_percentiles([50, 90, 95, 99])

        # With 10 values, p50 should be around 50-60, p90 around 90-100
        assert 40.0 <= percentiles["p50"] <= 60.0
        assert 80.0 <= percentiles["p90"] <= 100.0
        assert 90.0 <= percentiles["p95"] <= 100.0
        assert 90.0 <= percentiles["p99"] <= 100.0

    def test_get_percentiles_empty(self, monitor):
        """Test percentiles with no data."""
        percentiles = monitor.get_percentiles([50, 90, 95, 99])

        assert percentiles["p50"] == 0.0
        assert percentiles["p90"] == 0.0
        assert percentiles["p95"] == 0.0
        assert percentiles["p99"] == 0.0

    def test_get_recent_requests(self, monitor):
        """Test getting recent requests."""
        # Record 5 requests
        for i in range(5):
            monitor.record_request(f"/test{i}", "GET", 200, 100.0)

        recent = monitor.get_recent_requests(limit=3)

        assert len(recent) == 3
        # Should return the last 3 requests (test2, test3, test4)
        assert recent[0]["endpoint"] == "/test2"
        assert recent[1]["endpoint"] == "/test3"
        assert recent[2]["endpoint"] == "/test4"

    def test_get_recent_requests_all(self, monitor):
        """Test getting all recent requests when limit is larger."""
        # Record 3 requests
        for i in range(3):
            monitor.record_request(f"/test{i}", "GET", 200, 100.0)

        recent = monitor.get_recent_requests(limit=10)

        assert len(recent) == 3

    def test_history_max_size(self):
        """Test that history respects max_history limit."""
        monitor = PerformanceMonitor(max_history=5)

        # Record 10 requests
        for i in range(10):
            monitor.record_request(f"/test{i}", "GET", 200, 100.0)

        # Should only keep last 5
        assert len(monitor.request_history) == 5
        # But total_requests should still be 10
        assert monitor.total_requests == 10

    def test_reset(self, monitor):
        """Test reset clears all metrics."""
        # Record some requests
        monitor.record_request("/api/v1/ask", "POST", 200, 100.0)
        monitor.record_request("/health", "GET", 200, 10.0)

        # Reset
        monitor.reset()

        assert monitor.total_requests == 0
        assert monitor.total_errors == 0
        assert monitor.total_duration_ms == 0.0
        assert monitor.total_tokens == 0
        assert monitor.total_cost == 0.0
        assert monitor.cache_hits == 0
        assert monitor.cache_misses == 0
        assert len(monitor.endpoint_metrics) == 0
        assert len(monitor.request_history) == 0


class TestPerformanceMonitorGlobal:
    """Tests for global performance monitor singleton."""

    def test_get_performance_monitor(self):
        """Test getting global performance monitor."""
        monitor1 = get_performance_monitor()
        monitor2 = get_performance_monitor()

        # Should return the same instance
        assert monitor1 is monitor2

    def test_global_monitor_persistence(self):
        """Test that global monitor persists data."""
        monitor = get_performance_monitor()

        # Reset first to ensure clean state
        monitor.reset()

        # Record a request
        monitor.record_request("/test", "GET", 200, 100.0)

        # Get monitor again
        monitor2 = get_performance_monitor()

        # Should have the same data
        assert monitor2.total_requests == 1
