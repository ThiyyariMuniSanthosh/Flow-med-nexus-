from __future__ import annotations

import copy
import html
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator

BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"
DATASET_FILE = BASE_DIR / "sample_dataset.json"

app = FastAPI(
    title="FlowMed Nexus 2.0 API",
    description="Autonomous Hospital Operations & AI Bed-Balancing Command Engine",
    version="2.0.0",
)

allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins if origin.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next: Any) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response


def sanitize_text(value: str, max_len: int = 200) -> str:
    cleaned = re.sub(r"[<>]", "", str(value)).strip()
    return html.escape(cleaned[:max_len], quote=True)


DEFAULT_WARDS: list[dict[str, Any]] = [
    {"id": "emergency", "name": "Emergency & Trauma", "total": 20, "free": 6, "status": "Active"},
    {"id": "general", "name": "General Medicine", "total": 50, "free": 18, "status": "Active"},
    {"id": "icu", "name": "Intensive Care (ICU)", "total": 15, "free": 3, "status": "Active"},
    {"id": "paediatrics", "name": "Paediatrics Ward", "total": 25, "free": 11, "status": "Active"},
]

DEFAULT_PATIENTS: list[dict[str, str]] = [
    {"id": "FM-1001", "name": "Alex Rivera", "department": "Cardiology", "acuity": "Priority 2", "status": "Checked in"},
    {"id": "FM-1002", "name": "Sara Morgan", "department": "Neurology", "acuity": "Routine", "status": "Scheduled"},
    {"id": "FM-1003", "name": "Jordan Kim", "department": "General Medicine", "acuity": "Priority 2", "status": "Under review"},
    {"id": "FM-1004", "name": "Priya Nair", "department": "Paediatrics", "acuity": "Priority 1", "status": "Admitted · Ward D"},
    {"id": "FM-1005", "name": "Liam Carter", "department": "Emergency", "acuity": "Stable", "status": "Discharged"},
]


def load_initial_state() -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    if DATASET_FILE.exists():
        try:
            raw = json.loads(DATASET_FILE.read_text(encoding="utf-8"))
            wards_data = raw.get("wards")
            patients_data = raw.get("patients")
            if isinstance(wards_data, list) and wards_data:
                return copy.deepcopy(wards_data), copy.deepcopy(patients_data or DEFAULT_PATIENTS)
        except (json.JSONDecodeError, OSError):
            pass
    return copy.deepcopy(DEFAULT_WARDS), copy.deepcopy(DEFAULT_PATIENTS)


WARDS, PATIENTS = load_initial_state()
AUDIT_LOGS: list[dict[str, str]] = [
    {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": "SYSTEM_BOOT",
        "target_ward": "All Hospital Wards",
        "operator": "ops.admin@flowmed-nexus.demo",
    }
]


class WardCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    total: int = Field(..., ge=1, le=2000)
    free: int = Field(..., ge=0, le=2000)
    status: Literal["Active", "High Alert", "Maintenance"] = "Active"

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        cleaned = sanitize_text(v, 80)
        if len(cleaned) < 2:
            raise ValueError("Ward name must be at least 2 valid characters.")
        return cleaned


class BedAdjustment(BaseModel):
    delta: Literal[-1, 1]


class CopilotQuery(BaseModel):
    question: str = Field(..., min_length=2, max_length=500)


def log_audit(event: str, target_ward: str, operator: str = "ops.admin@flowmed-nexus.demo") -> None:
    AUDIT_LOGS.insert(
        0,
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": sanitize_text(event, 60),
            "target_ward": sanitize_text(target_ward, 80),
            "operator": sanitize_text(operator, 80),
        },
    )


def compute_metrics() -> dict[str, Any]:
    total_beds = sum(int(w["total"]) for w in WARDS)
    free_beds = sum(int(w["free"]) for w in WARDS)
    occupied_beds = max(0, total_beds - free_beds)
    occupancy_pct = round((occupied_beds / total_beds) * 100) if total_beds > 0 else 0
    sorted_wards = sorted(WARDS, key=lambda w: (w["free"] / w["total"]) if w["total"] else 1.0)
    busiest = sorted_wards[0] if sorted_wards else None
    openest = sorted_wards[-1] if sorted_wards else None
    return {
        "total_beds": total_beds,
        "available_beds": free_beds,
        "occupied_beds": occupied_beds,
        "occupancy_pct": occupancy_pct,
        "ward_count": len(WARDS),
        "busiest_ward": busiest["name"] if busiest else None,
        "openest_ward": openest["name"] if openest else None,
    }


@app.get("/", include_in_schema=False)
def serve_frontend() -> Response:
    if INDEX_FILE.exists():
        return FileResponse(INDEX_FILE)
    return JSONResponse({"service": "FlowMed Nexus 2.0", "status": "operational"})


@app.get("/api/health")
def health_check() -> dict[str, Any]:
    return {
        "status": "optimal",
        "service": "FlowMed Nexus 2.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metrics": compute_metrics(),
    }


