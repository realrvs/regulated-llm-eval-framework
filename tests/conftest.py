"""Shared fixtures for tests."""

import pytest


@pytest.fixture
def sample_dataset_path():
    """Path to sample golden set dataset."""
    return "datasets/tax_qa_v1/sample.jsonl"
