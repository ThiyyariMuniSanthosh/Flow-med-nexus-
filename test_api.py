from pathlib import Path
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def setup_function() -> None:
    client.post("/api/reset")


def test_health_and_frontend_accessibility_landmarks() -> None:
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "optimal"
    assert body["metrics"]["total_beds"] > 0

    html_path = Path(__file__).resolve().parent / "index.html"
    html_text = html_path.read_text(encoding="utf-8")
    assert '<html lang="en">' in html_text
    assert 'id="main-content"' in html_text
    assert 'role="progressbar"' in html_text
    assert 'aria-live="polite"' in html_text
    assert ".innerHTML" not in html_text


def test_ward_crud_and_capacity_bounds() -> None:
    # Create valid ward
    create_res = client.post(
        "/api/wards",
        json={"name": "Cardiology Step-Down", "total": 12, "free": 5, "status": "Active"},
    )
    assert create_res.status_code == 201
    ward = create_res.json()
    ward_id = ward["id"]

    # Reject invalid capacity (available > total)
    bad_res = client.post(
        "/api/wards",
        json={"name": "Invalid Ward", "total": 10, "free": 15, "status": "Active"},
    )
    assert bad_res.status_code == 422

    # Admit patient (-1 free bed)
    admit_res = client.post(f"/api/wards/{ward_id}/adjust", json={"delta": -1})
    assert admit_res.status_code == 200
    assert admit_res.json()["ward"]["free"] == 4

    # Delete ward cleanly
    del_res = client.delete(f"/api/wards/{ward_id}")
    assert del_res.status_code == 200


def test_bed_overflow_and_underflow_protection() -> None:
    create_res = client.post(
        "/api/wards",
        json={"name": "Isolation Unit", "total": 1, "free": 1, "status": "Active"},
    )
    ward_id = create_res.json()["id"]

    # Exceed max capacity via discharge when already completely empty
    overflow = client.post(f"/api/wards/{ward_id}/adjust", json={"delta": 1})
    assert overflow.status_code == 400

    # Admit 1 patient (free becomes 0), then try admitting another
    client.post(f"/api/wards/{ward_id}/adjust", json={"delta": -1})
    underflow = client.post(f"/api/wards/{ward_id}/adjust", json={"delta": -1})
    assert underflow.status_code == 400


def test_surge_simulation_and_ai_copilot_intents() -> None:
    before = client.get("/api/metrics").json()["metrics"]["available_beds"]
    surge = client.post("/api/simulate-surge")
    assert surge.status_code == 200
    after = surge.json()["metrics"]["available_beds"]
    assert after < before

    handoff = client.post("/api/copilot", json={"question": "Generate shift handoff summary"})
    assert handoff.status_code == 200
    assert handoff.json()["intent"] == "shift_handoff"

    surge_plan = client.post("/api/copilot", json={"question": "Recommend ER surge reallocation plan"})
    assert surge_plan.status_code == 200
    assert surge_plan.json()["intent"] == "er_surge_plan"


def test_input_sanitization_and_patient_search() -> None:
    xss_copilot = client.post("/api/copilot", json={"question": "<script>alert(1)</script>Check ICU load"})
    assert xss_copilot.status_code == 200
    assert "<script>" not in xss_copilot.json()["question"]

    search = client.get("/api/patients", params={"q": "Cardiology"})
    assert search.status_code == 200
    results = search.json()
    assert len(results) >= 1
    assert results[0]["department"] == "Cardiology"
