import re
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

CONTROL_CHAR_REGEX = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class RecipientInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    achievement: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, v: Any) -> str:
        if not isinstance(v, str):
            raise ValueError("Name must be a string")
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Name cannot be empty")
        if CONTROL_CHAR_REGEX.search(cleaned):
            raise ValueError("Name contains invalid control characters")
        return cleaned

    @field_validator("email", mode="before")
    @classmethod
    def clean_email(cls, v: Any) -> str:
        if not isinstance(v, str):
            raise ValueError("Email must be a string")
        cleaned = v.strip().lower()
        if CONTROL_CHAR_REGEX.search(cleaned):
            raise ValueError("Email contains invalid control characters")
        return cleaned

    @field_validator("achievement", mode="before")
    @classmethod
    def clean_achievement(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        if not isinstance(v, str):
            return str(v)
        cleaned = v.strip()
        if CONTROL_CHAR_REGEX.search(cleaned):
            raise ValueError("Achievement contains invalid control characters")
        return cleaned if cleaned else None


class JobCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    issuer_name: str = Field(..., min_length=1, max_length=255)
    issue_date: str = Field(..., min_length=1, max_length=50)
    signatory_name: str = Field(..., min_length=1, max_length=255)
    signatory_title: str = Field(..., min_length=1, max_length=255)
    recipients: List[Any] = Field(..., min_length=1)

    @field_validator("title", "issuer_name", "issue_date", "signatory_name", "signatory_title", mode="before")
    @classmethod
    def clean_strings(cls, v: Any) -> str:
        if not isinstance(v, str):
            raise ValueError("Job field must be a string")
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Job field cannot be empty")
        return cleaned


class JobAcceptedResponse(BaseModel):
    job_id: str
    status: str
    total_count: int
    accepted_count: int
    rejected_count: int
    status_url: str


class JobResponse(BaseModel):
    job_id: str
    title: str
    issuer_name: str
    issue_date: str
    signatory_name: str
    signatory_title: str
    status: str
    total_count: int
    accepted_count: int
    rejected_count: int
    success_count: int
    failed_count: int
    pending_count: int
    progress_percent: float
    status_url: str
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class JobListResponse(BaseModel):
    jobs: List[JobResponse]
    total: int
    limit: int
    offset: int
