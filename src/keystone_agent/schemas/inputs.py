"""Input schemas for board requests."""

from enum import Enum

from pydantic import BaseModel, Field


class RequestMode(str, Enum):
    """Types of board requests."""

    REVIEW = "review"
    DECIDE = "decide"
    AUDIT = "audit"
    CREATIVE = "creative"


class ProjectStage(str, Enum):
    """Stage of the project being evaluated."""

    IDEA = "idea"
    MVP = "mvp"
    BETA = "beta"
    LAUNCHED = "launched"


class ProjectContext(BaseModel):
    """Optional context about the project."""

    stage: ProjectStage = ProjectStage.IDEA
    traction: str | None = Field(default=None, description="Current traction metrics or status")
    constraints: str | None = Field(default=None, description="Known constraints (time, budget)")
    previous_decisions: list[str] = Field(
        default_factory=list,
        description="Summary of previous board decisions for context",
    )


class BoardRequest(BaseModel):
    """Request to the board for evaluation."""

    mode: RequestMode
    request_text: str = Field(..., min_length=10, description="The main request/question")
    project_id: str | None = Field(default=None, description="Project identifier for history")
    context: ProjectContext | None = Field(default=None, description="Additional project context")

    # For decide mode
    option_a: str | None = Field(default=None, description="First option for decide mode")
    option_b: str | None = Field(default=None, description="Second option for decide mode")

    # For audit mode
    since_days: int = Field(default=14, ge=1, le=90, description="Days to look back for audit")

    def get_formatted_request(self) -> str:
        """Format the request for agent consumption."""
        parts = [f"Mode: {self.mode.value}", f"Request: {self.request_text}"]

        if self.mode == RequestMode.DECIDE:
            if self.option_a:
                parts.append(f"Option A: {self.option_a}")
            if self.option_b:
                parts.append(f"Option B: {self.option_b}")

        if self.mode == RequestMode.AUDIT:
            parts.append(f"Audit period: Last {self.since_days} days")

        if self.context:
            parts.append(f"Project stage: {self.context.stage.value}")
            if self.context.traction:
                parts.append(f"Traction: {self.context.traction}")
            if self.context.constraints:
                parts.append(f"Constraints: {self.context.constraints}")

        return "\n".join(parts)
