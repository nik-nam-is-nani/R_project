import io
import zipfile

from fastapi.testclient import TestClient

from app.workers.processor import process_job


def test_download_single_pdf_and_verification(client: TestClient):
    payload = {
        "title": "Retrieval Test Job",
        "issuer_name": "Issuer Org",
        "issue_date": "2026-10-08",
        "signatory_name": "Signatory Name",
        "signatory_title": "Signatory Title",
        "recipients": [
            {"name": "Download Recipient", "email": "download@example.com", "achievement": "Distinction"}
        ]
    }

    res = client.post("/api/jobs", json=payload)
    job_id = res.json()["job_id"]
    process_job(job_id)

    certs = client.get(f"/api/jobs/{job_id}/certificates").json()["certificates"]
    cert = certs[0]

    # 1. Verify single PDF download
    dl_res = client.get(f"/api/certificates/{cert['id']}/download")
    assert dl_res.status_code == 200
    assert dl_res.headers["content-type"] == "application/pdf"
    assert dl_res.content.startswith(b"%PDF")

    # 2. Verify certificate endpoint
    v_res = client.get(f"/api/verify/{cert['verification_code']}")
    assert v_res.status_code == 200
    v_data = v_res.json()
    assert v_data["valid"] is True
    assert v_data["recipient_name"] == "Download Recipient"
    assert v_data["issuer_name"] == "Issuer Org"

    # 3. Test verification for non-existent code
    v_bad = client.get("/api/verify/INVALID-CODE-999")
    assert v_bad.json()["valid"] is False


def test_zip_archive_download(client: TestClient):
    payload = {
        "title": "ZIP Archive Download Test",
        "issuer_name": "Issuer Org",
        "issue_date": "2026-10-08",
        "signatory_name": "Signatory Name",
        "signatory_title": "Signatory Title",
        "recipients": [
            {"name": "Alice Smith", "email": "alice@example.com"},
            {"name": "Bob Jones", "email": "bob@example.com"}
        ]
    }

    res = client.post("/api/jobs", json=payload)
    job_id = res.json()["job_id"]
    process_job(job_id)

    zip_res = client.get(f"/api/jobs/{job_id}/download")
    assert zip_res.status_code == 200
    assert zip_res.headers["content-type"] == "application/zip"

    # Inspect zip contents
    zf = zipfile.ZipFile(io.BytesIO(zip_res.content))
    file_list = zf.namelist()

    assert len(file_list) == 2
    assert "001_Alice_Smith.pdf" in file_list[0]
    assert "002_Bob_Jones.pdf" in file_list[1]


def test_404_and_409_error_responses(client: TestClient):
    # 404 for unknown job
    res404 = client.get("/api/jobs/00000000-0000-0000-0000-000000000000")
    assert res404.status_code == 404

    # Create job with invalid recipient (will fail)
    payload = {
        "title": "Conflict Test Job",
        "issuer_name": "Issuer",
        "issue_date": "2026-10-08",
        "signatory_name": "Signatory",
        "signatory_title": "Title",
        "recipients": [{"name": "Bad Recipient", "email": "not-an-email"}]
    }

    create_res = client.post("/api/jobs", json=payload)
    job_id = create_res.json()["job_id"]
    process_job(job_id)

    cert_id = client.get(f"/api/jobs/{job_id}/certificates").json()["certificates"][0]["id"]

    # Download failed certificate should return 409 Conflict
    dl_fail = client.get(f"/api/certificates/{cert_id}/download")
    assert dl_fail.status_code == 409
