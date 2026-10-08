import io
import re
import zipfile
from typing import List

from app.db.models import Certificate, CertificateStatus
from app.services.storage import StorageProvider


def sanitize_filename(name: str) -> str:
    """Sanitize string to be safe for filenames inside ZIP archives."""
    # Replace non-alphanumeric chars (excluding dots/dashes/underscores) with underscores
    clean = re.sub(r"[^\w\-. ]", "_", name.strip())
    clean = re.sub(r"\s+", "_", clean)
    clean = re.sub(r"_+", "_", clean)
    return clean.strip("_") or "certificate"


def create_job_zip_archive(certificates: List[Certificate], storage: StorageProvider) -> io.BytesIO:
    """
    Build an in-memory ZIP archive containing generated PDFs for completed certificates.
    Filenames are formatted with row_index prefix and sanitized names (e.g., 001_Jane_Doe.pdf).
    """
    zip_buffer = io.BytesIO()
    used_filenames = set()

    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for cert in certificates:
            if cert.status != CertificateStatus.COMPLETED or not cert.file_path:
                continue

            if not storage.exists(cert.file_path):
                continue

            pdf_bytes = storage.get_file(cert.file_path)

            safe_name = sanitize_filename(cert.recipient_name)
            base_filename = f"{cert.row_index:03d}_{safe_name}.pdf"
            filename = base_filename
            counter = 1

            while filename in used_filenames:
                filename = f"{cert.row_index:03d}_{safe_name}_{counter}.pdf"
                counter += 1

            used_filenames.add(filename)
            zf.writestr(filename, pdf_bytes)

    zip_buffer.seek(0)
    return zip_buffer
