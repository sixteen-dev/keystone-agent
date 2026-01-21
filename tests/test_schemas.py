"""Tests for Pydantic schemas."""

import pytest
from pydantic import ValidationError

from keystone_agent.schemas import (
    BoardFinalOutput,
    BoardMemberOutput,
    BoardRequest,
    BoardVote,
    DayTask,
    Experiment,
    ProductPuristOutput,
    ProjectContext,
    ProjectStage,
    PuristVerdict,
    RequestMode,
    Verdict,
)


class TestBoardRequest:
    """Tests for BoardRequest schema."""

    def test_valid_review_request(self):
        """Test creating a valid review request."""
        request = BoardRequest(
            mode=RequestMode.REVIEW,
            request_text="I'm building an AI tool",
        )
        assert request.mode == RequestMode.REVIEW
        assert request.request_text == "I'm building an AI tool"

    def test_request_text_too_short(self):
        """Test that short request text is rejected."""
        with pytest.raises(ValidationError):
            BoardRequest(
                mode=RequestMode.REVIEW,
                request_text="short",  # < 10 chars
            )

    def test_decide_mode_with_options(self):
        """Test decide mode with options."""
        request = BoardRequest(
            mode=RequestMode.DECIDE,
            request_text="Which approach should I take?",
            option_a="Build mobile first",
            option_b="Build web first",
        )
        assert request.option_a == "Build mobile first"
        assert request.option_b == "Build web first"

    def test_get_formatted_request(self):
        """Test request formatting."""
        request = BoardRequest(
            mode=RequestMode.DECIDE,
            request_text="Which approach?",
            option_a="Option A details",
            option_b="Option B details",
        )
        formatted = request.get_formatted_request()
        assert "Mode: decide" in formatted
        assert "Option A: Option A details" in formatted
        assert "Option B: Option B details" in formatted


class TestBoardMemberOutput:
    """Tests for BoardMemberOutput schema."""

    def test_valid_output(self, sample_specialist_output):
        """Test creating a valid board member output."""
        output = BoardMemberOutput(**sample_specialist_output)
        assert output.agent_name == "Lynx"
        assert output.verdict == Verdict.GO
        assert len(output.top_3_reasons) == 3

    def test_invalid_reason_count(self, sample_specialist_output):
        """Test that wrong number of reasons is rejected."""
        sample_specialist_output["top_3_reasons"] = ["only one"]
        with pytest.raises(ValidationError):
            BoardMemberOutput(**sample_specialist_output)

    def test_confidence_bounds(self, sample_specialist_output):
        """Test confidence must be between 0 and 1."""
        sample_specialist_output["confidence"] = 1.5
        with pytest.raises(ValidationError):
            BoardMemberOutput(**sample_specialist_output)


class TestProductPuristOutput:
    """Tests for ProductPuristOutput schema."""

    def test_valid_purist_output(self):
        """Test creating a valid purist output."""
        output = ProductPuristOutput(
            verdict=PuristVerdict.GO,
            core_promise_12_words="Build faster, ship more",
            flagship_experience="One-click deploy",
            cut_list_3=["Settings page", "Analytics", "Team features"],
            whats_missing_or_broken="No clear onboarding",
            hard_questions_if_vague_3=[
                "Who is this for?",
                "What problem does it solve?",
                "Why now?",
            ],
            next_2_actions=["Define ICP", "Ship MVP"],
            confidence=0.8,
        )
        assert output.verdict == PuristVerdict.GO
        assert output.agent_name == "Razor"

    def test_core_promise_word_limit(self):
        """Test that core promise enforces 12 word limit."""
        with pytest.raises(ValidationError):
            ProductPuristOutput(
                verdict=PuristVerdict.GO,
                core_promise_12_words="This is a very long core promise that has way more than twelve words in it and should fail",
                flagship_experience="Test",
                cut_list_3=["A", "B", "C"],
                whats_missing_or_broken="Nothing",
                hard_questions_if_vague_3=["Q1", "Q2", "Q3"],
                next_2_actions=["A1", "A2"],
                confidence=0.5,
            )


class TestBoardFinalOutput:
    """Tests for BoardFinalOutput schema."""

    def test_valid_final_output(self):
        """Test creating a valid final output."""
        output = BoardFinalOutput(
            request_type=RequestMode.REVIEW,
            final_verdict=Verdict.GO,
            final_summary="The board recommends proceeding.",
            why_this_verdict=["Strong product fit", "Clear distribution", "Low risk"],
            key_tradeoffs=["Speed vs quality", "Scope vs time", "Build vs buy"],
            top_risks=["Competition", "Adoption", "Technical"],
            next_3_actions=["Validate", "Build", "Ship"],
            one_week_plan=[
                DayTask(day="Day 1-2", task="Validate"),
                DayTask(day="Day 3-4", task="Build"),
                DayTask(day="Day 5-7", task="Ship"),
            ],
            single_best_experiment=Experiment(
                hypothesis="If X then Y",
                test="Do Z",
                success_metric="50% conversion",
                timebox="1 week",
            ),
            board_votes=[
                BoardVote(agent_name="Lynx", role="product_operator", verdict="go", confidence=0.8),
            ],
            confidence=0.75,
        )
        assert output.final_verdict == Verdict.GO
        assert len(output.one_week_plan) == 3
