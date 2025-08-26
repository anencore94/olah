#!/usr/bin/env python3
"""
Integration test runner for Olah.

This script provides a simple way to run integration tests.
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], description: str) -> bool:
    """Run a command and return success status."""
    print(f"🔄 {description}...")
    print(f"   Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if result.returncode == 0:
            print(f"✅ {description} completed successfully")
            return True
        else:
            print(f"❌ {description} failed")
            print(f"   stdout: {result.stdout}")
            print(f"   stderr: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"⏰ {description} timed out")
        return False
    except Exception as e:
        print(f"❌ {description} error: {e}")
        return False


def main():
    """Main function to run integration tests."""
    print("🧪 Olah Integration Test Runner")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not Path("src/olah").exists():
        print("❌ Please run this script from the project root directory")
        sys.exit(1)
    
    # Check if olah is installed
    try:
        subprocess.run(["olah-cli", "--help"], capture_output=True, check=True)
        print("✅ olah-cli is available")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ olah-cli not found. Please install olah in editable mode first.")
        print("   Run: pip install -e .")
        sys.exit(1)
    
    # Run pytest integration tests
    print("\n📋 Running pytest integration tests...")
    pytest_cmd = [
        sys.executable, "-m", "pytest",
        "integration_tests/test_cache_integration_pytest.py",
        "-v",
        "--tb=short"
    ]
    
    if not run_command(pytest_cmd, "Pytest integration tests"):
        print("\n❌ Integration tests failed!")
        sys.exit(1)
    
    # Run standalone integration test
    print("\n📋 Running standalone integration test...")
    standalone_cmd = [sys.executable, "integration_tests/test_cache_integration.py"]
    
    if not run_command(standalone_cmd, "Standalone integration test"):
        print("\n❌ Standalone integration test failed!")
        sys.exit(1)
    
    print("\n🎉 All integration tests completed successfully!")
    print("=" * 50)


if __name__ == "__main__":
    main()
