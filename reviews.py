"""
Human review API — the mandatory approval gate.

POST /api/reviews/{diagnosis_id}/approve
POST /api/reviews/{diagnosis_id}/edit
POST /api/reviews/{diagnosis_id}/reject
GET  /api/reviews/{diagnosis_id}/verify   - simulated post-fix verification
                                             (only meaningful after approve/edit)
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.models import ReviewDecision
from app.schemas.diagnosis_schemas import DiagnosisOut
from app.schemas.review_schemas import (
    ApproveRequest,
    EditRequest,
    RejectRequest,
    ReviewOut,
    VerificationOut,
)
from app.services import diagnosis_service, review_service, verification_service
from app.services.review_service import ReviewError

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.post("/{diagnosis_id}/approve", response_model=ReviewOut)
def approve(diagnosis_id: int, payload: ApproveRequest = ApproveRequest(), db: Session = Depends(get_db)):
    try:
        review = review_service.approve_diagnosis(db, diagnosis_id, reviewer_comment=payload.reviewer_comment)
    except ReviewError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return review_service.review_to_dict(review)


@router.post("/{diagnosis_id}/edit", response_model=ReviewOut)
def edit(diagnosis_id: int, payload: EditRequest, db: Session = Depends(get_db)):
    try:
        review = review_service.edit_diagnosis(
            db, diagnosis_id, edited_commands=payload.edited_commands, reviewer_comment=payload.reviewer_comment
        )
    except ReviewError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return review_service.review_to_dict(review)


@router.post("/{diagnosis_id}/reject", response_model=ReviewOut)
def reject(diagnosis_id: int, payload: RejectRequest, db: Session = Depends(get_db)):
    try:
        review = review_service.reject_diagnosis(
            db,
            diagnosis_id,
            rejection_reason=payload.rejection_reason,
            reviewer_comment=payload.reviewer_comment,
        )
    except ReviewError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return review_service.review_to_dict(review)


@router.get("/{diagnosis_id}/verify", response_model=VerificationOut)
def verify(diagnosis_id: int, db: Session = Depends(get_db)):
    diagnosis = diagnosis_service.get_diagnosis(db, diagnosis_id)
    if not diagnosis:
        raise HTTPException(status_code=404, detail=f"Diagnosis {diagnosis_id} not found")
    if diagnosis.status not in (ReviewDecision.ACCEPTED.value, ReviewDecision.EDITED.value):
        raise HTTPException(
            status_code=400,
            detail="Verification is only available after a diagnosis has been Approved or Edited.",
        )
    return verification_service.run_simulated_verification(db, diagnosis)


@router.get("/queue", response_model=List[DiagnosisOut])
def get_review_queue(db: Session = Depends(get_db)):
    pending = review_service.list_pending_reviews(db)
    return [diagnosis_service.diagnosis_to_dict(d) for d in pending]
