from __future__ import annotations

import copy
import html
import json
import os
import re
import secrets
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Path as ApiPath, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator

BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"
STYLES_FILE = BASE_DIR / "styles.css"
SCRIPT_FILE = BASE_DIR / "app.js"
DATASET_FILE = BASE_DIR / "sample_dataset.json"

ADMIN_API_TOKEN = os.getenv("FLOWMED_ADMIN_TOKEN") or secrets.token_urlsafe(32)
ENFORCE_AUTH = os.getenv("FLOWMED_ENFORCE_AUTH", "0") == "1"

app = FastAPI(
    title="FlowMed Nexus 2.0 API",
    description="Autonomous Hospital Operations & AI Bed-Balancing Command Engine",
    version="2.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(GZipMiddleware, minimum_size=512)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver,*.github.io").split(","),
)

allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in allowed_origins if o.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-Operator-Token"],
)

RATE_BUCKET: dict[str, deque[float]] = {}
RATE_LIMIT_WINDOW = 60.0
RATE_LIMIT_MAX = 100
MAX_BODY_BYTES = 32_768
PROMPT_INJECTION_PATTERN = re.compile(r"(ignore previous instructions|system prompt|<script|javascript:|onerror=|onload=)", re.IGNORECASE)


def sanitize_text(value: str, max_len: int = 200) -> str:
    no_ctrl = re.sub(r"[\r\n\t\x00-\x1f\x7f<>\"'`;]", " ", str(value)).strip()
    collapsed = re.sub(r"\s{2,}", " ", no_ctrl)
    return html.escape(collapsed[:max_len], quote=True)


@app.middleware("http")
async def owasp_security_middleware(request: Request, call_next: Any) -> Response:
    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    history = RATE_BUCKET.setdefault(client_ip, deque())
    while history and now - history[0] > RATE_LIMIT_WINDOW:
        history.popleft()
    if len(history) >= RATE_LIMIT_MAX:
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded."})
    history.append(now)

    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_BODY_BYTES:
        return JSONResponse(status_code=413, content={"detail": "Request payload exceeds 32KB limit."})

    if request.method in {"POST", "PUT", "PATCH"} and content_length and int(content_length) > 0:
        ctype = request.headers.get("content-type", "")
        if "application/json" not in ctype.lower():
            return JSONResponse(status_code=415, content={"detail": "Unsupported Media Type. Use application/json."})

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "0"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=(), payment=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    )
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    return response


@app.exception_handler(Exception)
async def safe_global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": "Internal processing error."})


def verify_operator_token(x_operator_token: str | None = Header(default=None)) -> str:
    if ENFORCE_AUTH and not x_operator_token:
        log_audit("AUTH_MISSING_TOKEN", "Admin Endpoint", "unauthenticated")
        raise HTTPException(status_code=401, detail="Operator token required.")
    if x_operator_token is not None and not secrets.compare_digest(x_operator_token, ADMIN_API_TOKEN):
        log_audit("AUTH_INVALID_TOKEN", "Admin Endpoint", "unauthenticated")
        raise HTTPException(status_code=401, detail="Invalid operator credentials.")
    return "ops.admin@flowmed-nexus.demo"


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


def load_initial_state() -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    wards_list = copy.deepcopy(DEFAULT_WARDS)
    patients_list = copy.deepcopy(DEFAULT_PATIENTS)
    if DATASET_FILE.exists():
        try:
            raw = json.loads(DATASET_FILE.read_text(encoding="utf-8"))
            if isinstance(raw.get("wards"), list) and raw["wards"]:
                wards_list = copy.deepcopy(raw["wards"])
            if isinstance(raw.get("patients"), list) and raw["patients"]:
                patients_list = copy.deepcopy(raw["patients"])
        except (json.JSONDecodeError, OSError):
            pass
    return {w["id"]: w for w in wards_list}, patients_list


WARD_INDEX, PATIENTS = load_initial_state()
AUDIT_LOGS: deque[dict[str, str]] = deque(
    [
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "SYSTEM_BOOT",
            "target_ward": "All Hospital Wards",
            "operator": "ops.admin@flowmed-nexus.demo",
        }
    ],
    maxlen=200,
)


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
            raise ValueError("Ward name must contain at least 2 valid characters.")
        return cleaned


class BedAdjustment(BaseModel):
    delta: Literal[-1, 1]


class CopilotQuery(BaseModel):
    question: str = Field(..., min_length=2, max_length=500)


def log_audit(event: str, target_ward: str, operator: str = "ops.admin@flowmed-nexus.demo") -> None:
    AUDIT_LOGS.appendleft(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": sanitize_text(event, 60),
            "target_ward": sanitize_text(target_ward, 80),
            "operator": sanitize_text(operator, 80),
        }
    )


