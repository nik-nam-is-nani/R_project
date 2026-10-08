from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.workers.processor import process_job


def test_create_bulk_job_success(client: TestClient, db_session: Session):
    payload = {
        "title": "Python Microservices Certification",
        "issuer_name": "Tech Corp",
        "issue_date": "2026-10-08",
        "signatory_name": "Jane Doe",
        "signatory_title": "CTO",
        "recipients": [
            {"name": "Alice Smith", "email": "alice@example.com", "achievement": "Top Performer"},
            {"name": "Bob Jones", "email": "bob@example.com", "achievement": "Systems Master"}
        ]
    }

    response = client.post("/api/jobs", json=payload)
    assert response.status_code == 202
    data = response.json()

    assert "job_id" in data
    assert data["status"] == "PENDING"
    assert data["total_count"] == 2
    assert data["accepted_count"] == 2
    assert data["rejected_count"] == 0

    # Process job synchronously in tests
    process_job(data["job_id"])

    # Verify status transition
    status_resp = client.get(f"/api/jobs/{data['job_id']}")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["status"] == "COMPLETED"
    assert status_data["success_count"] == 2
    assert status_data["failed_count"] == 0


def test_idempotency_key_behavior(client: TestClient):
    payload = {
        "title": "Idempotency Test Job",
        "issuer_name": "Acme Inc",
        "issue_date": "2026-10-08",
        "signatory_name": "Boss",
        "signatory_title": "CEO",
        "recipients": [
            {"name": "Charlie", "email": "charlie@example.com"}
        ]
    }
    headers = {"Idempotency-Key": "UNIQUE-KEY-12345"}

    res1 = client.post("/api/jobs", json=payload, headers=headers)
    assert res1.status_code == 202
    data1 = res1.json()

    # Second request with same Idempotency-Key
    res2 = client.post("/api/jobs", json=payload, headers=headers)
    assert res2.status_code == 202
    data2 = res2.json()

    assert data1["job_id"] == data2["job_id"]
    assert data1["total_count"] == data2["total_count"]
