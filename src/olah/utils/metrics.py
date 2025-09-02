# coding=utf-8
# Copyright 2024 XiaHan
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

"""
Metrics collection and monitoring utilities for Olah server.

This module provides comprehensive metrics collection including:
- HTTP request/response statistics
- Bandwidth usage tracking
- Disk I/O monitoring
- Cache efficiency metrics
- Prometheus format export
"""

import asyncio
import time
import psutil
import threading
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class RequestMetrics:
    """Metrics for individual HTTP requests."""
    method: str
    path: str
    status_code: int
    response_time: float
    bytes_sent: int
    bytes_received: int
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SystemMetrics:
    """System resource metrics."""
    cpu_percent: float
    memory_percent: float
    disk_usage_percent: float
    disk_read_bytes: int
    disk_write_bytes: int
    network_bytes_sent: int
    network_bytes_received: int
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class CacheMetrics:
    """Cache efficiency and usage metrics."""
    total_requests: int
    cache_hits: int
    cache_misses: int
    cache_size_bytes: int
    cache_files_count: int
    avg_response_time: float
    timestamp: datetime = field(default_factory=datetime.now)


class MetricsCollector:
    """
    Central metrics collection and aggregation system.
    
    Collects and aggregates various metrics including HTTP requests,
    system resources, and cache performance.
    """
    
    def __init__(self, max_history_size: int = 10000):
        """
        Initialize metrics collector.
        
        Args:
            max_history_size: Maximum number of metrics to keep in memory
        """
        self.max_history_size = max_history_size
        
        # Request metrics
        self.request_history: deque = deque(maxlen=max_history_size)
        self.request_counts: Dict[str, int] = defaultdict(int)
        self.response_times: Dict[str, List[float]] = defaultdict(list)
        self.bytes_transferred: Dict[str, int] = defaultdict(int)
        
        # System metrics
        self.system_history: deque = deque(maxlen=1000)  # Keep less system metrics
        self._last_disk_io = None
        self._last_network_io = None
        
        # Cache metrics
        self.cache_metrics_history: deque = deque(maxlen=1000)
        self.cache_hit_count = 0
        self.cache_miss_count = 0
        self.total_requests = 0
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Start background collection
        self._start_background_collection()
    
    def _start_background_collection(self) -> None:
        """Start background system metrics collection."""
        def collect_system_metrics():
            while True:
                try:
                    self._collect_system_metrics()
                    time.sleep(5)  # Collect every 5 seconds
                except Exception as e:
                    logger.error(f"Error collecting system metrics: {e}")
                    time.sleep(10)  # Wait longer on error
        
        thread = threading.Thread(target=collect_system_metrics, daemon=True)
        thread.start()
    
    def record_request(self, metrics: RequestMetrics) -> None:
        """
        Record HTTP request metrics.
        
        Args:
            metrics: Request metrics to record
        """
        with self._lock:
            self.request_history.append(metrics)
            
            # Aggregate by endpoint
            endpoint = f"{metrics.method} {metrics.path}"
            self.request_counts[endpoint] += 1
            
            # Track response times
            if len(self.response_times[endpoint]) > 1000:
                self.response_times[endpoint] = self.response_times[endpoint][-500:]  # Keep last 500
            self.response_times[endpoint].append(metrics.response_time)
            
            # Track bytes transferred
            self.bytes_transferred[endpoint] += metrics.bytes_sent + metrics.bytes_received
    
    def record_cache_hit(self) -> None:
        """Record a cache hit."""
        with self._lock:
            self.cache_hit_count += 1
            self.total_requests += 1
    
    def record_cache_miss(self) -> None:
        """Record a cache miss."""
        with self._lock:
            self.cache_miss_count += 1
            self.total_requests += 1
    
    def _collect_system_metrics(self) -> None:
        """Collect current system metrics."""
        try:
            # CPU and memory
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_usage_percent = (disk.used / disk.total) * 100
            
            # Disk I/O
            disk_io = psutil.disk_io_counters()
            disk_read_bytes = disk_io.read_bytes if disk_io else 0
            disk_write_bytes = disk_io.write_bytes if disk_io else 0
            
            # Network I/O
            network_io = psutil.net_io_counters()
            network_bytes_sent = network_io.bytes_sent if network_io else 0
            network_bytes_received = network_io.bytes_recv if network_io else 0
            
            # Calculate deltas if we have previous values
            if self._last_disk_io:
                disk_read_bytes = disk_read_bytes - self._last_disk_io[0]
                disk_write_bytes = disk_write_bytes - self._last_disk_io[1]
            else:
                disk_read_bytes = 0
                disk_write_bytes = 0
            
            if self._last_network_io:
                network_bytes_sent = network_bytes_sent - self._last_network_io[0]
                network_bytes_received = network_bytes_received - self._last_network_io[1]
            else:
                network_bytes_sent = 0
                network_bytes_received = 0
            
            # Store current values for next calculation
            if disk_io:
                self._last_disk_io = (disk_io.read_bytes, disk_io.write_bytes)
            if network_io:
                self._last_network_io = (network_io.bytes_sent, network_io.bytes_recv)
            
            metrics = SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                disk_usage_percent=disk_usage_percent,
                disk_read_bytes=disk_read_bytes,
                disk_write_bytes=disk_write_bytes,
                network_bytes_sent=network_bytes_sent,
                network_bytes_received=network_bytes_received
            )
            
            with self._lock:
                self.system_history.append(metrics)
                
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
    
    def get_request_stats(self, time_window_minutes: int = 60) -> Dict[str, Any]:
        """
        Get request statistics for the specified time window.
        
        Args:
            time_window_minutes: Time window in minutes
            
        Returns:
            Dictionary containing request statistics
        """
        cutoff_time = datetime.now() - timedelta(minutes=time_window_minutes)
        
        with self._lock:
            recent_requests = [
                req for req in self.request_history 
                if req.timestamp >= cutoff_time
            ]
            
            if not recent_requests:
                return {
                    "total_requests": 0,
                    "avg_response_time": 0.0,
                    "total_bytes_transferred": 0,
                    "status_codes": {},
                    "endpoints": {}
                }
            
            # Calculate statistics
            total_requests = len(recent_requests)
            avg_response_time = sum(req.response_time for req in recent_requests) / total_requests
            total_bytes = sum(req.bytes_sent + req.bytes_received for req in recent_requests)
            
            # Status code distribution
            status_codes = defaultdict(int)
            for req in recent_requests:
                status_codes[req.status_code] += 1
            
            # Endpoint statistics
            endpoints = defaultdict(lambda: {"count": 0, "avg_time": 0.0, "bytes": 0})
            for req in recent_requests:
                endpoint = f"{req.method} {req.path}"
                endpoints[endpoint]["count"] += 1
                endpoints[endpoint]["bytes"] += req.bytes_sent + req.bytes_received
            
            # Calculate average response times per endpoint
            for endpoint in endpoints:
                endpoint_requests = [req for req in recent_requests 
                                   if f"{req.method} {req.path}" == endpoint]
                if endpoint_requests:
                    endpoints[endpoint]["avg_time"] = (
                        sum(req.response_time for req in endpoint_requests) / 
                        len(endpoint_requests)
                    )
            
            return {
                "total_requests": total_requests,
                "avg_response_time": avg_response_time,
                "total_bytes_transferred": total_bytes,
                "status_codes": dict(status_codes),
                "endpoints": dict(endpoints)
            }
    
    def get_system_stats(self) -> Dict[str, Any]:
        """
        Get current system statistics.
        
        Returns:
            Dictionary containing system statistics
        """
        with self._lock:
            if not self.system_history:
                return {
                    "cpu_percent": 0.0,
                    "memory_percent": 0.0,
                    "disk_usage_percent": 0.0,
                    "disk_io": {"read_bytes": 0, "write_bytes": 0},
                    "network_io": {"bytes_sent": 0, "bytes_received": 0}
                }
            
            latest = self.system_history[-1]
            
            # Calculate averages over last 10 measurements
            recent_metrics = list(self.system_history)[-10:]
            avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
            avg_memory = sum(m.memory_percent for m in recent_metrics) / len(recent_metrics)
            
            return {
                "cpu_percent": avg_cpu,
                "memory_percent": avg_memory,
                "disk_usage_percent": latest.disk_usage_percent,
                "disk_io": {
                    "read_bytes": latest.disk_read_bytes,
                    "write_bytes": latest.disk_write_bytes
                },
                "network_io": {
                    "bytes_sent": latest.network_bytes_sent,
                    "bytes_received": latest.network_bytes_received
                }
            }
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache performance statistics.
        
        Returns:
            Dictionary containing cache statistics
        """
        with self._lock:
            if self.total_requests == 0:
                hit_rate = 0.0
            else:
                hit_rate = (self.cache_hit_count / self.total_requests) * 100
            
            return {
                "total_requests": self.total_requests,
                "cache_hits": self.cache_hit_count,
                "cache_misses": self.cache_miss_count,
                "hit_rate_percent": hit_rate
            }
    
    def export_prometheus_metrics(self) -> str:
        """
        Export metrics in Prometheus format.
        
        Returns:
            Prometheus-formatted metrics string
        """
        lines = []
        
        # Request metrics
        request_stats = self.get_request_stats(60)  # Last hour
        lines.append(f"# HELP olah_http_requests_total Total number of HTTP requests")
        lines.append(f"# TYPE olah_http_requests_total counter")
        lines.append(f"olah_http_requests_total {request_stats['total_requests']}")
        
        lines.append(f"# HELP olah_http_request_duration_seconds Average HTTP request duration")
        lines.append(f"# TYPE olah_http_request_duration_seconds gauge")
        lines.append(f"olah_http_request_duration_seconds {request_stats['avg_response_time']:.4f}")
        
        lines.append(f"# HELP olah_http_bytes_transferred_total Total bytes transferred")
        lines.append(f"# TYPE olah_http_bytes_transferred_total counter")
        lines.append(f"olah_http_bytes_transferred_total {request_stats['total_bytes_transferred']}")
        
        # System metrics
        system_stats = self.get_system_stats()
        lines.append(f"# HELP olah_system_cpu_percent CPU usage percentage")
        lines.append(f"# TYPE olah_system_cpu_percent gauge")
        lines.append(f"olah_system_cpu_percent {system_stats['cpu_percent']:.2f}")
        
        lines.append(f"# HELP olah_system_memory_percent Memory usage percentage")
        lines.append(f"# TYPE olah_system_memory_percent gauge")
        lines.append(f"olah_system_memory_percent {system_stats['memory_percent']:.2f}")
        
        lines.append(f"# HELP olah_system_disk_usage_percent Disk usage percentage")
        lines.append(f"# TYPE olah_system_disk_usage_percent gauge")
        lines.append(f"olah_system_disk_usage_percent {system_stats['disk_usage_percent']:.2f}")
        
        # Cache metrics
        cache_stats = self.get_cache_stats()
        lines.append(f"# HELP olah_cache_requests_total Total cache requests")
        lines.append(f"# TYPE olah_cache_requests_total counter")
        lines.append(f"olah_cache_requests_total {cache_stats['total_requests']}")
        
        lines.append(f"# HELP olah_cache_hits_total Total cache hits")
        lines.append(f"# TYPE olah_cache_hits_total counter")
        lines.append(f"olah_cache_hits_total {cache_stats['cache_hits']}")
        
        lines.append(f"# HELP olah_cache_misses_total Total cache misses")
        lines.append(f"# TYPE olah_cache_misses_total counter")
        lines.append(f"olah_cache_misses_total {cache_stats['cache_misses']}")
        
        lines.append(f"# HELP olah_cache_hit_rate_percent Cache hit rate percentage")
        lines.append(f"# TYPE olah_cache_hit_rate_percent gauge")
        lines.append(f"olah_cache_hit_rate_percent {cache_stats['hit_rate_percent']:.2f}")
        
        return "\n".join(lines)


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """
    Get the global metrics collector instance.
    
    Returns:
        MetricsCollector instance
    """
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def record_request_metrics(
    method: str,
    path: str,
    status_code: int,
    response_time: float,
    bytes_sent: int = 0,
    bytes_received: int = 0
) -> None:
    """
    Record HTTP request metrics.
    
    Args:
        method: HTTP method
        path: Request path
        status_code: HTTP status code
        response_time: Response time in seconds
        bytes_sent: Bytes sent in response
        bytes_received: Bytes received in request
    """
    collector = get_metrics_collector()
    metrics = RequestMetrics(
        method=method,
        path=path,
        status_code=status_code,
        response_time=response_time,
        bytes_sent=bytes_sent,
        bytes_received=bytes_received
    )
    collector.record_request(metrics)


def record_cache_hit() -> None:
    """Record a cache hit."""
    collector = get_metrics_collector()
    collector.record_cache_hit()


def record_cache_miss() -> None:
    """Record a cache miss."""
    collector = get_metrics_collector()
    collector.record_cache_miss()
