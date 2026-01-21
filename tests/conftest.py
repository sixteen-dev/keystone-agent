"""Pytest fixtures for Keystone Agent tests."""

import os
import tempfile
from pathlib import Path

import pytest

from keystone_agent.storage import reset_storage


@pytest.fixture(autouse=True)
def reset_storage_between_tests():
    """Reset storage singleton between tests."""
    reset_storage()
    yield
    reset_storage()


@pytest.fixture
def temp_db_path():
    """Provide a temporary database path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test.db"


@pytest.fixture
def mock_openai_key(monkeypatch):
    """Set a mock OpenAI API key."""
    monkeypatch.setenv("KEYSTONE_OPENAI_API_KEY", "sk-test-key")


@pytest.fixture
def sample_board_request():
    """Provide a sample board request."""
    from keystone_agent.schemas import BoardRequest, RequestMode

    return BoardRequest(
        mode=RequestMode.REVIEW,
        request_text="I'm building an AI-powered code review tool for small teams",
        project_id="test-project",
    )


@pytest.fixture
def sample_specialist_output():
    """Provide a sample specialist output."""
    return {
        "agent_name": "Lynx",
        "role": "product_operator",
        "verdict": "go",
        "top_3_reasons": [
            "Clear pain point: code review is slow and inconsistent",
            "Small teams are underserved by existing tools",
            "AI can provide 24/7 review availability",
        ],
        "top_3_risks": [
            "Trust barrier: developers may not trust AI reviews",
            "Integration complexity with existing workflows",
            "False positives could erode trust quickly",
        ],
        "assumptions": [
            "Teams want faster code reviews",
            "AI quality is good enough for meaningful feedback",
        ],
        "missing_info": [
            "Target team size",
            "Pricing expectations",
        ],
        "next_3_actions": [
            "Interview 5 small team leads about review pain",
            "Build MVP that reviews a single PR",
            "Test with 3 beta teams for 2 weeks",
        ],
        "one_experiment": {
            "hypothesis": "If AI catches 50% of issues that humans catch, teams will adopt",
            "test": "Run AI review in parallel with human review for 10 PRs",
            "success_metric": "AI catches 50%+ of human-flagged issues",
            "timebox": "1 week",
        },
        "confidence": 0.72,
    }
