from typing import Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import Certificate, CertificateStatus, Job, JobStatus
from app.schemas.certificate import CertificateListResponse
from app.schemas.job import JobAcceptedResponse, JobCreate, JobListResponse, JobResponse
from app.services.certificate_service import get_job_certificates
from app.services.job_service import create_job, get_job_response_data, parse_csv_recipients
from app.services.storage import StorageProvider, get_storage_provider
from app.services.zip_service import create_job_zip_archive, sanitize_filename
from app.workers.processor import process_job

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.post("", response_model=JobAcceptedResponse, status_code=status.HTTP_202_ACCEPTED, summary="Create bulk certificate job (JSON)")
def create_bulk_job(
    job_data: JobCreate,
    background_tasks: BackgroundTasks,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: Session = Depends(get_db)
):
    """
    Create a bulk certificate generation job from JSON payload.
    Supports optional `Idempotency-Key` header to prevent duplicate job execution.
    Validates job-level data strictly, records invalid recipient rows as FAILED, and queues valid rows for background rendering.
    """
    try:
        job, is_existing = create_job(db, job_data, idempotency_key=idempotency_key)
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(ve)}}
        )

    # Calculate counters
    accepted_cnt = db.scalar(
        select(func.count(Certificate.id))
        .where(Certificate.job_id == job.id, Certificate.status != CertificateStatus.FAILED)
    ) or 0
    rejected_cnt = job.total_count - accepted_cnt

    # If it's a new job and has accepted rows pending, enqueue background worker
    if not is_existing and job.status == JobStatus.PENDING:
        background_tasks.add_task(process_job, job.id)

    return JobAcceptedResponse(
        job_id=job.id,
        status=job.status,
        total_count=job.total_count,
        accepted_count=accepted_cnt,
        rejected_count=rejected_cnt,
        status_url=f"/api/jobs/{job.id}"
    )


@router.post("/upload", response_model=JobAcceptedResponse, status_code=status.HTTP_202_ACCEPTED, summary="Create bulk certificate job (CSV Upload)")
def upload_csv_job(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    issuer_name: str = Form(...),
    issue_date: str = Form(...),
    signatory_name: str = Form(...),
    signatory_title: str = Form(...),
    file: UploadFile = File(...),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: Session = Depends(get_db)
):
    """
    Create a bulk certificate job via multipart CSV file upload + form parameters.
    Supports optional `Idempotency-Key` header.
    """
    if not file.filename.lower().endswith((".csv", ".txt")):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_FILE_TYPE", "message": "Uploaded file must be a CSV file."}}
        )

    try:
        content = file.file.read()
        recipients_list = parse_csv_recipients(content)

        job_data = JobCreate(
            title=title,
            issuer_name=issuer_name,
            issue_date=issue_date,
            signatory_name=signatory_name,
            signatory_title=signatory_title,
            recipients=recipients_list
        )

        job, is_existing = create_job(db, job_data, idempotency_key=idempotency_key)
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "CSV_PROCESSING_ERROR", "message": str(ve)}}
        )

    accepted_cnt = db.scalar(
        select(func.count(Certificate.id))
        .where(Certificate.job_id == job.id, Certificate.status != CertificateStatus.FAILED)
    ) or 0
    rejected_cnt = job.total_count - accepted_cnt

    if not is_existing and job.status == JobStatus.PENDING:
        background_tasks.add_task(process_job, job.id)

    return JobAcceptedResponse(
        job_id=job.id,
        status=job.status,
        total_count=job.total_count,
        accepted_count=accepted_cnt,
        rejected_count=rejected_cnt,
        status_url=f"/api/jobs/{job.id}"
    )


@router.get("", response_model=JobListResponse, summary="List paginated jobs")
def list_jobs(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Retrieve paginated list of jobs sorted newest first."""
    total = db.scalar(select(func.count(Job.id))) or 0
    jobs = db.scalars(
        select(Job).order_by(Job.created_at.desc()).offset(offset).limit(limit)
    ).all()

    items = [get_job_response_data(db, j) for j in jobs]
    return JobListResponse(jobs=items, total=total, limit=limit, offset=offset)


@router.get("/{job_id}", response_model=JobResponse, summary="Get job progress & details")
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """Fetch job metadata, current status, live progress percentage, and recipient counters."""
    job = db.scalar(select(Job).where(Job.id == job_id))
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "JOB_NOT_FOUND", "message": f"Job {job_id} not found."}}
        )

    return get_job_response_data(db, job)


@router.get("/{job_id}/certificates", response_model=CertificateListResponse, summary="List job certificates")
def list_job_certificates(
    job_id: str,
    status: Optional[str] = Query(None, description="Filter by COMPLETED, FAILED, or PENDING"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Retrieve paginated certificates for a specific job with optional status filtering."""
    job = db.scalar(select(Job).where(Job.id == job_id))
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "JOB_NOT_FOUND", "message": f"Job {job_id} not found."}}
        )

    items, total = get_job_certificates(db, job_id, status_filter=status, limit=limit, offset=offset)
    return CertificateListResponse(certificates=items, total=total, limit=limit, offset=offset)


@router.get("/{job_id}/download", summary="Download ZIP of all completed job certificates")
def download_job_zip(
    job_id: str,
    db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage_provider)
):
    """
    Stream a ZIP archive containing all completed PDF certificates in the job.
    Filenames are sanitized and deduplicated.
    Returns 409 Conflict if no certificates are ready.
    """
    job = db.scalar(select(Job).where(Job.id == job_id))
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "JOB_NOT_FOUND", "message": f"Job {job_id} not found."}}
        )

    certificates = db.scalars(
        select(Certificate).where(
            Certificate.job_id == job_id,
            Certificate.status == CertificateStatus.COMPLETED
        ).order_by(Certificate.row_index)
    ).all()

    if not certificates:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "NO_CERTIFICATES_READY",
                    "message": f"Job {job_id} has no completed certificates ready for download."
                }
            }
        )

    zip_buffer = create_job_zip_archive(certificates, storage)
    zip_filename = f"job_{sanitize_filename(job.title)}_{job.id[:8]}.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_filename}"'
        }
    )
