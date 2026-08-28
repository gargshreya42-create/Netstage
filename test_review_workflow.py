"""
Tests for the human-in-the-loop review workflow: approve/edit/reject,
the double-review guard, and that every action is captured in the audit
log. This is the safety-critical core of the platform.
"""
import pytest


def _create_diagnosis(client, case_id="NET-001"):
    resp = client.post(f"/api/diagnose/{case_id}", json={"force_ai": False})
    assert resp.status_code == 200
    return resp.json()


def test_approve_diagnosis(seeded_client):
    diagnosis = _create_diagnosis(seeded_client)
    resp = seeded_client.post(f"/api/reviews/{diagnosis['id']}/approve", json={"reviewer_comment": "Looks right"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] == "ACCEPTED"

    # Diagnosis status should now reflect the review
    diag_resp = seeded_client.get(f"/api/diagnoses/{diagnosis['id']}")
    assert diag_resp.json()["status"] == "ACCEPTED"


def test_edit_diagnosis_requires_commands(seeded_client):
    diagnosis = _create_diagnosis(seeded_client)
    resp = seeded_client.post(f"/api/reviews/{diagnosis['id']}/edit", json={"edited_commands": []})
    assert resp.status_code == 400


def test_edit_diagnosis_success(seeded_client):
    diagnosis = _create_diagnosis(seeded_client)
    resp = seeded_client.post(
        f"/api/reviews/{diagnosis['id']}/edit",
        json={"edited_commands": ["interface Gi0/0.30", "no shutdown"], "reviewer_comment": "Adjusted"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] == "EDITED"
    assert body["edited_commands"] == ["interface Gi0/0.30", "no shutdown"]
    assert body["original_commands"] is not None


def test_reject_diagnosis_requires_reason(seeded_client):
    diagnosis = _create_diagnosis(seeded_client)
    resp = seeded_client.post(f"/api/reviews/{diagnosis['id']}/reject", json={"rejection_reason": ""})
    assert resp.status_code == 400


def test_reject_diagnosis_success(seeded_client):
    diagnosis = _create_diagnosis(seeded_client)
    resp = seeded_client.post(
        f"/api/reviews/{diagnosis['id']}/reject",
        json={"rejection_reason": "AI misread the evidence", "reviewer_comment": "See ACL instead"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] == "REJECTED"
    assert body["rejection_reason"] == "AI misread the evidence"


def test_cannot_review_same_diagnosis_twice(seeded_client):
    diagnosis = _create_diagnosis(seeded_client)
    first = seeded_client.post(f"/api/reviews/{diagnosis['id']}/approve", json={})
    assert first.status_code == 200

    second = seeded_client.post(f"/api/reviews/{diagnosis['id']}/approve", json={})
    assert second.status_code == 400


def test_review_nonexistent_diagnosis_fails_cleanly(seeded_client):
    resp = seeded_client.post("/api/reviews/999999/approve", json={})
    assert resp.status_code == 400


def test_review_queue_only_shows_pending(seeded_client):
    d1 = _create_diagnosis(seeded_client, "NET-001")
    d2 = _create_diagnosis(seeded_client, "NET-002")
    seeded_client.post(f"/api/reviews/{d1['id']}/approve", json={})

    queue = seeded_client.get("/api/reviews/queue").json()
    queue_ids = [d["id"] for d in queue]
    assert d1["id"] not in queue_ids
    assert d2["id"] in queue_ids


def test_verification_unavailable_before_review(seeded_client):
    diagnosis = _create_diagnosis(seeded_client)
    resp = seeded_client.get(f"/api/reviews/{diagnosis['id']}/verify")
    assert resp.status_code == 400


def test_verification_available_after_approval(seeded_client):
    diagnosis = _create_diagnosis(seeded_client)
    seeded_client.post(f"/api/reviews/{diagnosis['id']}/approve", json={})
    resp = seeded_client.get(f"/api/reviews/{diagnosis['id']}/verify")
    assert resp.status_code == 200
    body = resp.json()
    assert body["simulated"] is True
    assert "not" in body["note"].lower() or "never" in body["note"].lower()


def test_full_workflow_produces_audit_trail(seeded_client):
    """End-to-end: rule check -> diagnose -> approve -> verify, all logged."""
    seeded_client.post("/api/rules/check/NET-001")
    diagnosis = _create_diagnosis(seeded_client)
    seeded_client.post(f"/api/reviews/{diagnosis['id']}/approve", json={"reviewer_comment": "confirmed"})
    seeded_client.get(f"/api/reviews/{diagnosis['id']}/verify")

    audit_resp = seeded_client.get("/api/audit", params={"case_id": "NET-001"})
    assert audit_resp.status_code == 200
    events = [e["event_type"] for e in audit_resp.json()]

    assert "RULE_CHECK_RUN" in events
    assert "RULES_ONLY_DIAGNOSIS_CREATED" in events
    assert "REVIEW_APPROVED" in events
    assert "VERIFICATION_RUN" in events
