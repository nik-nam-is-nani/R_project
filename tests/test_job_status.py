from fastapi.testclient import TestClient


def test_job_status_and_pagination(client: TestClient):
    payload = {
        "title": "Pagination and Status Test",
        "issuer_name": "Issuer",
        "issue_date": "2026-10-08",
        "signatory_name": "Signatory",
        "signatory_title": "Title",
        "recipients": [
            {"name": "User One", "email": "one@example.com"},
            {"name": "User Two", "email": "two@example.com"},
            {"name": "User Three", "email": "invalid-email"}
        ]
    }

    res = client.post("/api/jobs", json=payload)
    job_id = res.json()["job_id"]

    # Post-run status check
    status2 = client.get(f"/api/jobs/{job_id}").json()
    assert status2["status"] == "COMPLETED_WITH_ERRORS"
    assert status2["success_count"] == 2
    assert status2["failed_count"] == 1
    assert status2["pending_count"] == 0
    assert status2["progress_percent"] == 100.0

    # Test certificate pagination with status filter
    completed_certs = client.get(f"/api/jobs/{job_id}/certificates?status=COMPLETED").json()
    assert len(completed_certs["certificates"]) == 2

    failed_certs = client.get(f"/api/jobs/{job_id}/certificates?status=FAILED").json()
    assert len(failed_certs["certificates"]) == 1
    assert failed_certs["certificates"][0]["recipient_name"] == "User Three"
