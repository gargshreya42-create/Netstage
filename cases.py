"""
Case management API.

GET  /api/cases              - search/filter case library
GET  /api/cases/{case_id}    - full case detail
POST /api/cases               - create a custom case
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.case_schemas import CaseCreate, CaseListItem, CaseOut
from app.services import case_service

router = APIRouter(prefix="/api/cases", tags=["cases"])


@router.get("", response_model=List[CaseListItem])
def get_cases(
    search: Optional[str] = None,
    concept_tag: Optional[str] = None,
    severity: Optional[str] = None,
    db: Session = Depends(get_db),
):
    cases = case_service.list_cases(db, search=search, concept_tag=concept_tag, severity=severity)
    result = []
    for case in cases:
        result.append(
            CaseListItem(
                case_id=case.case_id,
                symptom=case.symptom,
                concept_tag=case.concept_tag,
                severity=case.severity,
                osi_layer=case.osi_layer,
                has_diagnosis=case_service.case_has_diagnosis(db, case.case_id),
                latest_status=case_service.get_latest_diagnosis_status(db, case.case_id),
            )
        )
    return result


@router.get("/{case_id}", response_model=CaseOut)
def get_case(case_id: str, db: Session = Depends(get_db)):
    case = case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    return case


@router.post("", response_model=CaseOut, status_code=201)
def create_case(payload: CaseCreate, db: Session = Depends(get_db)):
    try:
        return case_service.create_case(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
