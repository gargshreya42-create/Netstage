"""
Audit log API.

GET /api/audit - list audit log entries, optionally filtered by case_id
                  or event_type. Backs the Audit Log page in the UI.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.review_schemas import AuditLogOut
from app.services.audit_service import audit_log_to_dict, list_audit_logs

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("", response_model=List[AuditLogOut])
def get_audit_log(
    case_id: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    entries = list_audit_logs(db, case_id=case_id, event_type=event_type, limit=limit)
    return [audit_log_to_dict(e) for e in entries]
