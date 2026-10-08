from datetime import datetime, timezone

from sqlalchemy import select

from app.core.config import settings
from app.core.logging import logger
from app.db.base import SessionLocal
from app.db.models import Certificate, CertificateStatus, Job, JobStatus
from app.services.pdf_generator import generate_pdf
from app.services.storage import get_storage_provider


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def process_job(job_id: str) -> None:
    """
    Background worker function to generate certificates for a job.

    IMPORTANT ARCHITECTURAL RULE:
    Opens its OWN dedicated DB session using `SessionLocal()` to guarantee thread safety
    and prevent reusing the short-lived HTTP request session.
    """
    logger.info(f"Background worker started processing job {job_id}")

    storage = get_storage_provider()

    with SessionLocal() as db:
        job = db.scalar(select(Job).where(Job.id == job_id))
        if not job:
            logger.error(f"Worker process_job failed: Job {job_id} not found.")
            return

        if job.status not in [JobStatus.PENDING, JobStatus.PROCESSING]:
            logger.warning(f"Job {job_id} status is already {job.status}. Skipping worker execution.")
            return

        job.status = JobStatus.PROCESSING
        if not job.started_at:
            job.started_at = utc_now()
        db.commit()

        pending_certs = db.scalars(
            select(Certificate)
            .where(Certificate.job_id == job_id, Certificate.status == CertificateStatus.PENDING)
            .order_by(Certificate.row_index)
        ).all()

        logger.info(f"Job {job_id}: Processing {len(pending_certs)} PENDING certificates out of total {job.total_count}")

        for cert in pending_certs:
            try:
                cert_data = {
                    "title": job.title,
                    "recipient_name": cert.recipient_name,
                    "recipient_email": cert.recipient_email,
                    "achievement": cert.achievement or f"Completion of {job.title}",
                    "issuer_name": job.issuer_name,
                    "issue_date": job.issue_date,
                    "signatory_name": job.signatory_name,
                    "signatory_title": job.signatory_title,
                    "verification_code": cert.verification_code,
                    "base_url": settings.BASE_URL,
                }

                pdf_bytes = generate_pdf(cert_data)
                rel_path = f"certificates/{job_id}/{cert.id}.pdf"
                saved_path = storage.save_file(rel_path, pdf_bytes)

                cert.status = CertificateStatus.COMPLETED
                cert.file_path = saved_path
                cert.generated_at = utc_now()
                job.success_count += 1

            except Exception as e:
                error_trace = f"Generation Error: {str(e)}"
                logger.exception(f"Error generating PDF for certificate {cert.id} (row {cert.row_index}): {e}")

                cert.status = CertificateStatus.FAILED
                cert.error_message = error_trace
                job.failed_count += 1

            db.commit()

        db.refresh(job)

        if job.failed_count == 0 and job.success_count > 0:
            job.status = JobStatus.COMPLETED
        elif job.success_count > 0 and job.failed_count > 0:
            job.status = JobStatus.COMPLETED_WITH_ERRORS
        else:
            job.status = JobStatus.FAILED

        job.finished_at = utc_now()
        db.commit()

        logger.info(f"Job {job_id} processing completed. Final status: {job.status} (success={job.success_count}, failed={job.failed_count})")


def recover_stuck_jobs_on_startup() -> None:
    """
    Startup recovery handler.
    Identifies any jobs left in `PROCESSING` state from a server crash/restart,
    re-enqueues their pending certificates, or updates their status.
    """
    logger.info("Checking for uncompleted or stuck jobs from previous server restarts...")
    with SessionLocal() as db:
        stuck_jobs = db.scalars(
            select(Job).where(Job.status == JobStatus.PROCESSING)
        ).all()

        for job in stuck_jobs:
            logger.warning(f"Found stuck job {job.id} in PROCESSING state. Resuming background processing...")
            process_job(job.id)
