# FlowMed Nexus 2.0 — Autonomous Hospital Operations & AI Command

FlowMed Nexus 2.0 is a full-stack hospital telemetry and predictive bed-allocation platform built to eliminate emergency room bottlenecks and optimize ward capacity in real time.

## Problem Statement Alignment
Hospital emergency departments frequently face overcrowding due to delayed ward visibility and manual bed transfers. FlowMed Nexus 2.0 combines real-time ward occupancy tracking, automated ER surge simulation, and a multi-intent AI Operations Copilot to recommend step-down transfers and shift handoffs before wards hit critical capacity.

## System Architecture
- **Backend (`main.py`):** FastAPI REST engine with Pydantic schema validation, real-time capacity telemetry, audit trail logging, and multi-intent AI copilot routing.
- **Frontend (`index.html`):** Zero-latency reactive dashboard with interactive ward admission/discharge controls, live surge simulation, and role-based operator governance.
- **Data Layer (`schema.sql`, `sample_dataset.json`):** Normalized relational hospital ward, patient triage, and audit log schema.

## Security & Data Hygiene
- **Input Sanitization:** All user-supplied ward names, search queries, and AI copilot prompts are stripped of HTML tags (`<`, `>`) and escaped prior to storage or rendering.
- **XSS-Safe DOM Rendering:** Frontend dynamic views use `document.createElement` and `.textContent` exclusively (zero `.innerHTML` injection vectors).
- **HTTP Security Headers & CORS:** Enforces `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, and strict origin allowlisting.

## WCAG Accessibility Compliance
- Semantic HTML5 landmarks (`<aside>`, `<nav>`, `<main id="main-content">`, `<header>`, `<section>`).
- Full ARIA coverage including `aria-label` on all inputs and action buttons, `role="progressbar"` with `aria-valuenow` on occupancy meters, `aria-current="page"` on active navigation, and `aria-live="polite"` on AI copilot outputs.

## Running Automated Tests (`test_api.py`)
```bash
pip install -r requirements.txt
pytest -v
