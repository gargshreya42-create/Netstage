"""
Audit logging service.

Every meaningful state change in the system (case creation, rule checks,
AI diagnoses, human review decisions, verification runs) is recorded here.
This is the backbone of the "AI proposes -> Human decides -> Action is
logged" design principle.
"""
import json
from typing import Optional

from sqlalchemy.orm import Session

from app.models.models import AuditLog


def log_event(
    db: Session,
    case_id: str,
    diagnosis_id: Optional[int],
    event_type: str,
    details: Optional[dict] = None,
) -> AuditLog:
    entry = AuditLog(
        case_id=case_id,
        diagnosis_id=diagnosis_id,
        event_type=event_type,
        details=json.dumps(details or {}),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def list_audit_logs(
    db: Session,
    case_id: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 200,
):
    query = db.query(AuditLog)
    if case_id:
        query = query.filter(AuditLog.case_id == case_id)
    if event_type:
        query = query.filter(AuditLog.event_type == event_type)
    return query.order_by(AuditLog.timestamp.desc()).limit(limit).all()


def audit_log_to_dict(entry: AuditLog) -> dict:
    return {
        "id": entry.id,
        "case_id": entry.case_id,
        "diagnosis_id": entry.diagnosis_id,
        "event_type": entry.event_type,
        "details": json.loads(entry.details) if entry.details else {},
        "timestamp": entry.timestamp,
    }
