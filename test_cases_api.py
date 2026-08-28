"""Tests for /api/cases — dataset seeding, CRUD, search/filter, invalid data."""


def test_health_check(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_dataset_seeds_30_cases(seeded_client):
    resp = seeded_client.get("/api/cases")
    assert resp.status_code == 200
    assert len(resp.json()) == 30


def test_get_single_case(seeded_client):
    resp = seeded_client.get("/api/cases/NET-001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["case_id"] == "NET-001"
    assert body["concept_tag"] == "VLAN"


def test_get_nonexistent_case_returns_404(seeded_client):
    resp = seeded_client.get("/api/cases/NET-999")
    assert resp.status_code == 404


def test_search_cases_by_concept_tag(seeded_client):
    resp = seeded_client.get("/api/cases", params={"concept_tag": "DHCP"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) > 0
    assert all(c["concept_tag"] == "DHCP" for c in body)


def test_search_cases_by_text(seeded_client):
    resp = seeded_client.get("/api/cases", params={"search": "VLAN 30"})
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_create_custom_case_success(seeded_client):
    payload = {
        "symptom": "Test symptom for custom case",
        "topology_note": "Test topology",
        "show_outputs": "R1# show ip interface brief\nSome output here",
        "concept_tag": "VLAN",
        "severity": "Medium",
    }
    resp = seeded_client.post("/api/cases", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["case_id"].startswith("CUST-")


def test_create_case_with_blank_symptom_rejected(seeded_client):
    """Section 21: invalid case data must be rejected cleanly, not crash the app."""
    payload = {
        "symptom": "   ",
        "show_outputs": "some output",
        "concept_tag": "VLAN",
        "severity": "Medium",
    }
    resp = seeded_client.post("/api/cases", json=payload)
    assert resp.status_code == 422


def test_create_case_with_invalid_severity_rejected(seeded_client):
    payload = {
        "symptom": "Valid symptom",
        "show_outputs": "some output",
        "concept_tag": "VLAN",
        "severity": "Apocalyptic",
    }
    resp = seeded_client.post("/api/cases", json=payload)
    assert resp.status_code == 422


def test_create_case_with_invalid_concept_tag_rejected(seeded_client):
    payload = {
        "symptom": "Valid symptom",
        "show_outputs": "some output",
        "concept_tag": "Not A Real Tag",
        "severity": "Medium",
    }
    resp = seeded_client.post("/api/cases", json=payload)
    assert resp.status_code == 422


def test_create_case_missing_required_field_rejected(seeded_client):
    payload = {"symptom": "Missing show_outputs entirely", "concept_tag": "VLAN"}
    resp = seeded_client.post("/api/cases", json=payload)
    assert resp.status_code == 422
