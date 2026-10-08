from unittest.mock import patch

from fastapi.testclient import TestClient

import app.workers.processor as processor_module


def test_failure_isolation_on_generator_exception(client: TestClient):
    payload = {
        "title": "Failure Isolation Mock Test",
        "issuer_name": "Issuer",
        "issue_date": "2026-10-08",
        "signatory_name": "Signatory",
        "signatory_title": "Title",
        "recipients": [
            {"name": "Recipient 1", "email": "r1@example.com"},
            {"name": "Recipient 2 (Will Fail)", "email": "r2@example.com"},
            {"name": "Recipient 3", "email": "r3@example.com"}
        ]
    }

    original_generate_pdf = processor_module.generate_pdf

    def mock_generate_pdf(data):
        if "Recipient 2" in data.get("recipient_name", ""):
            raise RuntimeError("Simulated ReportLab Engine Failure on Recipient 2")
        return original_generate_pdf(data)

    with patch("app.workers.processor.generate_pdf", side_effect=mock_generate_pdf):
        res = client.post("/api/jobs", json=payload)

    job_id = res.json()["job_id"]

    status_data = client.get(f"/api/jobs/{job_id}").json()
    assert status_data["status"] == "COMPLETED_WITH_ERRORS"
    assert status_data["success_count"] == 2
    assert status_data["failed_count"] == 1

    certs_data = client.get(f"/api/jobs/{job_id}/certificates").json()["certificates"]
    c1, c2, c3 = certs_data[0], certs_data[1], certs_data[2]

    assert c1["status"] == "COMPLETED"
    assert c2["status"] == "FAILED"
    assert "Simulated ReportLab Engine Failure" in c2["error_message"]
    assert c3["status"] == "COMPLETED"