@app.get("/api/metrics")
def get_metrics() -> dict[str, Any]:
    return {"metrics": compute_metrics(), "wards": WARDS}


@app.get("/api/wards")
def list_wards() -> list[dict[str, Any]]:
    return WARDS


@app.post("/api/wards", status_code=201)
def create_ward(payload: WardCreate) -> dict[str, Any]:
    if payload.free > payload.total:
        raise HTTPException(status_code=422, detail="Available beds cannot exceed total beds.")
    ward_id = re.sub(r"[^a-z0-9]+", "-", payload.name.lower()).strip("-") or f"ward-{len(WARDS) + 1}"
    if any(w["id"] == ward_id for w in WARDS):
        ward_id = f"{ward_id}-{len(WARDS) + 1}"
    ward = {
        "id": ward_id,
        "name": payload.name,
        "total": payload.total,
        "free": payload.free,
        "status": payload.status,
    }
    WARDS.append(ward)
    log_audit("CREATED_WARD", ward["name"])
    return ward


@app.post("/api/wards/{ward_id}/adjust")
def adjust_ward_beds(ward_id: str, payload: BedAdjustment) -> dict[str, Any]:
    ward = next((w for w in WARDS if w["id"] == ward_id), None)
    if not ward:
        raise HTTPException(status_code=404, detail="Ward not found.")
    next_free = int(ward["free"]) + payload.delta
    if next_free < 0 or next_free > int(ward["total"]):
        raise HTTPException(status_code=400, detail="Bed adjustment exceeds ward capacity bounds.")
    ward["free"] = next_free
    log_audit("PATIENT_ADMITTED" if payload.delta < 0 else "PATIENT_DISCHARGED", ward["name"])
    return {"ward": ward, "metrics": compute_metrics()}


@app.delete("/api/wards/{ward_id}")
def delete_ward(ward_id: str) -> dict[str, str]:
    idx = next((i for i, w in enumerate(WARDS) if w["id"] == ward_id), None)
    if idx is None:
        raise HTTPException(status_code=404, detail="Ward not found.")
    removed = WARDS.pop(idx)
    log_audit("REMOVED_WARD", removed["name"])
    return {"deleted": ward_id}


@app.post("/api/simulate-surge")
def simulate_er_surge() -> dict[str, Any]:
    remaining = 6
    allocated = 0
    for ward in WARDS:
        if remaining > 0 and ward["free"] > 0:
            take = min(int(ward["free"]), remaining, 2)
            ward["free"] -= take
            remaining -= take
            allocated += take
    log_audit("ER_SURGE_SIMULATED", f"Allocated {allocated} emergency beds")
    return {"allocated": allocated, "metrics": compute_metrics(), "wards": WARDS}


@app.post("/api/reset")
def reset_state() -> dict[str, Any]:
    global WARDS, PATIENTS
    WARDS, PATIENTS = load_initial_state()
    log_audit("RESET_TELEMETRY", "All Wards")
    return {"status": "reset", "metrics": compute_metrics(), "wards": WARDS}


@app.post("/api/copilot")
def ai_copilot(payload: CopilotQuery) -> dict[str, Any]:
    question = sanitize_text(payload.question, 500)
    lower = question.lower()
    metrics = compute_metrics()
    busiest = metrics["busiest_ward"] or "ICU"
    openest = metrics["openest_ward"] or "General Medicine"

    if "handoff" in lower or "shift" in lower:
        intent = "shift_handoff"
        recommendation = (
            f"Shift Handoff Summary: {metrics['occupied_beds']} of {metrics['total_beds']} beds occupied "
            f"({metrics['occupancy_pct']}%). Prioritize step-down review in {busiest} and stage buffer capacity in {openest}."
        )
    elif "surge" in lower or "reallocation" in lower:
        intent = "er_surge_plan"
        recommendation = (
            f"Autonomous Surge Plan: Divert non-critical Priority 2 admissions to {openest} and initiate "
            f"step-down transfers from {busiest} to preserve critical trauma availability."
        )
    else:
        intent = "capacity_analysis"
        recommendation = (
            f"Network Utilization at {metrics['occupancy_pct']}% ({metrics['available_beds']} beds free). "
            f"Primary bottleneck is {busiest}; route incoming step-down transfers toward {openest}."
        )

    return {
        "question": question,
        "intent": intent,
        "recommendation": recommendation,
        "metrics": metrics,
    }


@app.get("/api/patients")
def list_patients(q: str = "") -> list[dict[str, str]]:
    term = sanitize_text(q, 100).lower()
    if not term:
        return PATIENTS
    return [
        p for p in PATIENTS
        if term in p["name"].lower() or term in p["id"].lower() or term in p["department"].lower()
    ]


@app.get("/api/audit")
def get_audit_logs() -> list[dict[str, str]]:
    return AUDIT_LOGS[:50]
