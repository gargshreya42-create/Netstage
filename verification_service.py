"""
Simulated post-fix verification.

Per spec Section 19: after a diagnosis is approved, show a simulated
before/after verification (e.g. ping failure -> ping success). This is
ALWAYS a safe simulation — it never sends anything to a real or virtual
network device. The "success" outcome is derived deterministically from
the diagnosis's root cause/fix, not from any live probe.
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.models import Diagnosis
from app.services.audit_service import log_event


def run_simulated_verification(db: Session, diagnosis: Diagnosis) -> dict:
    """
    Returns a simulated before/after verification result for an approved
    or edited diagnosis. Purely illustrative — no real commands are run.
    """
    target = _infer_verification_target(diagnosis)

    result = {
        "diagnosis_id": diagnosis.id,
        "case_id": diagnosis.case_id,
        "target": target,
        "before_fix": {
            "command": f"ping {target}",
            "result": "FAILED",
            "detail": "Request timed out (4/4 lost) — matches the reported symptom.",
        },
        "after_fix": {
            "command": f"ping {target}",
            "result": "SUCCESS",
            "detail": "Reply received — simulated result assuming the approved/edited fix was applied.",
        },
        "verification_status": "Verification Passed (Simulated)",
        "simulated": True,
        "note": (
            "This is a safe simulation for demonstration purposes only. "
            "NetSage AI never executes commands against a real or virtual network device."
        ),
    }

    log_event(
        db,
        case_id=diagnosis.case_id,
        diagnosis_id=diagnosis.id,
        event_type="VERIFICATION_RUN",
        details={"target": target, "verification_status": result["verification_status"]},
    )

    return result


def _infer_verification_target(diagnosis: Diagnosis) -> str:
    """Best-effort pick of a plausible target host/IP to display in the simulated ping."""
    import re

    text = (diagnosis.reasoning or "") + " " + (diagnosis.root_cause or "")
    ip_match = re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", text)
    if ip_match:
        return ip_match.group(0)
    return "target host"
