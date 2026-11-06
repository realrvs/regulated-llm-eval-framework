"""Test runner script."""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import pytest

if __name__ == "__main__":
    sys.exit(pytest.main([
        "-v",
        "--tb=short",
        "tests/unit/test_schemas.py",
        "tests/unit/test_datasets.py",
        "tests/security/test_pii.py",
    ]))
