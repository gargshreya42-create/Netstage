"""
ORM models for NetSage AI.

Design notes:
- `evidence`, `fix_steps` and similar list/JSON-ish fields are stored as JSON
  text columns (SQLite has no native array type) and (de)serialized in the
  service layer / schemas.
- Every table has `id` as the surrogate primary key plus a human-friendly
  business key where relevant (`case_id`).
"""
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database.session import Base


def utcnow():
    return datetime.now(timezone.utc)


class SeverityLevel(str, enum.Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class ReviewDecision(str, enum.Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    ACCEPTED = "ACCEPTED"
    EDITED = "EDITED"
    REJECTED = "REJECTED"


class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String(32), unique=True, index=True, nullable=False)
    symptom = Column(Text, nullable=False)
    topology_note = Column(Text, nullable=True)
    show_outputs = Column(Text, nullable=False)  # raw multi-command terminal text
    expected_fault = Column(Text, nullable=True)  # ground-truth label for the dataset
    osi_layer = Column(String(64), nullable=True)
    concept_tag = Column(String(64), nullable=False, index=True)  # VLAN, DHCP, DNS, ...
    severity = Column(String(16), nullable=False, default=SeverityLevel.MEDIUM.value)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    diagnoses = relationship("Diagnosis", back_populates="case", cascade="all, delete-orphan")


class Diagnosis(Base):
    __tablename__ = "diagnoses"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String(32), ForeignKey("cases.case_id"), nullable=False, index=True)

    root_cause = Column(Text, nullable=False)
    osi_layer = Column(String(64), nullable=True)
    confidence = Column(String(16), nullable=False)  # Low | Medium | High
    severity = Column(String(16), nullable=False)
    evidence = Column(Text, nullable=False)  # JSON-encoded list[str]
    next_command = Column(Text, nullable=True)
    fix_steps = Column(Text, nullable=False)  # JSON-encoded list[str]
    reasoning = Column(Text, nullable=True)

    rule_checker_result = Column(Text, nullable=True)  # JSON-encoded deterministic result
    source = Column(String(16), default="ai")  # "ai" | "rules_only"
    requires_human_review = Column(Integer, default=1)  # boolean-as-int for SQLite portability

    status = Column(String(24), default=ReviewDecision.PENDING_REVIEW.value, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    case = relationship("Case", back_populates="diagnoses")
    review = relationship("Review", back_populates="diagnosis", uselist=False, cascade="all, delete-orphan")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    diagnosis_id = Column(Integer, ForeignKey("diagnoses.id"), nullable=False, index=True)

    decision = Column(String(24), nullable=False)  # ACCEPTED | EDITED | REJECTED
    original_commands = Column(Text, nullable=True)  # JSON-encoded list[str] (AI's fix_steps)
    edited_commands = Column(Text, nullable=True)  # JSON-encoded list[str], only for EDITED
    reviewer_comment = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), default=utcnow)

    diagnosis = relationship("Diagnosis", back_populates="review")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String(32), nullable=False, index=True)
    diagnosis_id = Column(Integer, nullable=True, index=True)
    event_type = Column(String(48), nullable=False)
    # e.g. CASE_CREATED, RULE_CHECK_RUN, AI_DIAGNOSIS_CREATED,
    #      REVIEW_APPROVED, REVIEW_EDITED, REVIEW_REJECTED, VERIFICATION_RUN
    details = Column(Text, nullable=True)  # JSON-encoded free-form payload
    timestamp = Column(DateTime(timezone=True), default=utcnow)
