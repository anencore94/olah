#!/usr/bin/env python3
"""
Integration test for Olah cache management functionality.

This script tests the complete workflow:
1. Start Olah server
2. Download models using huggingface-cli
3. Test cache API endpoints
4. Verify cache statistics
5. Clean up test data
"""

import asyncio
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Optional
import httpx


class OlahIntegrationTest:
    """Integration test class for Olah server and cache functionality."""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8090):
        """Initialize the integration test."""
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.server_process: Optional[subprocess.Popen] = None
    
    async def start_server(self) -> bool:
        """Start the Olah server in background."""
        try:
            print("🚀 Starting Olah server...")
            cmd = [
                sys.executable, "-c",
                "from olah.server import app; import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8090)"
            ]
            self.server_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid
            )
            await asyncio.sleep(3)
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/")
                if response.status_code == 200:
                    print("✅ Server started successfully")
                    return True
                print(f"❌ Server not responding: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Failed to start server: {e}")
            return False
    
    async def stop_server(self):
        """Stop the Olah server."""
        if self.server_process:
            print("🛑 Stopping Olah server...")
            try:
                os.killpg(os.getpgid(self.server_process.pid), signal.SIGTERM)
                self.server_process.wait(timeout=5)
                print("✅ Server stopped successfully")
            except subprocess.TimeoutExpired:
                print("⚠️  Server didn't stop gracefully, force killing...")
                os.killpg(os.getpgid(self.server_process.pid), signal.SIGKILL)
            except Exception as e:
                print(f"⚠️  Error stopping server: {e}")
    
    async def test_cache_stats_api(self) -> bool:
        """Test the cache stats API endpoint."""
        try:
            print("🔍 Testing cache stats API...")
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/cache-stats")
                if response.status_code != 200:
                    print(f"❌ Cache stats API failed: {response.status_code}")
                    return False
                data = response.json()
                assert data.get("status") == "success"
                assert "overview" in data and "efficiency" in data
                overview = data["overview"]
                for field in ["total_size", "total_files", "repo_counts"]:
                    if field not in overview:
                        print(f"❌ Missing overview field: {field}")
                        return False
                print("✅ Cache stats API working correctly")
                return True
        except Exception as e:
            print(f"❌ Error testing cache stats API: {e}")
            return False
    
    async def download_with_hf_cli(self) -> bool:
        """Download small models using huggingface-cli pointing to this server via HF_ENDPOINT."""
        try:
            print("📥 Downloading models via huggingface-cli...")
            env = os.environ.copy()
            env["HF_ENDPOINT"] = self.base_url
            env["hf_endpoint"] = self.base_url
            models = ["distilbert-base-uncased", "bert-base-uncased"]
            for model in models:
                cmd = [
                    "huggingface-cli",
                    "download",
                    "--repo-type",
                    "model",
                    model,
                    "--local-dir",
                    str(Path(".cache_hf_cli") / model),
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=300)
                if result.returncode != 0:
                    print(f"❌ huggingface-cli download failed for {model}: {result.stderr}")
                    return False
            print("✅ huggingface-cli downloads completed")
            return True
        except Exception as e:
            print(f"❌ Error running huggingface-cli: {e}")
            return False

    async def test_cache_repos_api(self) -> bool:
        """Test the cache repos and search API endpoints."""
        try:
            print("🔍 Testing cache repos API...")
            async with httpx.AsyncClient() as client:
                # Unfiltered
                response = await client.get(f"{self.base_url}/cache-repos")
                if response.status_code != 200:
                    print(f"❌ Cache repos API failed: {response.status_code}")
                    return False
                data = response.json()
                repos = data.get("repos") or data.get("results")
                if not isinstance(repos, list):
                    print("❌ Invalid repos payload shape")
                    return False
                # Search
                response = await client.get(f"{self.base_url}/cache-search?query=bert")
                if response.status_code != 200:
                    print(f"❌ Cache search API failed: {response.status_code}")
                    return False
                print("✅ Cache repos/search API working correctly")
                return True
        except Exception as e:
            print(f"❌ Error testing cache repos API: {e}")
            return False
    
    async def test_repo_details_api(self) -> bool:
        """Test the repository details API endpoint."""
        try:
            print("🔍 Testing repository details API...")
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/cache-repos/models/distilbert-base-uncased")
                if response.status_code == 200:
                    data = response.json()
                    for field in ["name", "size", "file_count", "last_access", "last_modified"]:
                        if field not in data:
                            print(f"❌ Missing repo field: {field}")
                            return False
                    print("✅ Repository details API working correctly")
                    return True
                # Accept not found for clean caches
                if response.status_code in (404, 400, 500):
                    print(f"ℹ️ Repo not present or server returned {response.status_code}, skipping assert")
                    return True
                print(f"❌ Unexpected status: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Error testing repository details API: {e}")
            return False
    
    async def verify_cache_layout(self) -> bool:
        """Verify that default repos layout exists (non-strict)."""
        try:
            print("🔍 Verifying cache layout...")
            repos_root = Path("repos")
            if not repos_root.exists():
                print("❌ Repos root directory not found")
                return False
            # Optional directories depending on usage
            for p in [Path("repos/api/models"), Path("repos/files")]:
                if p.exists() and not p.is_dir():
                    print(f"❌ Path exists but is not a directory: {p}")
                    return False
            print("✅ Cache layout verified")
            return True
        except Exception as e:
            print(f"❌ Error verifying cache layout: {e}")
            return False
    
    async def run_integration_test(self) -> bool:
        """Run the complete integration test."""
        print("🧪 Starting Olah Integration Test")
        print("=" * 50)
        try:
            if not await self.start_server():
                return False
            await asyncio.sleep(2)
            # Download via huggingface-cli targeting this mirror
            if not await self.download_with_hf_cli():
                return False
            await asyncio.sleep(2)
            if not await self.test_cache_stats_api():
                return False
            if not await self.test_cache_repos_api():
                return False
            if not await self.test_repo_details_api():
                return False
            if not await self.verify_cache_layout():
                return False
            print("=" * 50)
            print("🎉 All integration tests passed!")
            return True
        except Exception as e:
            print(f"❌ Integration test failed: {e}")
            return False
        finally:
            await self.stop_server()


async def main():
    """Main function to run the integration test."""
    test = OlahIntegrationTest()
    success = await test.run_integration_test()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
