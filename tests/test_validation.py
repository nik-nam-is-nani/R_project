import io

from fastapi.testclient import TestClient

from app.workers.processor import process_job


def test_invalid_job_level_fields(client: TestClient):
    payload = {
        "title": "",  # Empty title
        "issuer_name": "Tech Corp",
        "issue_date": "2026-10-08",
        "signatory_name": "Jane",
        "signatory_title": "CTO",
        "recipients": [{"name": "Valid", "email": "valid@example.com"}]
    }
    res = client.post("/api/jobs", json=payload)
    assert res.status_code == 422


def test_empty_recipients_list(client: TestClient):
    payload = {
        "title": "Valid Title",
        "issuer_name": "Tech Corp",
        "issue_date": "2026-10-08",
        "signatory_name": "Jane",
        "signatory_title": "CTO",
        "recipients": []
    }
    res = client.post("/api/jobs", json=payload)
    assert res.status_code == 422


def test_per_recipient_validation_isolation(client: TestClient):
    payload = {
        "title": "Validation Isolation Test",
        "issuer_name": "Tech Corp",
        "issue_date": "2026-10-08",
        "signatory_name": "Jane",
        "signatory_title": "CTO",
        "recipients": [
            {"name": "Good Recipient", "email": "good@example.com"},
            {"name": "Bad Email Recipient", "email": "invalid-email-string"},
            {"name": "   ", "email": "emptyname@example.com"}
        ]
    }

    res = client.post("/api/jobs", json=payload)
    assert res.status_code == 202
    data = res.json()

    assert data["total_count"] == 3
    assert data["accepted_count"] == 1
    assert data["rejected_count"] == 2

    job_id = data["job_id"]
    process_job(job_id)

    certs_res = client.get(f"/api/jobs/{job_id}/certificates")
    assert certs_res.status_code == 200
    certs_data = certs_res.json()["certificates"]

    assert len(certs_data) == 3
    statuses = [c["status"] for c in certs_data]
    assert statuses == ["COMPLETED", "FAILED", "FAILED"]
    assert "email" in certs_data[1]["error_message"].lower()


def test_csv_upload_with_bom_and_bad_rows(client: TestClient):
    # CSV content encoded with UTF-8 BOM containing valid and invalid rows
    csv_content = "\ufeffName,Email,Achievement\nGood User,good.user@example.com,Backend\nBad User,not-an-email,Frontend\n".encode("utf-8-sig")

    files = {"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
    data = {
        "title": "CSV Upload Job",
        "issuer_name": "Issuer",
        "issue_date": "2026-10-08",
        "signatory_name": "Signatory",
        "signatory_title": "Manager"
    }

    res = client.post("/api/jobs/upload", data=data, files=files)
    assert res.status_code == 202
    res_data = res.json()

    assert res_data["total_count"] == 2
    assert res_data["accepted_count"] == 1
    assert res_data["rejected_count"] == 1
