#!/usr/bin/env python3
"""
Pytest-based integration tests for Olah cache management functionality.

This module provides pytest fixtures and tests for integration testing.
Run with: pytest integration_tests/test_cache_integration_pytest.py -v
"""

import asyncio
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import AsyncGenerator, Optional
import pytest
import pytest_asyncio
import httpx


@pytest_asyncio.fixture
async def olah_server() -> AsyncGenerator[tuple[str, int], None]:
    """Fixture to start and stop Olah server for testing."""
    host = "0.0.0.0"
    port = 8090
    base_url = f"http://{host}:{port}"
    server_process: Optional[subprocess.Popen] = None
    
    try:
        print("🚀 Starting Olah server...")
        
        # Start server using Python module
        cmd = [
            sys.executable, "-c",
            "from olah.server import app; import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8090)"
        ]
        
        server_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid
        )
        
        # Wait for server to start
        await asyncio.sleep(3)
        
        # Test if server is responding
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/")
            if response.status_code != 200:
                pytest.fail(f"Server not responding: {response.status_code}")
        
        print("✅ Server started successfully")
        yield base_url, port
        
    finally:
        if server_process:
            print("🛑 Stopping Olah server...")
            try:
                os.killpg(os.getpgid(server_process.pid), signal.SIGTERM)
                server_process.wait(timeout=5)
                print("✅ Server stopped successfully")
            except subprocess.TimeoutExpired:
                print("⚠️  Server didn't stop gracefully, force killing...")
                os.killpg(os.getpgid(server_process.pid), signal.SIGKILL)
            except Exception as e:
                print(f"⚠️  Error stopping server: {e}")


@pytest.fixture
def test_models() -> list[str]:
    """Fixture providing test model names."""
    return ["distilbert-base-uncased", "bert-base-uncased"]


class TestOlahIntegration:
    """Integration test class for Olah functionality."""
    
    @pytest.mark.asyncio
    async def test_server_startup(self, olah_server):
        """Test that the server starts and responds correctly."""
        base_url, port = olah_server
        
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/")
            assert response.status_code == 200
            
            # Test cache stats endpoint
            response = await client.get(f"{base_url}/cache-stats")
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_cache_stats_api(self, olah_server):
        """Test the cache stats API endpoint structure."""
        base_url, _ = olah_server
        
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/cache-stats")
            assert response.status_code == 200
            
            data = response.json()
            assert data.get("status") == "success"
            assert "overview" in data
            assert "efficiency" in data
            
            overview = data["overview"]
            efficiency = data["efficiency"]
            
            for field in ["total_size", "total_files", "repo_counts"]:
                assert field in overview, f"Missing overview field: {field}"
            
            # Accept either efficiency_percentage or access_efficiency
            assert (
                "efficiency_percentage" in efficiency or "access_efficiency" in efficiency
            ), "Missing efficiency percentage field"
    
    @pytest.mark.asyncio
    async def test_hf_cli_download_and_cache(self, olah_server, tmp_path):
        """Download small models via huggingface-cli using HF_ENDPOINT and verify cache updates."""
        base_url, port = olah_server
        env = os.environ.copy()
        # Support both HF_ENDPOINT and hf_endpoint for robustness
        env["HF_ENDPOINT"] = base_url
        env["hf_endpoint"] = base_url
        models = ["distilbert-base-uncased", "bert-base-uncased"]
        for model in models:
            cmd = [
                "huggingface-cli",
                "download",
                "--repo-type",
                "model",
                model,
                "--local-dir",
                str(tmp_path / model),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=300)
            assert result.returncode == 0, f"huggingface-cli download failed for {model}: {result.stderr}"

        # Give the server a moment to register accesses
        await asyncio.sleep(2)

        # Verify cache stats reflect downloads
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{base_url}/cache-stats")
            assert resp.status_code == 200
            payload = resp.json()
            assert payload.get("status") == "success"
            models_count = payload["overview"]["repo_counts"].get("models", {}).get("repo_count", 0)
            assert models_count >= 1

    @pytest.mark.asyncio
    async def test_cache_repos_api(self, olah_server):
        """Test the cache repos API endpoint."""
        base_url, _ = olah_server
        
        async with httpx.AsyncClient() as client:
            # Unfiltered listing
            response = await client.get(f"{base_url}/cache-repos")
            assert response.status_code == 200
            data = response.json()
            # Support both legacy and current shapes
            repos = data.get("repos") or data.get("results")
            assert isinstance(repos, list)
            
            # Filtered listing
            response = await client.get(f"{base_url}/cache-repos?repo_type=models&limit=5")
            assert response.status_code == 200
            data = response.json()
            repos = data.get("repos") or data.get("results")
            assert isinstance(repos, list)
            
            # Search
            response = await client.get(f"{base_url}/cache-search?query=bert")
            assert response.status_code == 200
            data = response.json()
            repos = data.get("repos") or data.get("results")
            assert isinstance(repos, list)
    
    @pytest.mark.asyncio
    async def test_repo_details_api(self, olah_server):
        """Test the repository details API endpoint returns expected structure if present."""
        base_url, _ = olah_server
        
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/cache-repos/models/distilbert-base-uncased")
            
            if response.status_code == 200:
                data = response.json()
                assert isinstance(data, dict)
                # Flexible checks based on presence
                for field in ["name", "size", "file_count", "last_access", "last_modified"]:
                    assert field in data
            else:
                # Repository might not exist in a fresh environment
                assert response.status_code in (404, 400, 500)
    
    @pytest.mark.asyncio
    async def test_cache_files_verification(self, olah_server):
        """Verify cache directories exist as per default layout."""
        # Default repos layout places models under repos/api/models
        models_path = Path("repos/api/models")
        files_path = Path("repos/files")
        # At least the root repos directory should exist after server runs
        repos_root = Path("repos")
        assert repos_root.exists(), "Repos root directory not found"
        # Models/files folders may or may not exist depending on activity; do not fail hard
        if models_path.exists():
            assert models_path.is_dir()
        if files_path.exists():
            assert files_path.is_dir()
    
    @pytest.mark.asyncio
    async def test_cache_efficiency_analysis(self, olah_server):
        """Test cache efficiency analysis fields exist."""
        base_url, _ = olah_server
        
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/cache-stats")
            assert response.status_code == 200
            data = response.json()
            efficiency = data.get("efficiency", {})
            for field in ["recent_access_count", "old_access_count"]:
                assert field in efficiency
            # Accept either key naming for percentage
            percent = efficiency.get("efficiency_percentage") or efficiency.get("access_efficiency")
            assert isinstance(percent, (int, float))
            assert 0 <= float(percent) <= 100


if __name__ == "__main__":
    # Run tests directly if script is executed
    pytest.main([__file__, "-v"])
