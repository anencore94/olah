# coding=utf-8
# Copyright 2024 XiaHan
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

"""
Unit tests for metrics collection and monitoring functionality.

Tests the MetricsCollector class and related utilities for collecting
HTTP request metrics, system metrics, and cache performance metrics.
"""

import pytest
import time
import threading
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from olah.utils.metrics import (
    MetricsCollector,
    RequestMetrics,
    SystemMetrics,
    CacheMetrics,
    get_metrics_collector,
    record_request_metrics,
    record_cache_hit,
    record_cache_miss,
)


class TestRequestMetrics:
    """Test RequestMetrics dataclass."""
    
    def test_request_metrics_creation(self):
        """Test creating RequestMetrics instance."""
        metrics = RequestMetrics(
            method="GET",
            path="/api/test",
            status_code=200,
            response_time=0.5,
            bytes_sent=1024,
            bytes_received=512
        )
        
        assert metrics.method == "GET"
        assert metrics.path == "/api/test"
        assert metrics.status_code == 200
        assert metrics.response_time == 0.5
        assert metrics.bytes_sent == 1024
        assert metrics.bytes_received == 512
        assert isinstance(metrics.timestamp, datetime)


class TestSystemMetrics:
    """Test SystemMetrics dataclass."""
    
    def test_system_metrics_creation(self):
        """Test creating SystemMetrics instance."""
        metrics = SystemMetrics(
            cpu_percent=25.5,
            memory_percent=60.0,
            disk_usage_percent=45.0,
            disk_read_bytes=1024,
            disk_write_bytes=2048,
            network_bytes_sent=512,
            network_bytes_received=256
        )
        
        assert metrics.cpu_percent == 25.5
        assert metrics.memory_percent == 60.0
        assert metrics.disk_usage_percent == 45.0
        assert metrics.disk_read_bytes == 1024
        assert metrics.disk_write_bytes == 2048
        assert metrics.network_bytes_sent == 512
        assert metrics.network_bytes_received == 256
        assert isinstance(metrics.timestamp, datetime)


class TestCacheMetrics:
    """Test CacheMetrics dataclass."""
    
    def test_cache_metrics_creation(self):
        """Test creating CacheMetrics instance."""
        metrics = CacheMetrics(
            total_requests=100,
            cache_hits=80,
            cache_misses=20,
            cache_size_bytes=1024000,
            cache_files_count=50,
            avg_response_time=0.1
        )
        
        assert metrics.total_requests == 100
        assert metrics.cache_hits == 80
        assert metrics.cache_misses == 20
        assert metrics.cache_size_bytes == 1024000
        assert metrics.cache_files_count == 50
        assert metrics.avg_response_time == 0.1
        assert isinstance(metrics.timestamp, datetime)


