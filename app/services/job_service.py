import csv
import io
import secrets
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.db.models import Certificate, CertificateStatus, Job, JobStatus
from app.schemas.job import JobCreate, JobResponse, RecipientInput


def generate_verification_code() -> str:
    """Generate a unique short verification code for printed certificates."""
    token = secrets.token_hex(4).upper()
    return f"CERT-{token}"


def parse_csv_recipients(file_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Parse CSV file content into a list of recipient dictionary objects.
    Handles UTF-8, UTF-8 with BOM, latin-1 encodings, and column header normalization.
    """
    decoded_text = ""
    for encoding in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
        try:
            decoded_text = file_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    if not decoded_text:
        raise ValueError("Unable to decode CSV file content with supported encodings.")

    reader = csv.reader(io.StringIO(decoded_text))
    rows = [row for row in reader if any(field.strip() for field in row)]

    if not rows:
        raise ValueError("CSV file is empty.")

    header = [c.strip().lower().replace(" ", "_") for c in rows[0]]
    data_rows = rows[1:]

    name_idx = next((i for i, col in enumerate(header) if "name" in col or "recipient" in col), 0)
    email_idx = next((i for i, col in enumerate(header) if "email" in col or "mail" in col), 1)
    achievement_idx = next((i for i, col in enumerate(header) if "achievement" in col or "course" in col or "details" in col), None)

    recipients = []
    for r in data_rows:
        if not r:
            continue
        r_name = r[name_idx] if name_idx < len(r) else ""
        r_email = r[email_idx] if email_idx < len(r) else ""
        r_achieve = r[achievement_idx] if achievement_idx is not None and achievement_idx < len(r) else ""
        recipients.append({
            "name": r_name,
            "email": r_email,
            "achievement": r_achieve
        })

    return recipients


def create_job(
    db: Session,
    job_data: JobCreate,
    idempotency_key: Optional[str] = None
) -> Tuple[Job, bool]:
    """
    Create a new bulk certificate job with validated recipient rows.

    Returns (Job, is_existing_idempotent).
    """
    if idempotency_key:
        existing_job = db.scalar(select(Job).where(Job.idempotency_key == idempotency_key))
        if existing_job:
            logger.info(f"Returning idempotent existing job: {existing_job.id}")
            return existing_job, True

    total_count = len(job_data.recipients)
    if total_count == 0:
        raise ValueError("Recipients list cannot be empty.")
    if total_count > settings.MAX_RECIPIENTS:
        raise ValueError(f"Recipients count {total_count} exceeds maximum allowed limit of {settings.MAX_RECIPIENTS}.")

    job = Job(
        title=job_data.title,
        issuer_name=job_data.issuer_name,
        issue_date=job_data.issue_date,
        signatory_name=job_data.signatory_name,
        signatory_title=job_data.signatory_title,
        status=JobStatus.PENDING,
        total_count=total_count,
        success_count=0,
        failed_count=0,
        idempotency_key=idempotency_key
    )
    db.add(job)
    db.flush()

    certificates: List[Certificate] = []
    accepted_count = 0
    rejected_count = 0

    for idx, raw_rec in enumerate(job_data.recipients, start=1):
        v_code = generate_verification_code()
        rec_dict = raw_rec if isinstance(raw_rec, dict) else (raw_rec.model_dump() if hasattr(raw_rec, "model_dump") else {})

        try:
            validated_rec = RecipientInput(**rec_dict)
            cert = Certificate(
                job_id=job.id,
                row_index=idx,
                recipient_name=validated_rec.name,
                recipient_email=validated_rec.email,
                achievement=validated_rec.achievement,
                status=CertificateStatus.PENDING,
                verification_code=v_code
            )
            accepted_count += 1
        except ValidationError as ve:
            errors = [f"{err['loc'][0] if err['loc'] else 'field'}: {err['msg']}" for err in ve.errors()]
            error_msg = f"Validation Error: {'; '.join(errors)}"

            raw_name = str(rec_dict.get("name", f"Row_{idx}")).strip() or f"Row_{idx}"
            raw_email = str(rec_dict.get("email", "invalid@email")).strip() or "invalid@email"
            raw_achieve = str(rec_dict.get("achievement", "")).strip() or None

            cert = Certificate(
                job_id=job.id,
                row_index=idx,
                recipient_name=raw_name,
                recipient_email=raw_email,
                achievement=raw_achieve,
                status=CertificateStatus.FAILED,
                verification_code=v_code,
                error_message=error_msg
            )
            rejected_count += 1

        certificates.append(cert)

    db.add_all(certificates)
    job.failed_count = rejected_count

    if accepted_count == 0:
        job.status = JobStatus.FAILED

    db.commit()
    db.refresh(job)

    logger.info(f"Created Job {job.id}: total={total_count}, accepted={accepted_count}, rejected={rejected_count}")
    return job, False


def get_job_response_data(db: Session, job: Job) -> JobResponse:
    """Build detailed JobResponse schema including progress percentage and state counters."""
    counts = db.execute(
        select(
            Certificate.status,
            func.count(Certificate.id)
        ).where(Certificate.job_id == job.id).group_by(Certificate.status)
    ).all()

    status_dict = {status: count for status, count in counts}
    completed_cnt = status_dict.get(CertificateStatus.COMPLETED, 0)
    failed_cnt = status_dict.get(CertificateStatus.FAILED, 0)
    pending_cnt = status_dict.get(CertificateStatus.PENDING, 0)

    accepted_cnt = completed_cnt + pending_cnt
    processed_total = completed_cnt + failed_cnt
    percent = round((processed_total / job.total_count * 100.0), 1) if job.total_count > 0 else 0.0

    return JobResponse(
        job_id=job.id,
        title=job.title,
        issuer_name=job.issuer_name,
        issue_date=job.issue_date,
        signatory_name=job.signatory_name,
        signatory_title=job.signatory_title,
        status=job.status,
        total_count=job.total_count,
        accepted_count=accepted_cnt,
        rejected_count=failed_cnt,
        success_count=completed_cnt,
        failed_count=failed_cnt,
        pending_count=pending_cnt,
        progress_percent=min(100.0, percent),
        status_url=f"/api/jobs/{job.id}",
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at
    )
