"""
Human review service.

Implements the mandatory human-in-the-loop gate: every Diagnosis must be
explicitly Approved, Edited, or Rejected by a human reviewer before it is
considered actionable. This module never executes any Cisco command — it
only records the review decision and (for approvals) simulates verification.
"""
import json
from typing import Optional

from sqlalchemy.orm import Session

from app.models.models import Diagnosis, Review, ReviewDecision
from app.services.audit_service import log_event


class ReviewError(Exception):
    pass


def _get_diagnosis_or_raise(db: Session, diagnosis_id: int) -> Diagnosis:
    diagnosis = db.query(Diagnosis).filter(Diagnosis.id == diagnosis_id).first()
    if not diagnosis:
        raise ReviewError(f"Diagnosis {diagnosis_id} not found")
    if diagnosis.review is not None:
        raise ReviewError(
            f"Diagnosis {diagnosis_id} has already been reviewed "
            f"(decision: {diagnosis.review.decision}). Re-run diagnosis to review again."
        )
    return diagnosis


def approve_diagnosis(db: Session, diagnosis_id: int, reviewer_comment: Optional[str] = None) -> Review:
    diagnosis = _get_diagnosis_or_raise(db, diagnosis_id)
    original_commands = json.loads(diagnosis.fix_steps) if diagnosis.fix_steps else []

    review = Review(
        diagnosis_id=diagnosis.id,
        decision=ReviewDecision.ACCEPTED.value,
        original_commands=json.dumps(original_commands),
        edited_commands=None,
        reviewer_comment=reviewer_comment,
        rejection_reason=None,
    )
    diagnosis.status = ReviewDecision.ACCEPTED.value

    db.add(review)
    db.add(diagnosis)
    db.commit()
    db.refresh(review)

    # IMPORTANT: this only *simulates* deployment for the demo. NetSage AI
    # never executes commands against a real or simulated device automatically.
    log_event(
        db,
        case_id=diagnosis.case_id,
        diagnosis_id=diagnosis.id,
        event_type="REVIEW_APPROVED",
        details={
            "commands_approved": original_commands,
            "reviewer_comment": reviewer_comment,
            "note": "Simulated only — no commands were executed against any real or virtual device.",
        },
    )

    return review


def edit_diagnosis(
    db: Session, diagnosis_id: int, edited_commands: list, reviewer_comment: Optional[str] = None
) -> Review:
    diagnosis = _get_diagnosis_or_raise(db, diagnosis_id)
    original_commands = json.loads(diagnosis.fix_steps) if diagnosis.fix_steps else []

    if not edited_commands:
        raise ReviewError("edited_commands must not be empty for an EDIT decision")

    review = Review(
        diagnosis_id=diagnosis.id,
        decision=ReviewDecision.EDITED.value,
        original_commands=json.dumps(original_commands),
        edited_commands=json.dumps(edited_commands),
        reviewer_comment=reviewer_comment,
        rejection_reason=None,
    )
    diagnosis.status = ReviewDecision.EDITED.value

    db.add(review)
    db.add(diagnosis)
    db.commit()
    db.refresh(review)

    log_event(
        db,
        case_id=diagnosis.case_id,
        diagnosis_id=diagnosis.id,
        event_type="REVIEW_EDITED",
        details={
            "original_commands": original_commands,
            "edited_commands": edited_commands,
            "reviewer_comment": reviewer_comment,
        },
    )

    return review


def reject_diagnosis(
    db: Session, diagnosis_id: int, rejection_reason: str, reviewer_comment: Optional[str] = None
) -> Review:
    diagnosis = _get_diagnosis_or_raise(db, diagnosis_id)
    original_commands = json.loads(diagnosis.fix_steps) if diagnosis.fix_steps else []

    if not rejection_reason or not rejection_reason.strip():
        raise ReviewError("rejection_reason is required for a REJECT decision")

    review = Review(
        diagnosis_id=diagnosis.id,
        decision=ReviewDecision.REJECTED.value,
        original_commands=json.dumps(original_commands),
        edited_commands=None,
        reviewer_comment=reviewer_comment,
        rejection_reason=rejection_reason,
    )
    diagnosis.status = ReviewDecision.REJECTED.value

    db.add(review)
    db.add(diagnosis)
    db.commit()
    db.refresh(review)

    log_event(
        db,
        case_id=diagnosis.case_id,
        diagnosis_id=diagnosis.id,
        event_type="REVIEW_REJECTED",
        details={
            "rejection_reason": rejection_reason,
            "reviewer_comment": reviewer_comment,
            "ai_root_cause": diagnosis.root_cause,
        },
    )

    return review


def review_to_dict(review: Review) -> dict:
    return {
        "id": review.id,
        "diagnosis_id": review.diagnosis_id,
        "decision": review.decision,
        "original_commands": json.loads(review.original_commands) if review.original_commands else [],
        "edited_commands": json.loads(review.edited_commands) if review.edited_commands else None,
        "reviewer_comment": review.reviewer_comment,
        "rejection_reason": review.rejection_reason,
        "reviewed_at": review.reviewed_at,
    }


def list_pending_reviews(db: Session):
    """Diagnoses awaiting human review (the 'Review Queue' page)."""
    return db.query(Diagnosis).filter(Diagnosis.status == ReviewDecision.PENDING_REVIEW.value).order_by(
        Diagnosis.created_at.asc()
    ).all()
