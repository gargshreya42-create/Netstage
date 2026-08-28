from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class RuleError(BaseModel):
    type: str
    interface: Optional[str] = None
    severity: str
    evidence: str


class RuleCheckResult(BaseModel):
    status: str  # "ERRORS_DETECTED" | "NO_ERRORS_DETECTED"
    errors: List[RuleError] = Field(default_factory=list)


class AIDiagnosisPayload(BaseModel):
    """
    Strict schema the LLM's JSON output is parsed/validated into.
    Any response that doesn't fit this shape is treated as a parse failure
    by the AI engine (see app/ai/engine.py) and surfaced as an error rather
    than silently accepted.
    """
    root_cause: str
    osi_layer: str
    confidence: str  # Low | Medium | High
    severity: str  # Low | Medium | High | Critical
    evidence: List[str]
    next_command: Optional[str] = None
    fix_steps: List[str]
    reasoning: str
    requires_human_review: bool = True

    @field_validator("requires_human_review")
    @classmethod
    def force_human_review(cls, v):
        # Hard safety invariant: no AI output may ever waive human review,
        # regardless of what the model returned.
        return True


class DiagnosisOut(BaseModel):
    id: int
    case_id: str
    root_cause: str
    osi_layer: Optional[str]
    confidence: str
    severity: str
    evidence: List[str]
    next_command: Optional[str]
    fix_steps: List[str]
    reasoning: Optional[str]
    rule_checker_result: Optional[RuleCheckResult] = None
    source: str
    requires_human_review: bool
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DiagnoseRequest(BaseModel):
    force_ai: bool = True  # if False, only run the deterministic rule checker
