"""
Case management service.

Responsibilities:
- Seed the `cases` table from data/cases.csv on first run (idempotent).
- CRUD + search/filter operations used by the case library and
  troubleshooting workflow.
"""
import os
import uuid
from typing import List, Optional

import pandas as pd
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.models import Case, Diagnosis
from app.schemas.case_schemas import CaseCreate
from app.services.audit_service import log_event

DATA_CSV_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "cases.csv"
)


def seed_cases_from_csv(db: Session, csv_path: str = DATA_CSV_PATH) -> int:
    """
    Load cases.csv into the database if the table is currently empty.
    Returns the number of cases inserted. Safe to call on every startup.
    """
    existing_count = db.query(Case).count()
    if existing_count > 0:
        return 0

    csv_path = os.path.abspath(csv_path)
    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"Dataset not found at {csv_path}. Run backend/data/generate_cases.py first."
        )

    df = pd.read_csv(csv_path)
    required_cols = {
        "case_id", "symptom", "topology_note", "show_outputs",
        "expected_fault", "osi_layer", "concept_tag", "severity",
    }
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"cases.csv is missing required columns: {missing}")

    inserted = 0
    for _, row in df.iterrows():
        case = Case(
            case_id=str(row["case_id"]),
            symptom=str(row["symptom"]),
            topology_note=str(row.get("topology_note", "") or ""),
            show_outputs=str(row["show_outputs"]),
            expected_fault=str(row.get("expected_fault", "") or ""),
            osi_layer=str(row.get("osi_layer", "") or ""),
            concept_tag=str(row["concept_tag"]),
            severity=str(row["severity"]),
        )
        db.add(case)
        inserted += 1

    db.commit()
    log_event(db, case_id="SYSTEM", diagnosis_id=None, event_type="DATASET_SEEDED",
               details={"inserted": inserted, "source": csv_path})
    return inserted


def generate_custom_case_id(db: Session) -> str:
    """Generate a unique case_id for user-created custom cases, e.g. CUST-A1B2C3."""
    while True:
        candidate = f"CUST-{uuid.uuid4().hex[:6].upper()}"
        if not db.query(Case).filter(Case.case_id == candidate).first():
            return candidate


def create_case(db: Session, payload: CaseCreate) -> Case:
    case_id = payload.case_id or generate_custom_case_id(db)
    if db.query(Case).filter(Case.case_id == case_id).first():
        raise ValueError(f"case_id '{case_id}' already exists")

    case = Case(
        case_id=case_id,
        symptom=payload.symptom,
        topology_note=payload.topology_note,
        show_outputs=payload.show_outputs,
        expected_fault=payload.expected_fault,
        osi_layer=payload.osi_layer,
        concept_tag=payload.concept_tag,
        severity=payload.severity,
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    log_event(db, case_id=case.case_id, diagnosis_id=None, event_type="CASE_CREATED",
               details={"symptom": case.symptom, "concept_tag": case.concept_tag})
    return case


def get_case(db: Session, case_id: str) -> Optional[Case]:
    return db.query(Case).filter(Case.case_id == case_id).first()


def list_cases(
    db: Session,
    search: Optional[str] = None,
    concept_tag: Optional[str] = None,
    severity: Optional[str] = None,
) -> List[Case]:
    query = db.query(Case)

    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(Case.case_id.ilike(like), Case.symptom.ilike(like), Case.concept_tag.ilike(like))
        )
    if concept_tag:
        query = query.filter(Case.concept_tag == concept_tag)
    if severity:
        query = query.filter(Case.severity == severity)

    return query.order_by(Case.case_id.asc()).all()


def get_latest_diagnosis_status(db: Session, case_id: str) -> Optional[str]:
    diag = (
        db.query(Diagnosis)
        .filter(Diagnosis.case_id == case_id)
        .order_by(Diagnosis.created_at.desc())
        .first()
    )
    return diag.status if diag else None


def case_has_diagnosis(db: Session, case_id: str) -> bool:
    return db.query(Diagnosis).filter(Diagnosis.case_id == case_id).first() is not None