def compute_metrics() -> dict[str, Any]:
    wards = list(WARD_INDEX.values())
    total_beds = sum(int(w["total"]) for w in wards)
    free_beds = sum(int(w["free"]) for w in wards)
    occupied_beds = max(0, total_beds - free_beds)
    occupancy_pct = round((occupied_beds / total_beds) * 100) if total_beds > 0 else 0
    sorted_wards = sorted(wards, key=lambda w: (w["free"] / w["total"]) if w["total"] else 1.0)
    busiest = sorted_wards[0] if sorted_wards else None
    openest = sorted_wards[-1] if sorted_wards else None
    return {
        "total_beds": total_beds,
        "available_beds": free_beds,
        "occupied_beds": occupied_beds,
        "occupancy_pct": occupancy_pct,
        "ward_count": len(wards),
        "busiest_ward": busiest["name"] if busiest else None,
        "openest_ward": openest["name"] if openest else None,
    }


@app.get("/", include_in_schema=False)
def serve_frontend() -> Response:
    if INDEX_FILE.exists():
        return FileResponse(INDEX_FILE, media_type="text/html")
    return JSONResponse({"service": "FlowMed Nexus 2.0", "status": "operational"})


@app.get("/styles.css", include_in_schema=False)
def serve_styles() -> Response:
    if STYLES_FILE.exists():
        return FileResponse(STYLES_FILE, media_type="text/css")
    raise HTTPException(status_code=404, detail="Stylesheet not found.")


@app.get("/app.js", include_in_schema=False)
def serve_script() -> Response:
    if SCRIPT_FILE.exists():
        return FileResponse(SCRIPT_FILE, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="Script not found.")


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
    return {"metrics": compute_metrics(), "wards": list(WARD_INDEX.values())}


@app.get("/api/wards")
def list_wards() -> list[dict[str, Any]]:
    return list(WARD_INDEX.values())


@app.post("/api/wards", status_code=201)
def create_ward(payload: WardCreate, operator: str = Depends(verify_operator_token)) -> dict[str, Any]:
    if payload.free > payload.total:
        raise HTTPException(status_code=422, detail="Available beds cannot exceed total beds.")
    base_id = re.sub(r"[^a-z0-9]+", "-", payload.name.lower()).strip("-") or f"ward-{len(WARD_INDEX) + 1}"
    ward_id = base_id if base_id not in WARD_INDEX else f"{base_id}-{len(WARD_INDEX) + 1}"
    ward = {
        "id": ward_id,
        "name": payload.name,
        "total": payload.total,
        "free": payload.free,
        "status": payload.status,
    }
    WARD_INDEX[ward_id] = ward
    log_audit("CREATED_WARD", ward["name"], operator)
    return ward


@app.post("/api/wards/{ward_id}/adjust")
def adjust_ward_beds(
    payload: BedAdjustment,
    ward_id: str = ApiPath(..., pattern=r"^[a-z0-9-]{2,64}$"),
    operator: str = Depends(verify_operator_token),
) -> dict[str, Any]:
    ward = WARD_INDEX.get(ward_id)
    if not ward:
        raise HTTPException(status_code=404, detail="Ward not found.")
    next_free = int(ward["free"]) + payload.delta
    if next_free < 0 or next_free > int(ward["total"]):
        raise HTTPException(status_code=400, detail="Bed adjustment exceeds ward capacity bounds.")
    ward["free"] = next_free
    log_audit("PATIENT_ADMITTED" if payload.delta < 0 else "PATIENT_DISCHARGED", ward["name"], operator)
    return {"ward": ward, "metrics": compute_metrics()}


@app.delete("/api/wards/{ward_id}")
def delete_ward(
    ward_id: str = ApiPath(..., pattern=r"^[a-z0-9-]{2,64}$"),
    operator: str = Depends(verify_operator_token),
) -> dict[str, str]:
    removed = WARD_INDEX.pop(ward_id, None)
    if not removed:
        raise HTTPException(status_code=404, detail="Ward not found.")
    log_audit("REMOVED_WARD", removed["name"], operator)
    return {"deleted": ward_id}


@app.post("/api/simulate-surge")
def simulate_er_surge(operator: str = Depends(verify_operator_token)) -> dict[str, Any]:
    remaining = 6
    allocated = 0
    for ward in WARD_INDEX.values():
        if remaining > 0 and ward["free"] > 0:
            take = min(int(ward["free"]), remaining, 2)
            ward["free"] -= take
            remaining -= take
            allocated += take
    log_audit("ER_SURGE_SIMULATED", f"Allocated {allocated} emergency beds", operator)
    return {"allocated": allocated, "metrics": compute_metrics(), "wards": list(WARD_INDEX.values())}


@app.post("/api/reset")
def reset_state(operator: str = Depends(verify_operator_token)) -> dict[str, Any]:
    global WARD_INDEX, PATIENTS
    WARD_INDEX, PATIENTS = load_initial_state()
    log_audit("RESET_TELEMETRY", "All Wards", operator)
    return {"status": "reset", "metrics": compute_metrics(), "wards": list(WARD_INDEX.values())}


@app.post("/api/copilot")
def ai_copilot(payload: CopilotQuery) -> dict[str, Any]:
    if PROMPT_INJECTION_PATTERN.search(payload.question):
        raise HTTPException(status_code=400, detail="Unsafe prompt pattern rejected.")
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
    return list(AUDIT_LOGS)[:50]
