"""
AI diagnosis API.

POST /api/diagnose/{case_id} - run rule checker + AI engine for a case,
persist a Diagnosis record (status=PENDING_REVIEW), and return it.

GET  /api/diagnoses           - list diagnoses (optionally filtered)
GET  /api/diagnoses/{id}      - fetch a single diagnosis
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.diagnosis_schemas import DiagnoseRequest, DiagnosisOut
from app.services import case_service, diagnosis_service

router = APIRouter(tags=["diagnosis"])


@router.post("/api/diagnose/{case_id}", response_model=DiagnosisOut)
def diagnose(case_id: str, payload: DiagnoseRequest = DiagnoseRequest(), db: Session = Depends(get_db)):
    case = case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")

    diagnosis = diagnosis_service.diagnose_case(db, case, force_ai=payload.force_ai)
    return diagnosis_service.diagnosis_to_dict(diagnosis)


@router.get("/api/diagnoses", response_model=List[DiagnosisOut])
def get_diagnoses(case_id: Optional[str] = None, status: Optional[str] = None, db: Session = Depends(get_db)):
    diagnoses = diagnosis_service.list_diagnoses(db, case_id=case_id, status=status)
    return [diagnosis_service.diagnosis_to_dict(d) for d in diagnoses]


@router.get("/api/diagnoses/{diagnosis_id}", response_model=DiagnosisOut)
def get_diagnosis(diagnosis_id: int, db: Session = Depends(get_db)):
    diagnosis = diagnosis_service.get_diagnosis(db, diagnosis_id)
    if not diagnosis:
        raise HTTPException(status_code=404, detail=f"Diagnosis {diagnosis_id} not found")
    return diagnosis_service.diagnosis_to_dict(diagnosis)
