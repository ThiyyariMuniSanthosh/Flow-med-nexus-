"""FlowMed Nexus 2.0 API — synthetic hospital-operations demo.

Gemini is used only for operational explanations grounded in supplied state and SOPs.
No clinical diagnosis/treatment, real patient data, or automatic consequential actions.
Approval records are in-memory for this demo; use PostgreSQL before production.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
DATA_PATH = ROOT / "database" / "sample_dataset.json"
with DATA_PATH.open("r", encoding="utf-8") as f:
    SEED_DATA = json.load(f)

try:
    from google import genai
except ImportError:  # Gemini is optional; rules-based demo still runs.
    genai = None

# Optional Firebase Admin connection. The service-account JSON belongs in the
# hosting provider's Secrets/Environment Variables, never in frontend code.
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
except ImportError:
    firebase_admin = None
    credentials = firestore = None

FIRESTORE_DB = None
FIREBASE_ERROR = None
raw_firebase_credentials = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
if raw_firebase_credentials and firebase_admin is not None:
    try:
        service_account_info = json.loads(raw_firebase_credentials)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(credentials.Certificate(service_account_info))
        FIRESTORE_DB = firestore.client()
    except Exception as exc:
        FIREBASE_ERROR = type(exc).__name__

def firestore_docs(collection_name: str) -> list[dict]:
    if FIRESTORE_DB is None:
        return []
    docs = FIRESTORE_DB.collection(collection_name).stream()
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]

def seed_firestore_if_empty() -> dict:
    """Create top-level demo collections only when enabled and currently empty."""
    if FIRESTORE_DB is None:
        return {"seeded": False, "reason": "Firebase is not connected"}
    if os.getenv("FIREBASE_SEED_ON_START", "false").lower() != "true":
        return {"seeded": False, "reason": "Set FIREBASE_SEED_ON_START=true to seed synthetic demo data"}
    samples = {
        "hospitals": SEED_DATA["hospitals"],
        "beds": [
            {"bed_id":"ED-103","hospital_id":"HOSP-01","department":"Emergency","ward":"Observation","floor":1,"status":"Available"},
            {"bed_id":"ED-104","hospital_id":"HOSP-01","department":"Emergency","ward":"Observation","floor":1,"status":"Maintenance"},
            {"bed_id":"ICU-203","hospital_id":"HOSP-01","department":"ICU","ward":"Critical Care B","floor":2,"status":"Available"},
            {"bed_id":"CAR-302","hospital_id":"HOSP-01","department":"Cardiology","ward":"Telemetry","floor":3,"status":"Occupied"}
        ],
        "lab_tests": [
            {"test_id":"LAB-8822","patient_alias":"PT-SYN-409","department":"Cardiology","test_name":"Lipid & BNP Profile","priority":"Urgent","status":"Ready"},
            {"test_id":"LAB-8823","patient_alias":"PT-SYN-415","department":"General Medicine","test_name":"Complete Blood Count","priority":"Routine","status":"Processing"}
        ],
        "resource_requests": [
            {"request_id":"REQ-301","source_hospital_id":"HOSP-01","target_hospital_id":"HOSP-02","resource_type":"ICU Overflow Beds","quantity":3,"urgency":"High","status":"Pending Approval"}
        ],
        "sop_documents": SEED_DATA["sop_documents"],
        "audit_logs": [
            {"log_id":"LOG-SEED-001","timestamp":now_iso(),"actor_role":"System","action_type":"Demo data initialized","target_entity":"FlowMed demo network","details":"Synthetic demonstration records created","human_approved":False}
        ]
    }
    created = {}
    for collection_name, records in samples.items():
        collection = FIRESTORE_DB.collection(collection_name)
        count = 0
        for record in records:
            key = (record.get("id") or record.get("bed_id") or record.get("test_id") or
                   record.get("request_id") or record.get("sop_id") or record.get("log_id"))
            if key and collection.document(str(key)).get().exists is False:
                collection.document(str(key)).set(record)
                count += 1
        created[collection_name] = count
    return {"seeded": True, "created_documents": created, "synthetic_data": True}

Role = Literal["Hospital Administrator", "Department Coordinator", "Network Coordinator"]
AGENTS = {
    "Patient Flow Analyst Agent", "Bed Availability Analyst Agent",
    "Laboratory Coordination Agent", "Resource Coordination Agent",
    "Operations Reporting Agent",
}
CLINICAL_TERMS = re.compile(r"\b(diagnos\w*|prescrib\w*|treat\w*|medicat\w*|dosage|therapy|clinical advice)\b", re.I)

app = FastAPI(
    title="FlowMed Nexus 2.0 API",
    description="Synthetic hospital capacity and coordination demo API",
    version="2.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

AUDIT_LOG: list[dict] = []
PENDING_ACTIONS: dict[str, dict] = {}

class AIQueryRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1200)
    agent: str = "Auto-Route"
    role: Role = "Hospital Administrator"
    live_state: dict = Field(default_factory=dict)

class DecisionRequest(BaseModel):
    approved: bool
    role: Role


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def audit(role: str, action: str, target: str, details: str, approved: bool) -> None:
    entry = {
        "timestamp": now_iso(), "actor_role": role, "action_type": action,
        "target_entity": target, "details": details, "human_approved": approved,
        "demo_only": True,
    }
    AUDIT_LOG.insert(0, entry)
    del AUDIT_LOG[100:]
    if FIRESTORE_DB is not None:
        try:
            FIRESTORE_DB.collection("audit_logs").add(entry)
        except Exception:
            pass  # Keep the demo usable; /api/firebase/status reports connection state.


def retrieve_sops(query: str) -> list[dict]:
    """Small transparent lexical retriever over the supplied SOP knowledge base."""
    words = {w for w in re.findall(r"[a-z0-9-]+", query.lower()) if len(w) > 2}
    scored = []
    for sop in SEED_DATA["sop_documents"]:
        text = f"{sop['title']} {sop['category']} {sop['content']}".lower()
        score = sum(1 for word in words if word in text)
        if score:
            scored.append((score, sop))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in scored[:2]] or SEED_DATA["sop_documents"][:1]


def choose_agent(query: str, selected: str) -> str:
    if selected in AGENTS:
        return selected
    q = query.lower()
    if any(w in q for w in ("bed", "icu", "maintenance", "occupancy")):
        return "Bed Availability Analyst Agent"
    if any(w in q for w in ("lab", "test", "report", "specimen", "notification")):
        return "Laboratory Coordination Agent"
    if any(w in q for w in ("network", "hospital", "transfer", "ventilator", "resource")):
        return "Resource Coordination Agent"
    if any(w in q for w in ("bottleneck", "surge", "wait", "arrival", "flow")):
        return "Patient Flow Analyst Agent"
    return "Operations Reporting Agent"


def make_grounded_summary(agent: str, state: dict) -> str:
    departments = state.get("departments") or []
    beds = state.get("beds") or []
    labs = state.get("labTests") or []
    hospitals = state.get("hospitals") or []
    if agent == "Patient Flow Analyst Agent" and departments:
        top = max(departments, key=lambda d: int(d.get("waitMins", 0)))
        return (f"The highest average wait in the supplied snapshot is {top.get('name', 'Unknown')}: "
                f"{top.get('waitMins', 'N/A')} minutes, {top.get('waiting', 'N/A')} waiting, "
                f"and {top.get('loadPct', 'N/A')}% load. Treat this as synthetic operational data, "
                "not a clinical triage decision.")
    if agent == "Bed Availability Analyst Agent" and beds:
        counts = {s: sum(1 for b in beds if b.get("status") == s)
                  for s in ("Available", "Occupied", "Maintenance")}
        return (f"The supplied bed registry contains {len(beds)} beds: {counts['Available']} available, "
                f"{counts['Occupied']} occupied and {counts['Maintenance']} in maintenance.")
    if agent == "Laboratory Coordination Agent" and labs:
        pending = [x for x in labs if x.get("stage") != "Notified"]
        ready = [x for x in labs if x.get("stage") == "Ready"]
        ready_ids = ", ".join(str(x.get("id")) for x in ready) or "none"
        return f"There are {len(pending)} lab orders not yet marked Notified. {len(ready)} are Ready: {ready_ids}. This is a simulated workflow; no real messages are sent."
    if agent == "Resource Coordination Agent" and hospitals:
        partners = [h for h in hospitals if h.get("id") != "HOSP-01"]
        best = max(partners, key=lambda h: int(h.get("icuAvailable", 0)), default=None)
        if best:
            return (f"Among the supplied partner records, {best.get('name')} has the highest listed ICU availability "
                    f"({best.get('icuAvailable')}) and {best.get('availableBeds')} total available beds. "
                    "Verify availability directly before any real-world coordination.")
    total_waiting = sum(int(d.get("waiting", 0)) for d in departments)
    avg_wait = round(sum(int(d.get("waitMins", 0)) for d in departments) / len(departments)) if departments else "N/A"
    available = sum(1 for b in beds if b.get("status") == "Available")
    return (f"Snapshot summary: {len(departments)} departments, {total_waiting} waiting across those departments, "
            f"average department wait {avg_wait} minutes, {available}/{len(beds)} tracked beds available, "
            f"and {sum(1 for x in labs if x.get('stage') != 'Notified')} lab orders not yet notified.")


def propose_action(agent: str, query: str, state: dict) -> Optional[dict]:
    q = query.lower()
    if agent == "Bed Availability Analyst Agent" and any(w in q for w in ("bed", "maintenance", "icu")):
        bed = next((b for b in state.get("beds", []) if b.get("status") == "Maintenance"), None)
        if bed:
            return {"id": str(uuid.uuid4()), "label": f"Review {bed.get('id')} for maintenance clearance", "type": "clear-bed", "target": bed.get("id"), "status": "pending"}
    if agent == "Laboratory Coordination Agent" and any(w in q for w in ("lab", "report", "notif")):
        lab = next((x for x in state.get("labTests", []) if x.get("stage") == "Ready"), None)
        if lab:
            return {"id": str(uuid.uuid4()), "label": f"Queue simulated readiness notification for {lab.get('id')}", "type": "notify-lab", "target": lab.get("id"), "status": "pending"}
    return None


@app.get("/")
def frontend():
    return FileResponse(ROOT / "frontend" / "index.html")

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "FlowMed Nexus 2.0", "version": "2.1.0", "synthetic_data": True,
            "gemini_configured": bool(os.getenv("GEMINI_API_KEY")),
            "ai_provider": "Gemini" if os.getenv("GEMINI_API_KEY") else "rules-demo"}

@app.get("/api/hospitals")
def hospitals():
    records = firestore_docs("hospitals") if FIRESTORE_DB is not None else SEED_DATA["hospitals"]
    return {"hospitals": records or SEED_DATA["hospitals"], "synthetic_data": True}

@app.get("/api/sops")
def sops():
    records = firestore_docs("sop_documents") if FIRESTORE_DB is not None else SEED_DATA["sop_documents"]
    return {"sops": records or SEED_DATA["sop_documents"]}

@app.post("/api/ai/query")
def query_ai(payload: AIQueryRequest):
    if CLINICAL_TERMS.search(payload.query):
        return {"agent": "Operations Reporting Agent",
                "answer": "I can help with hospital operations only. I cannot provide diagnoses, prescriptions, medication guidance, or treatment decisions.",
                "reasoning": "Safety boundary: clinical decision requests are outside this prototype's scope.",
                "sops_cited": [], "proposed_action": None, "mode": "safety-guardrail"}

    agent = choose_agent(payload.query, payload.agent)
    matched = retrieve_sops(payload.query)
    grounded = make_grounded_summary(agent, payload.live_state)
    answer = grounded
    mode = "rules-demo"
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key and genai is not None:
        try:
            client = genai.Client(api_key=api_key)
            prompt = f"""Explain this hospital OPERATIONS snapshot for a hackathon demo.
