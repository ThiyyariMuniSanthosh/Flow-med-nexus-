# Security Policy — FlowMed Nexus 2.0
- **Input & Prompt Sanitization:** All ward, patient, and AI copilot inputs strip HTML/control characters and reject prompt-injection patterns.
- **XSS-Safe DOM Rendering:** Frontend dynamic views use `document.createElement` and `.textContent` exclusively without `.innerHTML`.
- **API Hardening:** Enforces `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, HSTS, strict `application/json` content-type validation (`HTTP 415`), sliding-window rate limiting (`HTTP 429`), and constant-time operator token comparison (`secrets.compare_digest`).
