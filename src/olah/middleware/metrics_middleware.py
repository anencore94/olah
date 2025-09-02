# coding=utf-8
# Copyright 2024 XiaHan
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

"""
FastAPI middleware for collecting HTTP request metrics.

This middleware automatically collects metrics for all HTTP requests
including response times, status codes, and bytes transferred.
"""

import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from olah.utils.metrics import record_request_metrics


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware to collect HTTP request metrics.
    
    Automatically tracks:
    - Request/response times
    - Status codes
    - Bytes transferred
    - Request paths and methods
    """
    
    def __init__(self, app: ASGIApp):
        """
        Initialize metrics middleware.
        
        Args:
            app: ASGI application instance
        """
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and collect metrics.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain
            
        Returns:
            HTTP response
        """
        # Record start time
        start_time = time.time()
        
        # Get request size (approximate)
        bytes_received = 0
        if hasattr(request, '_body'):
            bytes_received = len(request._body) if request._body else 0
        
        # Process request
        response = await call_next(request)
        
        # Calculate metrics
        response_time = time.time() - start_time
        
        # Get response size (approximate)
        bytes_sent = 0
        if hasattr(response, 'body'):
            bytes_sent = len(response.body) if response.body else 0
        
        # Record metrics
        try:
            record_request_metrics(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                response_time=response_time,
                bytes_sent=bytes_sent,
                bytes_received=bytes_received
            )
        except Exception as e:
            # Don't let metrics collection break the request
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to record metrics: {e}")
        
        return response