Do not diagnose, prescribe, recommend treatment, triage individuals, or invent facts.
Use only the supplied snapshot and SOP text. Clearly say data is synthetic. If the data is insufficient, say so.
Agent: {agent}
User question: {payload.query}
Grounded computed facts: {grounded}
Operational state JSON: {json.dumps(payload.live_state, ensure_ascii=False)}
Retrieved SOP documents: {json.dumps(matched, ensure_ascii=False)}
Return a concise answer with: observation, relevant SOP implication, and safe next operational step.
Do not claim any action was executed. Human approval is required for all consequential actions."""
            response = client.models.generate_content(
                model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
                contents=prompt,
            )
            if response.text and response.text.strip():
                answer = response.text.strip()
                mode = "gemini-live"
            client.close()
        except Exception as exc:
            # Surface fallback transparently; do not silently pretend Gemini answered.
            mode = "rules-fallback"
            answer += f"\n\nGemini is temporarily unavailable; this answer uses deterministic rules instead. ({type(exc).__name__})"

    action = propose_action(agent, payload.query, payload.live_state)
    if action:
        PENDING_ACTIONS[action["id"]] = {**action, "created_at": now_iso(), "role_requested": payload.role}
    return {"agent": agent, "answer": answer,
            "reasoning": f"Computed from the supplied synthetic dashboard state; retrieved {len(matched)} SOP document(s).",
            "sops_cited": [s["id"] for s in matched],
            "proposed_action": action,
            "requires_human_approval": bool(action),
            "mode": mode,
            "synthetic_data": True}

@app.post("/api/actions/{action_id}/decision")
def decide_action(action_id: str, payload: DecisionRequest):
    action = PENDING_ACTIONS.get(action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found or already processed. Ask the assistant to generate a fresh recommendation.")
    if action.get("status") != "pending":
        raise HTTPException(status_code=409, detail="This action has already been processed.")
    # Demo-only role gate. Real identity/authentication is required before production use.
    if payload.role not in ("Hospital Administrator", "Department Coordinator", "Network Coordinator"):
        raise HTTPException(status_code=403, detail="Role is not permitted.")
    action["status"] = "approved" if payload.approved else "dismissed"
    action["decided_at"] = now_iso()
    action["decided_by"] = payload.role
    audit(payload.role, "AI action approved (simulated)" if payload.approved else "AI action dismissed",
          action.get("target", "unknown"), action.get("label", ""), payload.approved)
    return {"ok": True, "action": action, "message": "Recorded in the demo audit log. No real hospital system or notification was changed."}

@app.get("/api/audit-logs")
def audit_logs():
    if FIRESTORE_DB is not None:
        return {"logs": firestore_docs("audit_logs"), "synthetic_data": True, "persistence": "firestore"}
    return {"logs": AUDIT_LOG, "synthetic_data": True, "persistence": "in-memory demo only"}
