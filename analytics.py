"""
Analytics API.

GET /api/analytics - live dashboard/analytics metrics computed from the
database (never hardcoded), backing both the Dashboard overview and the
dedicated Analytics page.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.review_schemas import AnalyticsOut
from app.services.analytics_service import compute_analytics

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("", response_model=AnalyticsOut)
def get_analytics(db: Session = Depends(get_db)):
    return compute_analytics(db)