class TestMetricsCollector:
    """Test MetricsCollector class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.collector = MetricsCollector(max_history_size=100)
    
    def test_initialization(self):
        """Test MetricsCollector initialization."""
        assert self.collector.max_history_size == 100
        assert len(self.collector.request_history) == 0
        assert len(self.collector.system_history) == 0
        assert len(self.collector.cache_metrics_history) == 0
        assert self.collector.cache_hit_count == 0
        assert self.collector.cache_miss_count == 0
        assert self.collector.total_requests == 0
    
    def test_record_request(self):
        """Test recording HTTP request metrics."""
        metrics = RequestMetrics(
            method="GET",
            path="/api/test",
            status_code=200,
            response_time=0.5,
            bytes_sent=1024,
            bytes_received=512
        )
        
        self.collector.record_request(metrics)
        
        assert len(self.collector.request_history) == 1
        assert self.collector.request_history[0] == metrics
        assert self.collector.request_counts["GET /api/test"] == 1
        assert len(self.collector.response_times["GET /api/test"]) == 1
        assert self.collector.response_times["GET /api/test"][0] == 0.5
        assert self.collector.bytes_transferred["GET /api/test"] == 1536
    
    def test_record_multiple_requests(self):
        """Test recording multiple requests."""
        # Record multiple requests
        for i in range(5):
            metrics = RequestMetrics(
                method="GET",
                path="/api/test",
                status_code=200,
                response_time=0.1 * i,
                bytes_sent=100,
                bytes_received=50
            )
            self.collector.record_request(metrics)
        
        assert len(self.collector.request_history) == 5
        assert self.collector.request_counts["GET /api/test"] == 5
        assert len(self.collector.response_times["GET /api/test"]) == 5
        assert self.collector.bytes_transferred["GET /api/test"] == 750
    
    def test_record_cache_hit(self):
        """Test recording cache hit."""
        self.collector.record_cache_hit()
        
        assert self.collector.cache_hit_count == 1
        assert self.collector.total_requests == 1
        assert self.collector.cache_miss_count == 0
    
    def test_record_cache_miss(self):
        """Test recording cache miss."""
        self.collector.record_cache_miss()
        
        assert self.collector.cache_miss_count == 1
        assert self.collector.total_requests == 1
        assert self.collector.cache_hit_count == 0
    
    def test_record_mixed_cache_events(self):
        """Test recording mixed cache hits and misses."""
        for _ in range(3):
            self.collector.record_cache_hit()
        for _ in range(2):
            self.collector.record_cache_miss()
        
        assert self.collector.cache_hit_count == 3
        assert self.collector.cache_miss_count == 2
        assert self.collector.total_requests == 5
    
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    @patch('psutil.disk_io_counters')
    @patch('psutil.net_io_counters')
    def test_collect_system_metrics(self, mock_net_io, mock_disk_io, mock_disk_usage, 
                                   mock_memory, mock_cpu):
        """Test collecting system metrics."""
        # Mock system metrics
        mock_cpu.return_value = 25.5
        mock_memory.return_value = MagicMock(percent=60.0)
        mock_disk_usage.return_value = MagicMock(used=500, total=1000)
        mock_disk_io.return_value = MagicMock(read_bytes=1024, write_bytes=2048)
        mock_net_io.return_value = MagicMock(bytes_sent=512, bytes_recv=256)
        
        # Collect metrics
        self.collector._collect_system_metrics()
        
        assert len(self.collector.system_history) == 1
        metrics = self.collector.system_history[0]
        assert metrics.cpu_percent == 25.5
        assert metrics.memory_percent == 60.0
        assert metrics.disk_usage_percent == 50.0
    
    def test_get_request_stats_empty(self):
        """Test getting request stats when no requests recorded."""
        stats = self.collector.get_request_stats(60)
        
        assert stats["total_requests"] == 0
        assert stats["avg_response_time"] == 0.0
        assert stats["total_bytes_transferred"] == 0
        assert stats["status_codes"] == {}
        assert stats["endpoints"] == {}
    
    def test_get_request_stats_with_data(self):
        """Test getting request stats with recorded data."""
        # Record some requests
        for i in range(3):
            metrics = RequestMetrics(
                method="GET",
                path="/api/test",
                status_code=200,
                response_time=0.1 * (i + 1),
                bytes_sent=100,
                bytes_received=50
            )
            self.collector.record_request(metrics)
        
        stats = self.collector.get_request_stats(60)
        
        assert stats["total_requests"] == 3
        assert abs(stats["avg_response_time"] - 0.2) < 0.001  # (0.1 + 0.2 + 0.3) / 3
        assert stats["total_bytes_transferred"] == 450  # 3 * 150
        assert stats["status_codes"][200] == 3
        assert "GET /api/test" in stats["endpoints"]
        assert stats["endpoints"]["GET /api/test"]["count"] == 3
    
    def test_get_request_stats_time_window(self):
        """Test getting request stats with time window filtering."""
        # Record old request
        old_metrics = RequestMetrics(
            method="GET",
            path="/api/old",
            status_code=200,
            response_time=0.5,
            bytes_sent=100,
            bytes_received=50
        )
        old_metrics.timestamp = datetime.now() - timedelta(hours=2)
        self.collector.request_history.append(old_metrics)
        
        # Record recent request
        recent_metrics = RequestMetrics(
            method="GET",
            path="/api/recent",
            status_code=200,
            response_time=0.1,
            bytes_sent=100,
            bytes_received=50
        )
        self.collector.record_request(recent_metrics)
        
        # Get stats for last hour (should only include recent request)
        stats = self.collector.get_request_stats(60)
        
        assert stats["total_requests"] == 1
        assert stats["avg_response_time"] == 0.1
        assert "GET /api/recent" in stats["endpoints"]
        assert "GET /api/old" not in stats["endpoints"]
    
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    @patch('psutil.disk_io_counters')
    @patch('psutil.net_io_counters')
    def test_get_system_stats(self, mock_net_io, mock_disk_io, mock_disk_usage, 
                             mock_memory, mock_cpu):
        """Test getting system statistics."""
        # Mock system metrics
        mock_cpu.return_value = 25.5
        mock_memory.return_value = MagicMock(percent=60.0)
        mock_disk_usage.return_value = MagicMock(used=500, total=1000)
        mock_disk_io.return_value = MagicMock(read_bytes=1024, write_bytes=2048)
        mock_net_io.return_value = MagicMock(bytes_sent=512, bytes_recv=256)
        
        # Collect metrics
        self.collector._collect_system_metrics()
        
        stats = self.collector.get_system_stats()
        
        assert "cpu_percent" in stats
        assert "memory_percent" in stats
        assert "disk_usage_percent" in stats
        assert "disk_io" in stats
        assert "network_io" in stats
    
    def test_get_cache_stats(self):
        """Test getting cache statistics."""
        # Record some cache events
        for _ in range(8):
            self.collector.record_cache_hit()
        for _ in range(2):
            self.collector.record_cache_miss()
        
        stats = self.collector.get_cache_stats()
        
        assert stats["total_requests"] == 10
        assert stats["cache_hits"] == 8
        assert stats["cache_misses"] == 2
        assert stats["hit_rate_percent"] == 80.0
    
    def test_get_cache_stats_no_requests(self):
        """Test getting cache stats when no requests recorded."""
        stats = self.collector.get_cache_stats()
        
        assert stats["total_requests"] == 0
        assert stats["cache_hits"] == 0
        assert stats["cache_misses"] == 0
        assert stats["hit_rate_percent"] == 0.0
    
    def test_export_prometheus_metrics(self):
        """Test exporting metrics in Prometheus format."""
        # Record some data
        metrics = RequestMetrics(
            method="GET",
            path="/api/test",
            status_code=200,
            response_time=0.5,
            bytes_sent=1024,
            bytes_received=512
        )
        self.collector.record_request(metrics)
        self.collector.record_cache_hit()
        self.collector.record_cache_miss()
        
        prometheus_data = self.collector.export_prometheus_metrics()
        
        assert isinstance(prometheus_data, str)
        assert "# HELP" in prometheus_data
        assert "# TYPE" in prometheus_data
        assert "olah_http_requests_total" in prometheus_data
        assert "olah_cache_hits_total" in prometheus_data
        assert "olah_cache_misses_total" in prometheus_data
    
    def test_max_history_size_limit(self):
        """Test that history size is limited."""
        collector = MetricsCollector(max_history_size=3)
        
        # Record more requests than max size
        for i in range(5):
            metrics = RequestMetrics(
                method="GET",
                path=f"/api/test{i}",
                status_code=200,
                response_time=0.1,
                bytes_sent=100,
                bytes_received=50
            )
            collector.record_request(metrics)
        
        # Should only keep the last 3 requests
        assert len(collector.request_history) == 3
        # Last request should be the 5th one
        assert collector.request_history[-1].path == "/api/test4"


class TestGlobalFunctions:
    """Test global utility functions."""
    
    def test_get_metrics_collector_singleton(self):
        """Test that get_metrics_collector returns singleton instance."""
        collector1 = get_metrics_collector()
        collector2 = get_metrics_collector()
        
        assert collector1 is collector2
    
    def test_record_request_metrics(self):
        """Test record_request_metrics function."""
        # This test verifies the function doesn't raise exceptions
        record_request_metrics(
            method="GET",
            path="/api/test",
            status_code=200,
            response_time=0.5,
            bytes_sent=1024,
            bytes_received=512
        )
        
        # Verify the request was recorded
        collector = get_metrics_collector()
        assert len(collector.request_history) >= 1
    
    def test_record_cache_hit_function(self):
        """Test record_cache_hit function."""
        collector = get_metrics_collector()
        initial_hits = collector.cache_hit_count
        
        record_cache_hit()
        
        assert collector.cache_hit_count == initial_hits + 1
    
    def test_record_cache_miss_function(self):
        """Test record_cache_miss function."""
        collector = get_metrics_collector()
        initial_misses = collector.cache_miss_count
        
        record_cache_miss()
        
        assert collector.cache_miss_count == initial_misses + 1


class TestThreadSafety:
    """Test thread safety of metrics collection."""
    
    def test_concurrent_request_recording(self):
        """Test concurrent request recording."""
        collector = MetricsCollector(max_history_size=1000)
        
        def record_requests():
            for i in range(100):
                metrics = RequestMetrics(
                    method="GET",
                    path=f"/api/test{i}",
                    status_code=200,
                    response_time=0.1,
                    bytes_sent=100,
                    bytes_received=50
                )
                collector.record_request(metrics)
        
        # Start multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=record_requests)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Should have recorded 500 requests total
        assert len(collector.request_history) == 500
    
    def test_concurrent_cache_recording(self):
        """Test concurrent cache hit/miss recording."""
        collector = MetricsCollector()
        
        def record_cache_events():
            for _ in range(50):
                collector.record_cache_hit()
                collector.record_cache_miss()
        
        # Start multiple threads
        threads = []
        for _ in range(4):
            thread = threading.Thread(target=record_cache_events)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Should have recorded 200 hits and 200 misses
        assert collector.cache_hit_count == 200
        assert collector.cache_miss_count == 200
        assert collector.total_requests == 400


if __name__ == "__main__":
    pytest.main([__file__])
