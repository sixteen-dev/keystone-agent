"""Tests for consensus logic."""

import pytest

from keystone_agent.core.consensus import (
    aggregate_actions,
    apply_consensus_rules,
    select_best_experiment,
)
from keystone_agent.schemas import Verdict


class TestConsensusRules:
    """Tests for consensus rule application."""

    def test_no_go_threshold(self):
        """Test that 2+ no_go votes results in NO_GO verdict."""
        outputs = {
            "Lynx": {"verdict": "no_go", "confidence": 0.6},
            "Wildfire": {"verdict": "no_go", "confidence": 0.5},
            "Bedrock": {"verdict": "go", "confidence": 0.7},
        }
        verdict, confidence, reasons = apply_consensus_rules(outputs, "review")
        assert verdict == Verdict.NO_GO
        assert "2 specialists voted NO_GO" in reasons[0]

    def test_razor_veto(self):
        """Test that Razor CUT/REFRAME blocks GO."""
        outputs = {
            "Lynx": {"verdict": "go", "confidence": 0.6},
            "Wildfire": {"verdict": "go", "confidence": 0.6},
            "Razor": {"verdict": "CUT", "confidence": 0.8},
        }
        verdict, confidence, reasons = apply_consensus_rules(outputs, "review")
        assert verdict == Verdict.PIVOT
        assert any("Razor" in r for r in reasons)

    def test_razor_veto_override(self):
        """Test that Razor veto can be overridden with high confidence."""
        outputs = {
            "Lynx": {"verdict": "go", "confidence": 0.8},
            "Wildfire": {"verdict": "go", "confidence": 0.8},
            "Razor": {"verdict": "CUT", "confidence": 0.5},
        }
        verdict, confidence, reasons = apply_consensus_rules(outputs, "review")
        # Should NOT result in PIVOT because Lynx and Wildfire have >= 0.75 confidence
        assert verdict != Verdict.NO_GO

    def test_all_agents_failed(self):
        """Test handling when all agents fail."""
        outputs = {
            "Lynx": {"failed": True, "error": "timeout"},
            "Wildfire": {"failed": True, "error": "timeout"},
        }
        verdict, confidence, reasons = apply_consensus_rules(outputs, "review")
        assert verdict == Verdict.UNCLEAR
        assert confidence == 0.3

    def test_majority_go(self):
        """Test that majority GO results in GO verdict."""
        outputs = {
            "Lynx": {"verdict": "go", "confidence": 0.7},
            "Wildfire": {"verdict": "go", "confidence": 0.8},
            "Bedrock": {"verdict": "go", "confidence": 0.6},
            "Leverage": {"verdict": "pivot", "confidence": 0.5},
            "Sentinel": {"verdict": "go", "confidence": 0.7},
        }
        verdict, confidence, _ = apply_consensus_rules(outputs, "review")
        assert verdict == Verdict.GO


class TestAggregateActions:
    """Tests for action aggregation."""

    def test_aggregates_from_multiple_agents(self):
        """Test that actions are aggregated from multiple agents."""
        outputs = {
            "Lynx": {
                "next_3_actions": ["Interview users", "Build MVP", "Test"],
            },
            "Wildfire": {
                "next_3_actions": ["Post on Reddit", "Build MVP", "Measure"],
            },
        }
        actions = aggregate_actions(outputs)
        assert len(actions) <= 3
        # Should deduplicate "Build MVP"
        assert sum(1 for a in actions if "MVP" in a) <= 1

    def test_includes_razor_actions(self):
        """Test that Razor's 2 actions are included."""
        outputs = {
            "Razor": {
                "next_2_actions": ["Define ICP", "Ship MVP"],
            },
        }
        actions = aggregate_actions(outputs)
        assert any("ICP" in a or "Ship" in a for a in actions)

    def test_handles_failed_agents(self):
        """Test that failed agents are skipped."""
        outputs = {
            "Lynx": {"failed": True},
            "Wildfire": {
                "next_3_actions": ["Action 1", "Action 2", "Action 3"],
            },
        }
        actions = aggregate_actions(outputs)
        assert len(actions) == 3


class TestSelectBestExperiment:
    """Tests for experiment selection."""

    def test_prefers_shorter_timebox(self):
        """Test that shorter timeboxes are preferred."""
        outputs = {
            "Lynx": {
                "one_experiment": {
                    "hypothesis": "Test",
                    "test": "Do thing",
                    "success_metric": "Works",
                    "timebox": "1 month",
                },
            },
            "Wildfire": {
                "one_experiment": {
                    "hypothesis": "Test",
                    "test": "Do thing",
                    "success_metric": "50% conversion",
                    "timebox": "3 days",
                },
            },
        }
        experiment = select_best_experiment(outputs)
        assert "day" in experiment["timebox"].lower()

    def test_prefers_quantitative_metrics(self):
        """Test that quantitative metrics are preferred."""
        outputs = {
            "Lynx": {
                "one_experiment": {
                    "hypothesis": "Test",
                    "test": "Do thing",
                    "success_metric": "Users like it",
                    "timebox": "1 week",
                },
            },
            "Wildfire": {
                "one_experiment": {
                    "hypothesis": "Test",
                    "test": "Do thing",
                    "success_metric": "50% conversion rate",
                    "timebox": "1 week",
                },
            },
        }
        experiment = select_best_experiment(outputs)
        assert "%" in experiment["success_metric"]

    def test_handles_no_experiments(self):
        """Test fallback when no experiments available."""
        outputs = {
            "Lynx": {"failed": True},
        }
        experiment = select_best_experiment(outputs)
        assert "hypothesis" in experiment
        assert experiment["timebox"] == "1 week"
