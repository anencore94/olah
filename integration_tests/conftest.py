"""
Pytest configuration for integration tests.

This file provides shared fixtures and configuration for integration tests.
"""

import pytest
import asyncio
from typing import AsyncGenerator
import httpx


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide an HTTP client for testing."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        yield client


@pytest.fixture
def test_config():
    """Provide test configuration."""
    return {
        "host": "0.0.0.0",
        "port": 8090,
        "base_url": "http://0.0.0.0:8090",
        "test_models": ["distilbert-base-uncased", "bert-base-uncased"],
        "timeout": 300,  # 5 minutes
        "server_startup_wait": 3,
        "download_wait": 5
    }


# Mark all tests as integration tests
pytestmark = pytest.mark.integration
