import io

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import CertificateStatus
from app.services.certificate_service import get_certificate_by_id
from app.services.storage import StorageProvider, get_storage_provider
from app.services.zip_service import sanitize_filename

router = APIRouter(prefix="/certificates", tags=["Certificates"])


@router.get("/{certificate_id}/download", summary="Download single certificate PDF")
def download_certificate(
    certificate_id: str,
    db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage_provider)
):
    """
    Stream generated certificate PDF for a specific recipient.
    Returns 404 if certificate not found, or 409 Conflict if not yet completed / failed.
    """
    cert = get_certificate_by_id(db, certificate_id)
    if not cert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": f"Certificate {certificate_id} not found."}}
        )

    if cert.status != CertificateStatus.COMPLETED or not cert.file_path:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "CERTIFICATE_NOT_READY",
                    "message": f"Certificate is currently in state '{cert.status}' with error: '{cert.error_message or 'processing'}'."
                }
            }
        )

    if not storage.exists(cert.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "FILE_MISSING", "message": "Certificate PDF file is missing from storage."}}
        )

    pdf_bytes = storage.get_file(cert.file_path)
    safe_name = sanitize_filename(cert.recipient_name)
    filename = f"{cert.row_index:03d}_{safe_name}.pdf"

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )
