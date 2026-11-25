# FlowMed Nexus 2.0 — Run & Deploy

## Local run (recommended first)

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
# Add GEMINI_API_KEY in .env
uvicorn backend.main:app --reload --port 8000
```

Open `http://127.0.0.1:8000`. The backend serves the frontend and API from one origin. Use `http://127.0.0.1:8000/docs` to inspect the API.

## Replit deployment
1. Import the complete project folder/repository.
2. Add `GEMINI_API_KEY` and optionally `GEMINI_MODEL` under Replit Secrets.
3. Use run command: `uvicorn backend.main:app --host 0.0.0.0 --port 8000`.
4. Open the generated web URL and verify `/api/health` reports `gemini_configured: true`.

## Render deployment
1. Push the project to a Git repository.
2. Create a **Web Service** and set the root directory to the project root.
3. Build command: `pip install -r backend/requirements.txt`.
4. Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`.
5. Add `GEMINI_API_KEY` as a secret environment variable.
6. Verify the service root and `/api/health` after deployment.

## Before any real-world/production deployment
This repository is a hackathon demo only. Add a persistent database integration, authenticated users, server-side role permissions, CSRF/security controls as applicable, rate limits, durable audit records, observability, backups, privacy/legal review, and clinical-safety review. Never connect synthetic workflows to a real hospital environment without formal authorization and validation.
