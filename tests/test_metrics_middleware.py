# coding=utf-8
# Copyright 2024 XiaHan
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

"""
Unit tests for metrics middleware functionality.

Tests the MetricsMiddleware class for collecting HTTP request metrics
in FastAPI applications.
"""

import pytest
import time
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient

from olah.middleware.metrics_middleware import MetricsMiddleware
from olah.utils.metrics import get_metrics_collector


class TestMetricsMiddleware:
    """Test MetricsMiddleware class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = FastAPI()
        self.middleware = MetricsMiddleware(self.app)
        
        # Add a simple test endpoint
        @self.app.get("/test")
        async def test_endpoint():
            return {"message": "test"}
        
        @self.app.get("/test-error")
        async def test_error_endpoint():
            return Response(content="error", status_code=500)
    
    def test_middleware_initialization(self):
        """Test middleware initialization."""
        assert self.middleware.app == self.app
    
    @pytest.mark.asyncio
    @patch('olah.middleware.metrics_middleware.record_request_metrics')
    async def test_dispatch_successful_request(self, mock_record_metrics):
        """Test middleware dispatch with successful request."""
        # Create mock request and call_next
        request = MagicMock(spec=Request)
        request.method = "GET"
        request.url.path = "/test"
        request.headers = {}
        request._body = b"test body"
        
        response = Response(content="test response", status_code=200)
        response.body = b"test response"
        
        call_next = AsyncMock(return_value=response)
        
        # Call middleware
        result = await self.middleware.dispatch(request, call_next)
        
        # Verify response
        assert result == response
        
        # Verify metrics were recorded
        mock_record_metrics.assert_called_once()
        call_args = mock_record_metrics.call_args[1]
        assert call_args["method"] == "GET"
        assert call_args["path"] == "/test"
        assert call_args["status_code"] == 200
        assert call_args["response_time"] > 0
        assert call_args["bytes_sent"] == len(b"test response")
        assert call_args["bytes_received"] == len(b"test body")
    
    @pytest.mark.asyncio
    @patch('olah.middleware.metrics_middleware.record_request_metrics')
    async def test_dispatch_error_request(self, mock_record_metrics):
        """Test middleware dispatch with error request."""
        # Create mock request and call_next
        request = MagicMock(spec=Request)
        request.method = "GET"
        request.url.path = "/test-error"
        request.headers = {}
        request._body = b""
        
        response = Response(content="error", status_code=500)
        response.body = b"error"
        
        call_next = AsyncMock(return_value=response)
        
        # Call middleware
        result = await self.middleware.dispatch(request, call_next)
        
        # Verify response
        assert result == response
        
        # Verify metrics were recorded
        mock_record_metrics.assert_called_once()
        call_args = mock_record_metrics.call_args[1]
        assert call_args["method"] == "GET"
        assert call_args["path"] == "/test-error"
        assert call_args["status_code"] == 500
    
    @pytest.mark.asyncio
    @patch('olah.middleware.metrics_middleware.record_request_metrics')
    async def test_dispatch_without_body(self, mock_record_metrics):
        """Test middleware dispatch when request/response has no body."""
        # Create mock request and call_next
        request = MagicMock(spec=Request)
        request.method = "HEAD"
        request.url.path = "/test"
        request.headers = {}
        request._body = None
        
        response = Response(content="", status_code=200)
        response.body = None
        
        call_next = AsyncMock(return_value=response)
        
        # Call middleware
        result = await self.middleware.dispatch(request, call_next)
        
        # Verify response
        assert result == response
        
        # Verify metrics were recorded with zero bytes
        mock_record_metrics.assert_called_once()
        call_args = mock_record_metrics.call_args[1]
        assert call_args["bytes_sent"] == 0
        assert call_args["bytes_received"] == 0
    
    @pytest.mark.asyncio
    @patch('olah.middleware.metrics_middleware.record_request_metrics')
    async def test_dispatch_metrics_recording_failure(self, mock_record_metrics):
        """Test middleware continues working when metrics recording fails."""
        # Make metrics recording raise an exception
        mock_record_metrics.side_effect = Exception("Metrics recording failed")
        
        # Create mock request and call_next
        request = MagicMock(spec=Request)
        request.method = "GET"
        request.url.path = "/test"
        request.headers = {}
        request._body = b""
        
        response = Response(content="test", status_code=200)
        response.body = b"test"
        
        call_next = AsyncMock(return_value=response)
        
        # Call middleware - should not raise exception
        result = await self.middleware.dispatch(request, call_next)
        
        # Verify response is still returned
        assert result == response
    
    def test_integration_with_fastapi_app(self):
        """Test middleware integration with FastAPI app."""
        # Create app with middleware
        app = FastAPI()
        app.add_middleware(MetricsMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}
        
        # Test with TestClient
        client = TestClient(app)
        
        # Make request
        response = client.get("/test")
        
        # Verify response
        assert response.status_code == 200
        assert response.json() == {"message": "test"}
        
        # Verify metrics were collected
        collector = get_metrics_collector()
        stats = collector.get_request_stats(1)  # Last minute
        
        # Should have at least one request
        assert stats["total_requests"] >= 1
        
        # Check if our test endpoint is in the stats
        endpoint_found = False
        for endpoint in stats["endpoints"]:
            if "/test" in endpoint:
                endpoint_found = True
                break
        assert endpoint_found
    
    def test_multiple_requests_integration(self):
        """Test multiple requests with middleware."""
        # Create app with middleware
        app = FastAPI()
        app.add_middleware(MetricsMiddleware)
        
        @app.get("/test1")
        async def test_endpoint1():
            return {"message": "test1"}
        
        @app.get("/test2")
        async def test_endpoint2():
            return {"message": "test2"}
        
        # Test with TestClient
        client = TestClient(app)
        
        # Make multiple requests
        client.get("/test1")
        client.get("/test2")
        client.get("/test1")
        
        # Verify metrics were collected
        collector = get_metrics_collector()
        stats = collector.get_request_stats(1)  # Last minute
        
        # Should have at least 3 requests
        assert stats["total_requests"] >= 3
        
        # Check endpoint statistics
        endpoints = stats["endpoints"]
        assert any("/test1" in endpoint for endpoint in endpoints)
        assert any("/test2" in endpoint for endpoint in endpoints)
    
    def test_different_http_methods(self):
        """Test middleware with different HTTP methods."""
        # Create app with middleware
        app = FastAPI()
        app.add_middleware(MetricsMiddleware)
        
        @app.get("/test")
        async def get_endpoint():
            return {"method": "GET"}
        
        @app.post("/test")
        async def post_endpoint():
            return {"method": "POST"}
        
        @app.put("/test")
        async def put_endpoint():
            return {"method": "PUT"}
        
        @app.delete("/test")
        async def delete_endpoint():
            return {"method": "DELETE"}
        
        # Test with TestClient
        client = TestClient(app)
        
        # Make requests with different methods
        client.get("/test")
        client.post("/test")
        client.put("/test")
        client.delete("/test")
        
        # Verify metrics were collected
        collector = get_metrics_collector()
        stats = collector.get_request_stats(1)  # Last minute
        
        # Should have at least 4 requests
        assert stats["total_requests"] >= 4
        
        # Check that different methods are recorded
        endpoints = stats["endpoints"]
        method_endpoints = [endpoint for endpoint in endpoints if "/test" in endpoint]
        assert len(method_endpoints) >= 4  # Should have GET, POST, PUT, DELETE
    
    def test_response_time_measurement(self):
        """Test that response time is accurately measured."""
        # Create app with middleware
        app = FastAPI()
        app.add_middleware(MetricsMiddleware)
        
        @app.get("/slow")
        async def slow_endpoint():
            time.sleep(0.1)  # Simulate slow response
            return {"message": "slow"}
        
        @app.get("/fast")
        async def fast_endpoint():
            return {"message": "fast"}
        
        # Test with TestClient
        client = TestClient(app)
        
        # Make requests
        client.get("/slow")
        client.get("/fast")
        
        # Verify metrics were collected
        collector = get_metrics_collector()
        stats = collector.get_request_stats(1)  # Last minute
        
        # Check response times
        endpoints = stats["endpoints"]
        for endpoint, data in endpoints.items():
            if "/slow" in endpoint:
                assert data["avg_time"] >= 0.1  # Should be at least 0.1 seconds
            elif "/fast" in endpoint:
                assert data["avg_time"] < 0.1  # Should be much faster


if __name__ == "__main__":
    pytest.main([__file__])
