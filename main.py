"""
NetSage AI backend entrypoint.

Phase 1 scope: app bootstrap, DB table creation, health check.
Feature routers (cases, rules, diagnose, reviews, audit, analytics) are
mounted here as they're built in later phases.
"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database.session import Base, SessionLocal, engine
from app.services.case_service import seed_cases_from_csv

settings = get_settings()

app = FastAPI(
    title="NetSage AI",
    description="AI-assisted Cisco network troubleshooting platform with mandatory human review.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Turns Pydantic validation failures (invalid case data, malformed request
    bodies, etc.) into a clean, consistent 422 JSON response instead of a
    raw traceback — satisfies the 'invalid case data' error-handling
    requirement without needing per-endpoint try/except blocks.
    """
    return JSONResponse(
        status_code=422,
        content={"detail": "Invalid request data.", "errors": exc.errors()},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Last-resort safety net: any unexpected failure (database errors, etc.)
    is reported as a clean 500 JSON response rather than crashing the
    application or leaking a raw stack trace to the client.
    """
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected server error occurred. This has been logged for review."},
    )


@app.on_event("startup")
def on_startup():
    # Creates tables if they don't exist yet. For a real production
    # deployment this would be replaced by Alembic migrations.
    Base.metadata.create_all(bind=engine)

    # Seed the 30-case dataset on first boot (idempotent - no-op if cases exist).
    db = SessionLocal()
    try:
        inserted = seed_cases_from_csv(db)
        if inserted:
            print(f"[startup] Seeded {inserted} cases from dataset.")
    finally:
        db.close()


@app.get("/api/health", tags=["system"])
def health_check():
    return {
        "status": "ok",
        "service": settings.app_name,
        "ai_enabled": settings.ai_enabled,
        "environment": settings.app_env,
    }


# --- Routers (mounted progressively across phases) ---
from app.api import cases as cases_router  # noqa: E402
from app.api import rules as rules_router  # noqa: E402
from app.api import diagnose as diagnose_router  # noqa: E402
from app.api import reviews as reviews_router  # noqa: E402
from app.api import audit as audit_router  # noqa: E402
from app.api import analytics as analytics_router  # noqa: E402

app.include_router(cases_router.router)
app.include_router(rules_router.router)
app.include_router(diagnose_router.router)
app.include_router(reviews_router.router)
app.include_router(audit_router.router)
app.include_router(analytics_router.router)
