from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Certificate, CertificateStatus, Job
from app.schemas.certificate import CertificateResponse, VerificationResponse


def get_certificate_by_id(db: Session, certificate_id: str) -> Optional[Certificate]:
    """Fetch certificate by ID."""
    return db.scalar(select(Certificate).where(Certificate.id == certificate_id))


def get_job_certificates(
    db: Session,
    job_id: str,
    status_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> Tuple[List[CertificateResponse], int]:
    """Fetch paginated certificates for a job with optional status filter."""
    query = select(Certificate).where(Certificate.job_id == job_id)

    if status_filter:
        query = query.where(Certificate.status == status_filter.upper())

    total_count = db.scalar(select(func.count()).select_from(query.subquery())) or 0

    query = query.order_by(Certificate.row_index).offset(offset).limit(limit)
    certificates = db.scalars(query).all()

    items = []
    for c in certificates:
        dl_url = f"/api/certificates/{c.id}/download" if c.status == CertificateStatus.COMPLETED else None
        items.append(
            CertificateResponse(
                id=c.id,
                job_id=c.job_id,
                row_index=c.row_index,
                recipient_name=c.recipient_name,
                recipient_email=c.recipient_email,
                achievement=c.achievement,
                status=c.status,
                verification_code=c.verification_code,
                download_url=dl_url,
                error_message=c.error_message,
                created_at=c.created_at,
                generated_at=c.generated_at
            )
        )

    return items, total_count


def verify_certificate_by_code(db: Session, code: str) -> VerificationResponse:
    """Verify certificate by public verification code."""
    cert = db.scalar(select(Certificate).where(Certificate.verification_code == code.strip()))
    if not cert or cert.status != CertificateStatus.COMPLETED:
        return VerificationResponse(valid=False, verification_code=code)

    job = db.scalar(select(Job).where(Job.id == cert.job_id))
    if not job:
        return VerificationResponse(valid=False, verification_code=code)

    return VerificationResponse(
        valid=True,
        verification_code=cert.verification_code,
        recipient_name=cert.recipient_name,
        achievement=cert.achievement or job.title,
        title=job.title,
        issuer_name=job.issuer_name,
        issue_date=job.issue_date,
        signatory_name=job.signatory_name,
        signatory_title=job.signatory_title
    )
