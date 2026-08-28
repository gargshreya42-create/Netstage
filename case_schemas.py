from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

VALID_SEVERITIES = {"Low", "Medium", "High", "Critical"}
VALID_CONCEPT_TAGS = {"VLAN", "Gateway", "DHCP", "DNS", "Routing", "ACL", "NAT", "Wireless"}


class CaseBase(BaseModel):
    symptom: str
    topology_note: Optional[str] = None
    show_outputs: str
    expected_fault: Optional[str] = None
    osi_layer: Optional[str] = None
    concept_tag: str
    severity: str = Field(default="Medium")

    @field_validator("symptom", "show_outputs")
    @classmethod
    def not_blank(cls, v: str, info):
        if not v or not v.strip():
            raise ValueError(f"'{info.field_name}' must not be empty or whitespace-only")
        return v

    @field_validator("severity")
    @classmethod
    def valid_severity(cls, v: str):
        if v not in VALID_SEVERITIES:
            raise ValueError(f"severity must be one of {sorted(VALID_SEVERITIES)}, got '{v}'")
        return v

    @field_validator("concept_tag")
    @classmethod
    def valid_concept_tag(cls, v: str):
        if v not in VALID_CONCEPT_TAGS:
            raise ValueError(f"concept_tag must be one of {sorted(VALID_CONCEPT_TAGS)}, got '{v}'")
        return v


class CaseCreate(CaseBase):
    case_id: Optional[str] = None  # auto-generated if omitted (custom cases)


class CaseOut(CaseBase):
    id: int
    case_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CaseListItem(BaseModel):
    """Lightweight shape used by the case library list/search view."""
    case_id: str
    symptom: str
    concept_tag: str
    severity: str
    osi_layer: Optional[str] = None
    has_diagnosis: bool = False
    latest_status: Optional[str] = None

    model_config = {"from_attributes": True}
