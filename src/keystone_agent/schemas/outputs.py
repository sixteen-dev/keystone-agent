"""Output schemas for board responses."""

from enum import Enum

from pydantic import BaseModel, Field, field_validator

from keystone_agent.schemas.inputs import RequestMode


class Verdict(str, Enum):
    """Standard verdict from board members."""

    GO = "go"
    NO_GO = "no_go"
    PIVOT = "pivot"
    UNCLEAR = "unclear"


class PuristVerdict(str, Enum):
    """Special verdict from the Product Purist (Razor)."""

    GO = "GO"
    NO = "NO"
    CUT = "CUT"
    REFRAME = "REFRAME"


class Experiment(BaseModel):
    """A single experiment recommendation."""

    hypothesis: str = Field(..., description="If X then Y statement")
    test: str = Field(..., description="Concrete test to run")
    success_metric: str = Field(..., description="Measurable outcome")
    timebox: str = Field(..., description="Time limit for the experiment")


class BoardMemberOutput(BaseModel):
    """Standard output from most board members."""

    agent_name: str = Field(..., description="Codename of the agent")
    role: str = Field(..., description="Role identifier")
    verdict: Verdict
    top_3_reasons: list[str] = Field(..., min_length=3, max_length=3)
    top_3_risks: list[str] = Field(..., min_length=3, max_length=3)
    assumptions: list[str] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)
    next_3_actions: list[str] = Field(..., min_length=3, max_length=3)
    one_experiment: Experiment
    confidence: float = Field(..., ge=0.0, le=1.0)


class ProductPuristOutput(BaseModel):
    """Special output schema for the Product Purist (Razor)."""

    agent_name: str = Field(default="Razor", description="Codename: Razor")
    role: str = Field(default="product_purist")
    verdict: PuristVerdict
    core_promise_12_words: str = Field(..., max_length=120)
    flagship_experience: str
    cut_list_3: list[str] = Field(..., min_length=3, max_length=3)
    whats_missing_or_broken: str
    hard_questions_if_vague_3: list[str] = Field(..., min_length=3, max_length=3)
    next_2_actions: list[str] = Field(..., min_length=2, max_length=2)
    confidence: float = Field(..., ge=0.0, le=1.0)

    @field_validator("core_promise_12_words")
    @classmethod
    def validate_word_count(cls, v: str) -> str:
        """Ensure core promise is 12 words or less."""
        word_count = len(v.split())
        if word_count > 12:
            raise ValueError(f"Core promise must be 12 words or less, got {word_count}")
        return v


class DayTask(BaseModel):
    """A task for a specific day in the weekly plan."""

    day: str = Field(..., description="Day identifier (e.g., 'Day 1-2')")
    task: str = Field(..., description="Task description")


class BoardVote(BaseModel):
    """Summary of a single board member's vote."""

    agent_name: str
    role: str
    verdict: str
    confidence: float


class BoardFinalOutput(BaseModel):
    """Final consolidated output from the board."""

    request_type: RequestMode
    final_verdict: Verdict
    final_summary: str = Field(..., description="2-3 sentence synthesis")
    why_this_verdict: list[str] = Field(..., min_length=3, max_length=3)
    key_tradeoffs: list[str] = Field(..., min_length=3, max_length=3)
    top_risks: list[str] = Field(..., min_length=3, max_length=3)
    next_3_actions: list[str] = Field(..., min_length=3, max_length=3)
    one_week_plan: list[DayTask] = Field(..., min_length=3)
    single_best_experiment: Experiment
    board_votes: list[BoardVote]
    confidence: float = Field(..., ge=0.0, le=1.0)
    assumptions: list[str] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)
    failed_agents: list[str] = Field(
        default_factory=list,
        description="Agents that failed to respond after retries",
    )
