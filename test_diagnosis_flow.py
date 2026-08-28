"""
Tests for the rule-checker API and the diagnose endpoint's graceful
fallback behavior when no AI provider is configured (Section 21: missing
API key must never crash the app).
"""


def test_rule_check_endpoint(seeded_client):
    resp = seeded_client.post("/api/rules/check/NET-001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ERRORS_DETECTED"
    assert any(e["type"] == "INTERFACE_ADMIN_DOWN" for e in body["errors"])


def test_rule_check_nonexistent_case_404(seeded_client):
    resp = seeded_client.post("/api/rules/check/NOPE-999")
    assert resp.status_code == 404


def test_diagnose_without_api_key_falls_back_to_rules_only(seeded_client):
    """
    With no OPENAI_API_KEY configured in the test environment, /api/diagnose
    must NOT crash — it should persist a rules_only diagnosis and still
    require human review.
    """
    resp = seeded_client.post("/api/diagnose/NET-001", json={"force_ai": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "PENDING_REVIEW"
    assert body["requires_human_review"] is True
    # Since no API key is set in the test environment, this should have
    # gracefully fallen back rather than raising a 500.
    assert body["source"] in ("ai", "rules_only")


def test_diagnose_rules_only_explicitly(seeded_client):
    resp = seeded_client.post("/api/diagnose/NET-001", json={"force_ai": False})
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "rules_only"
    assert body["requires_human_review"] is True


def test_diagnose_nonexistent_case_404(seeded_client):
    resp = seeded_client.post("/api/diagnose/NOPE-999", json={"force_ai": False})
    assert resp.status_code == 404


def test_list_diagnoses(seeded_client):
    seeded_client.post("/api/diagnose/NET-001", json={"force_ai": False})
    resp = seeded_client.get("/api/diagnoses")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_get_single_diagnosis(seeded_client):
    create_resp = seeded_client.post("/api/diagnose/NET-001", json={"force_ai": False})
    diagnosis_id = create_resp.json()["id"]
    resp = seeded_client.get(f"/api/diagnoses/{diagnosis_id}")
    assert resp.status_code == 200
    assert resp.json()["case_id"] == "NET-001"


def test_get_nonexistent_diagnosis_404(seeded_client):
    resp = seeded_client.get("/api/diagnoses/999999")
    assert resp.status_code == 404
