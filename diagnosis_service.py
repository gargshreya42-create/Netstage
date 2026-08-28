"""
Diagnosis service.

Orchestrates: load case -> run deterministic rules -> run AI engine (if
available/requested) -> persist a Diagnosis row -> audit log the event.

This is the concrete implementation of "AI proposes -> Rule Checker
validates -> [Human reviews next, in review_service.py]".
"""
import json
from typing import Optional

from sqlalchemy.orm import Session

from app.ai.engine import AIEngineError, DiagnosisRequest, run_ai_diagnosis
from app.models.models import Case, Diagnosis, ReviewDecision
from app.rules.checker import run_rule_checks
from app.schemas.diagnosis_schemas import RuleCheckResult
from app.services.audit_service import log_event


class DiagnosisServiceError(Exception):
    pass


def diagnose_case(db: Session, case: Case, force_ai: bool = True) -> Diagnosis:
    """
    Run the full diagnosis pipeline for a case and persist the result.

    If AI is unavailable or fails, we still persist a rule-checker-only
    Diagnosis row (source="rules_only") rather than losing the rule-check
    work — the error is surfaced to the caller via the returned object's
    `reasoning` field and audit log, never by crashing.
    """
    rule_result: RuleCheckResult = run_rule_checks(case.show_outputs, case.topology_note or "")

    log_event(
        db,
        case_id=case.case_id,
        diagnosis_id=None,
        event_type="RULE_CHECK_RUN",
        details={"status": rule_result.status, "error_count": len(rule_result.errors)},
    )

    ai_payload = None
    ai_error: Optional[str] = None

    if force_ai:
        try:
            ai_payload = run_ai_diagnosis(
                DiagnosisRequest(
                    case_id=case.case_id,
                    symptom=case.symptom,
                    topology_note=case.topology_note or "",
                    show_outputs=case.show_outputs,
                    rule_check_result=rule_result,
                )
            )
        except AIEngineError as e:
            ai_error = str(e)

    if ai_payload is not None:
        diagnosis = Diagnosis(
            case_id=case.case_id,
            root_cause=ai_payload.root_cause,
            osi_layer=ai_payload.osi_layer,
            confidence=ai_payload.confidence,
            severity=ai_payload.severity,
            evidence=json.dumps(ai_payload.evidence),
            next_command=ai_payload.next_command,
            fix_steps=json.dumps(ai_payload.fix_steps),
            reasoning=ai_payload.reasoning,
            rule_checker_result=json.dumps(rule_result.model_dump()),
            source="ai",
            requires_human_review=1,
            status=ReviewDecision.PENDING_REVIEW.value,
        )
        event_type = "AI_DIAGNOSIS_CREATED"
        event_details = {
            "confidence": ai_payload.confidence,
            "severity": ai_payload.severity,
            "root_cause": ai_payload.root_cause,
        }
    else:
        # Fallback: rule-checker-only diagnosis. Still requires human review,
        # still fully auditable, just makes clear no AI reasoning happened.
        fallback_evidence = [e.evidence for e in rule_result.errors] or [
            "No deterministic rule matched; AI diagnosis unavailable for this run."
        ]
        diagnosis = Diagnosis(
            case_id=case.case_id,
            root_cause="AI diagnosis unavailable — see rule checker results and reasoning for details."
            if ai_error else "No AI diagnosis requested — rule checker results only.",
            osi_layer=None,
            confidence="Low",
            severity=case.severity,
            evidence=json.dumps(fallback_evidence),
            next_command=None,
            fix_steps=json.dumps([]),
            reasoning=ai_error or "AI diagnosis was not requested for this run.",
            rule_checker_result=json.dumps(rule_result.model_dump()),
            source="rules_only",
            requires_human_review=1,
            status=ReviewDecision.PENDING_REVIEW.value,
        )
        event_type = "RULES_ONLY_DIAGNOSIS_CREATED"
        event_details = {"ai_error": ai_error} if ai_error else {"reason": "ai_not_requested"}

    db.add(diagnosis)
    db.commit()
    db.refresh(diagnosis)

    log_event(db, case_id=case.case_id, diagnosis_id=diagnosis.id, event_type=event_type, details=event_details)

    return diagnosis


def get_diagnosis(db: Session, diagnosis_id: int) -> Optional[Diagnosis]:
    return db.query(Diagnosis).filter(Diagnosis.id == diagnosis_id).first()


def list_diagnoses(db: Session, case_id: Optional[str] = None, status: Optional[str] = None):
    query = db.query(Diagnosis)
    if case_id:
        query = query.filter(Diagnosis.case_id == case_id)
    if status:
        query = query.filter(Diagnosis.status == status)
    return query.order_by(Diagnosis.created_at.desc()).all()


def diagnosis_to_dict(diagnosis: Diagnosis) -> dict:
    """Deserialize JSON text columns back into Python objects for API responses."""
    return {
        "id": diagnosis.id,
        "case_id": diagnosis.case_id,
        "root_cause": diagnosis.root_cause,
        "osi_layer": diagnosis.osi_layer,
        "confidence": diagnosis.confidence,
        "severity": diagnosis.severity,
        "evidence": json.loads(diagnosis.evidence) if diagnosis.evidence else [],
        "next_command": diagnosis.next_command,
        "fix_steps": json.loads(diagnosis.fix_steps) if diagnosis.fix_steps else [],
        "reasoning": diagnosis.reasoning,
        "rule_checker_result": json.loads(diagnosis.rule_checker_result) if diagnosis.rule_checker_result else None,
        "source": diagnosis.source,
        "requires_human_review": bool(diagnosis.requires_human_review),
        "status": diagnosis.status,
        "created_at": diagnosis.created_at,
    }
