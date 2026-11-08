"""Test runner script for all tests."""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import pytest

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        # Run all tests
        args = [
            "tests/unit/",
            "tests/integration/",
            "tests/security/",
            "-v",
            "--tb=short",
        ]
    sys.exit(pytest.main(args))
