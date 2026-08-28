"""
Deterministic rule checker API.

POST /api/rules/check/{case_id} - run the regex-based rule checker against
a case's evidence and persist nothing (read-only, always safe to re-run).
This is intentionally separate from /api/diagnose, which additionally
invokes the AI engine and stores a Diagnosis record.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.rules.checker import run_rule_checks
from app.schemas.diagnosis_schemas import RuleCheckResult
from app.services import case_service
from app.services.audit_service import log_event

router = APIRouter(prefix="/api/rules", tags=["rules"])


@router.post("/check/{case_id}", response_model=RuleCheckResult)
def check_case(case_id: str, db: Session = Depends(get_db)):
    case = case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")

    result = run_rule_checks(case.show_outputs, case.topology_note or "")

    log_event(
        db,
        case_id=case.case_id,
        diagnosis_id=None,
        event_type="RULE_CHECK_RUN",
        details={"status": result.status, "error_count": len(result.errors)},
    )

    return result
