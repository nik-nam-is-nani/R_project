import io

from pypdf import PdfReader

from app.services.pdf_generator import generate_pdf
from app.services.storage import LocalStorageProvider


def test_pdf_bytes_and_structure(temp_storage_dir: str):
    data = {
        "title": "SYSTEM ARCHITECTURE CERTIFICATE",
        "recipient_name": "Alice Cooper",
        "recipient_email": "alice@example.com",
        "achievement": "High Honors",
        "issuer_name": "Academy",
        "issue_date": "2026-10-08",
        "signatory_name": "Dr. Vance",
        "signatory_title": "Director",
        "verification_code": "CERT-TEST9999"
    }

    pdf_bytes = generate_pdf(data)
    assert pdf_bytes.startswith(b"%PDF")

    # Verify PDF content via pypdf
    reader = PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) == 1
    extracted_text = reader.pages[0].extract_text()

    assert "SYSTEM ARCHITECTURE CERTIFICATE" in extracted_text
    assert "Alice Cooper" in extracted_text
    assert "CERT-TEST9999" in extracted_text

    # Test saving via storage provider
    storage = LocalStorageProvider(base_dir=temp_storage_dir)
    saved_rel_path = storage.save_file("certificates/job1/cert1.pdf", pdf_bytes)

    assert storage.exists(saved_rel_path)
    assert storage.get_file(saved_rel_path) == pdf_bytes


def test_long_name_and_unicode_handling():
    data = {
        "title": "UNICODE AND FONT AUTO-SCALING TEST",
        "recipient_name": "José Ramón & Renée Sōseki - Extremely Super Long Recipient Full Name For Auto Scaling Font Bounds Testing",
        "recipient_email": "jose@example.com",
        "achievement": "Internationalization Support",
        "issuer_name": "Global Org",
        "issue_date": "2026-10-08",
        "signatory_name": "Signatory",
        "signatory_title": "Lead",
        "verification_code": "CERT-UNICODE123"
    }

    pdf_bytes = generate_pdf(data)
    assert pdf_bytes.startswith(b"%PDF")
    reader = PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) == 1
