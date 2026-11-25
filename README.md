# FlowMed Nexus 2.0
**AI-Powered Hospital Capacity & Coordination Intelligence Platform**

> Connecting Hospital Intelligence. Improving Patient Flow.

FlowMed Nexus is a synthetic-data demonstration of hospital operations coordination: patient-flow bottleneck analysis, bed visibility, laboratory workflow tracking, cross-hospital capacity comparison, and a human-reviewed AI operations assistant.

## What's improved in this build
- The browser assistant now calls the FastAPI `/api/ai/query` endpoint instead of answering only with local JavaScript keyword rules.
- The backend retrieves relevant SOPs using transparent lexical matching and sends the selected SOPs plus the current dashboard snapshot to Gemini when `GEMINI_API_KEY` is configured.
- The backend returns a clearly labeled `gemini-live`, `rules-demo`, or `rules-fallback` mode so the demo never pretends Gemini was used when it was not.
- AI recommendations are registered server-side and require an explicit approval/dismissal request to `/api/actions/{id}/decision`.
- The dashboard is served by FastAPI at `/`, avoiding local-file CORS problems.
- Clinical diagnosis, prescription, medication and treatment requests are declined.

## Run locally
Python 3.10+ recommended.

```bash
# From the flowmed-nexus-2 folder
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
# Add GEMINI_API_KEY to .env (optional but recommended)
uvicorn backend.main:app --reload --port 8000
```

Open **http://127.0.0.1:8000**. API health: `http://127.0.0.1:8000/api/health`; interactive API docs: `http://127.0.0.1:8000/docs`.

### Gemini setup
1. Create an API key in Google AI Studio.
2. Put it in the root `.env` file as `GEMINI_API_KEY=...`.
3. Restart the server. Keep the key on the server; never paste it into `index.html`, GitHub, or a public screenshot.
4. Optional model override: `GEMINI_MODEL=gemini-3.8-flash`.

Without a key, the system remains demonstrable in `rules-demo` mode. That mode uses deterministic, state-grounded calculations, not generative AI.

## Demo flow for judges
1. Open the Operations Dashboard and note the synthetic-data disclaimer.
2. Go to AI Assistant and ask: **"Where is our biggest bottleneck right now?"**
3. Ask: **"Summarize bed availability and maintenance units."**
4. Ask: **"Which lab reports are ready for notification?"**
5. Review the proposed action and approve or dismiss it. Explain that approval is simulated and recorded in the demo audit log; it does not contact a hospital or patient.
6. Open `/api/docs` to show the backend endpoints and `/api/health` to show the active AI mode.

## Important scope and honest demo claims
- All hospital records, bed records, aliases, and metrics are synthetic.
- The approval and audit stores are in-memory and reset when the backend restarts. They are not immutable or production-grade.
- Bed/lab state changes after approval are reflected in the browser demo only. No external hospital system, SMS, or portal is modified.
- The current SOP retrieval is lexical keyword retrieval, not vector embeddings. Describe it as **SOP retrieval / lightweight RAG**, not a production vector database.
- The role selector is a demo workflow control, not authentication. Before production, add verified user identity, server-side RBAC, persistent PostgreSQL transactions, audit retention, rate limiting, and security review.
- This is not a clinical decision-support product and must not be used for real patient care.

## Project structure
```text
flowmed-nexus-2/
├── backend/main.py
├── backend/requirements.txt
├── database/sample_dataset.json
├── database/schema.sql
├── frontend/index.html
├── docs/DEPLOYMENT.md
├── .env.example
└── README.md
```


## Firebase Firestore connection (optional)

1. In Firebase Console, open Project settings → Service accounts → Generate new private key.
2. Put the complete JSON contents into your hosting provider's secret named `FIREBASE_SERVICE_ACCOUNT_JSON`. Never commit or share this key.
3. Set `FIREBASE_PROJECT_ID` to your Firebase project ID and `FIREBASE_SEED_ON_START=true`.
4. Install `backend/requirements.txt` and start with `uvicorn backend.main:app --host 0.0.0.0 --port 8000`.
5. Check `/api/firebase/status` and `/api/dashboard-data`. The seed routine creates top-level synthetic demo collections only when each collection is empty.

Firestore collections are created automatically on first write; manual creation is not required. Existing nested demo documents are not deleted. All records created by the seed routine are fictional.
