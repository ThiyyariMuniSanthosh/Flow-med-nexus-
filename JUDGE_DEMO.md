# 90-second judge demo script

**Opening (10 sec)**
“FlowMed Nexus is a hospital operations coordination prototype. Hospitals often hold bed, laboratory and capacity information in separate workflows. Our demo brings a synthetic view of those operational signals into one command workspace.”

**Problem + dashboard (15 sec)**
“Here the dashboard shows department wait times, bed states, lab workflow stages and a five-hospital sample network. Every record is synthetic, so we are demonstrating the workflow without exposing patient information.”

**AI + SOP retrieval (30 sec)**
Open AI Assistant and ask: `Where is our biggest bottleneck right now?`
Then ask: `Summarize bed availability and maintenance units.`
Explain that the API computes facts from the supplied dashboard snapshot, retrieves matching SOP documents, and uses Gemini to explain them when a server-side key is configured. Show the provider mode in the assistant reasoning and `/api/health`.

**Human review (20 sec)**
Ask: `Summarize bed availability and maintenance units.` If an action is proposed, inspect the target and choose Approve or Dismiss. Explain that the backend records the decision, while the UI mirrors the approved change in this simulated demo. No real bed, hospital, portal or SMS is changed.

**Close (15 sec)**
“Our focus is operational coordination, explainability and human approval—not automated clinical decisions. The next engineering milestone is persistent database storage and authenticated role permissions.”

## Judge questions to prepare for
- **Is the data real?** No. All data is synthetic and visibly labeled.
- **Is Gemini really connected?** When configured, yes: the backend calls the Google Gen AI SDK. `/api/health` reports whether a key is configured; the AI response shows `gemini-live` only after a successful model response.
- **Is this a real multi-agent system?** The current build routes queries to five named specialist roles. It is a lightweight single-orchestrator design, not five independently deployed autonomous agents.
- **Is this production-ready?** No. Persistence, authentication, server-side authorization, audit durability and formal healthcare validation are future requirements.
- **Does approval send messages or change real beds?** No. It records a simulated decision only.
