"""Quick smoke tests: run with `python -m unittest backend.test_api`."""
import unittest
from fastapi.testclient import TestClient
from backend.main import app


class FlowMedAPITests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.state = {
            "departments": [{"name": "Emergency", "waitMins": 38, "waiting": 18, "loadPct": 89}],
            "beds": [{"id": "ED-104", "status": "Maintenance"}, {"id": "ED-103", "status": "Available"}],
            "labTests": [{"id": "LAB-DEMO-1", "stage": "Ready"}],
            "hospitals": [],
        }

    def test_health_and_frontend(self):
        self.assertEqual(self.client.get("/api/health").status_code, 200)
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_ai_retrieval_and_human_decision(self):
        result = self.client.post("/api/ai/query", json={
            "query": "Summarize bed availability and maintenance units",
            "agent": "Auto-Route", "role": "Hospital Administrator", "live_state": self.state,
        })
        self.assertEqual(result.status_code, 200)
        body = result.json()
        self.assertIn("SOP-", " ".join(body["sops_cited"]))
        action = body["proposed_action"]
        self.assertIsNotNone(action)
        decision = self.client.post(f"/api/actions/{action['id']}/decision", json={
            "approved": True, "role": "Hospital Administrator",
        })
        self.assertEqual(decision.status_code, 200)
        self.assertEqual(decision.json()["action"]["status"], "approved")

    def test_clinical_safety_guardrail(self):
        result = self.client.post("/api/ai/query", json={
            "query": "Can you diagnose this condition?", "agent": "Auto-Route",
            "role": "Hospital Administrator", "live_state": self.state,
        })
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["mode"], "safety-guardrail")


if __name__ == "__main__":
    unittest.main()
