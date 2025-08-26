# Olah Integration Tests

This directory contains integration tests for the Olah HuggingFace mirror server. These tests verify the complete functionality by starting the server, downloading models, and testing the cache management APIs.

## 🏗️ Test Structure

- `test_cache_integration.py`: Standalone integration test script
- `test_cache_integration_pytest.py`: Pytest-based integration tests
- `run_integration_tests.py`: Test runner script
- `conftest.py`: Pytest configuration and shared fixtures

## 🚀 Quick Start

### Prerequisites

1. Install Olah in editable mode:

```bash
pip install -e .
```

2. Verify CLI tools:

```bash
olah-cli --help
huggingface-cli --help
```

### Running Tests

- All integration tests:

```bash
python integration_tests/run_integration_tests.py
```

- Pytest-only:

```bash
pytest integration_tests/test_cache_integration_pytest.py -v
```

- Standalone script:

```bash
python integration_tests/test_cache_integration.py
```

## 🧪 What the Tests Do

1. Start Olah server on port 8090
2. Use `huggingface-cli download` with `HF_ENDPOINT` pointed at the running mirror to fetch small models
3. Validate cache APIs: `/cache-stats`, `/cache-repos`, `/cache-repos/{...}`, `/cache-search`
4. Verify repo layout exists under `repos/`

### HF_ENDPOINT usage

Both environment variables are set for robustness:

- `HF_ENDPOINT`
- `hf_endpoint`

Example manual usage:

```bash
export HF_ENDPOINT=http://0.0.0.0:8090
huggingface-cli download --repo-type model distilbert-base-uncased --local-dir ./_tmp_distilbert
```

## ⚙️ Notes

- Tests assume network access to HuggingFace model metadata via the mirror
- Small models used by default: `distilbert-base-uncased`, `bert-base-uncased`
- Timeouts are conservative to reduce flakiness
