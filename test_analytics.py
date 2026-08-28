"""Tests for /api/analytics — verifies real DB-derived computation, not hardcoded values."""


def test_analytics_empty_db_returns_zeroes(client):
    resp = client.get("/api/analytics")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_cases"] == 0
    assert body["ai_agreement_rate"] == 0.0


def test_analytics_reflects_seeded_dataset(seeded_client):
    resp = seeded_client.get("/api/analytics")
    body = resp.json()
    assert body["total_cases"] == 30
    assert sum(body["issue_type_distribution"].values()) == 30
    assert sum(body["severity_distribution"].values()) == 30


def test_analytics_agreement_rate_after_reviews(seeded_client):
    # Create and approve one diagnosis, create and reject another.
    d1 = seeded_client.post("/api/diagnose/NET-001", json={"force_ai": False}).json()
    d2 = seeded_client.post("/api/diagnose/NET-002", json={"force_ai": False}).json()

    seeded_client.post(f"/api/reviews/{d1['id']}/approve", json={})
    seeded_client.post(f"/api/reviews/{d2['id']}/reject", json={"rejection_reason": "wrong"})

    resp = seeded_client.get("/api/analytics")
    body = resp.json()
    assert body["accepted"] == 1
    assert body["rejected"] == 1
    assert body["ai_agreement_rate"] == 50.0
