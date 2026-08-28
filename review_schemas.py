from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class ApproveRequest(BaseModel):
    reviewer_comment: Optional[str] = None


class EditRequest(BaseModel):
    edited_commands: List[str]
    reviewer_comment: Optional[str] = None


class RejectRequest(BaseModel):
    rejection_reason: str
    reviewer_comment: Optional[str] = None


class ReviewOut(BaseModel):
    id: int
    diagnosis_id: int
    decision: str
    original_commands: List[str]
    edited_commands: Optional[List[str]] = None
    reviewer_comment: Optional[str] = None
    rejection_reason: Optional[str] = None
    reviewed_at: datetime

    model_config = {"from_attributes": True}


class AuditLogOut(BaseModel):
    id: int
    case_id: str
    diagnosis_id: Optional[int]
    event_type: str
    details: Optional[dict] = None
    timestamp: datetime

    model_config = {"from_attributes": True}


class VerificationStepResult(BaseModel):
    command: str
    result: str
    detail: str


class VerificationOut(BaseModel):
    diagnosis_id: int
    case_id: str
    target: str
    before_fix: VerificationStepResult
    after_fix: VerificationStepResult
    verification_status: str
    simulated: bool
    note: str


class AnalyticsOut(BaseModel):
    total_cases: int
    diagnosed_cases: int
    pending_review: int
    accepted: int
    edited: int
    rejected: int
    ai_agreement_rate: float
    critical_issues: int
    issue_type_distribution: dict
    severity_distribution: dict
