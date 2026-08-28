"""
Analytics service.

Every number here is computed live from the database — nothing is
hardcoded. This is what backs both the Dashboard overview cards and the
dedicated Analytics page.
"""
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import Case, Diagnosis, ReviewDecision


def compute_analytics(db: Session) -> dict:
    total_cases = db.query(Case).count()
    diagnosed_cases = db.query(Diagnosis.case_id).distinct().count()

    pending_review = db.query(Diagnosis).filter(Diagnosis.status == ReviewDecision.PENDING_REVIEW.value).count()
    accepted = db.query(Diagnosis).filter(Diagnosis.status == ReviewDecision.ACCEPTED.value).count()
    edited = db.query(Diagnosis).filter(Diagnosis.status == ReviewDecision.EDITED.value).count()
    rejected = db.query(Diagnosis).filter(Diagnosis.status == ReviewDecision.REJECTED.value).count()

    reviewed_total = accepted + edited + rejected
    ai_agreement_rate = (accepted / reviewed_total * 100) if reviewed_total > 0 else 0.0

    critical_issues = db.query(Diagnosis).filter(Diagnosis.severity == "Critical").count()

    # Issue type distribution: pulled from Case.concept_tag (the dataset's
    # canonical categorization), not from free-text AI output, so it's
    # always one of the 8 known categories.
    issue_rows = (
        db.query(Case.concept_tag, func.count(Case.id))
        .group_by(Case.concept_tag)
        .all()
    )
    issue_type_distribution = {tag: count for tag, count in issue_rows}

    # Severity distribution across cases (dataset-level), ordered consistently.
    severity_rows = (
        db.query(Case.severity, func.count(Case.id))
        .group_by(Case.severity)
        .all()
    )
    severity_order = ["Low", "Medium", "High", "Critical"]
    raw_severity = {sev: count for sev, count in severity_rows}
    severity_distribution = {sev: raw_severity.get(sev, 0) for sev in severity_order if sev in raw_severity or True}
    # Only include severities that actually appear in the data OR are part
    # of the standard scale (keeps chart axes stable even at 0).
    severity_distribution = {sev: raw_severity.get(sev, 0) for sev in severity_order}

    return {
        "total_cases": total_cases,
        "diagnosed_cases": diagnosed_cases,
        "pending_review": pending_review,
        "accepted": accepted,
        "edited": edited,
        "rejected": rejected,
        "ai_agreement_rate": round(ai_agreement_rate, 1),
        "critical_issues": critical_issues,
        "issue_type_distribution": issue_type_distribution,
        "severity_distribution": severity_distribution,
    }
