from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class CertificateResponse(BaseModel):
    id: str
    job_id: str
    row_index: int
    recipient_name: str
    recipient_email: str
    achievement: Optional[str] = None
    status: str
    verification_code: str
    download_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    generated_at: Optional[datetime] = None


class CertificateListResponse(BaseModel):
    certificates: List[CertificateResponse]
    total: int
    limit: int
    offset: int


class VerificationResponse(BaseModel):
    valid: bool
    verification_code: str
    recipient_name: Optional[str] = None
    achievement: Optional[str] = None
    title: Optional[str] = None
    issuer_name: Optional[str] = None
    issue_date: Optional[str] = None
    signatory_name: Optional[str] = None
    signatory_title: Optional[str] = None
