# Archipelago

**Archipelago** is an engineering knowledge platform that turns GitHub repositories (and whole organizations) into a **living knowledge graph**. You can explore dependencies visually, ask natural-language questions about the codebase, compare documentation to the graph, generate architecture blueprints with an LLM, and use an architecture hub with metrics and learning-path style views.

---

## Features

- **Repository & organization parsing** — Clone and analyze a single repo or an entire GitHub org; results are stored for visualization and queries.
- **Knowledge graph** — Interactive dependency graph (Cytoscape) with support for repo keys and `org:…` organization graphs.
- **Q&A** — Ask questions in context of a selected graph (`/api/query`).
- **Documentation check** — Paste docs and get suggestions against the graph (`doc-diff`).
- **Architecture Studio** — Greenfield and brownfield architecture blueprints (JSON + Mermaid) via Groq.
- **Architecture Hub** — Dashboard-style view with charts and graph (`/hub`).
- **Integrations** — Optional Composio-powered flows for GitHub, Notion, and related APIs (when configured).
- **Learning path & timeline** — Organization-level learning path and GitHub timeline endpoints (see backend routers).

---

## Tech stack

| Layer | Technologies |
|--------|----------------|
| **Frontend** | React 19, React Router, Axios, Cytoscape, Recharts, React Markdown, Mermaid |
| **Backend** | Python 3.11+, FastAPI, Uvicorn, Pydantic v2 |
| **Graph / parsing** | NetworkX, GitPython, custom parsers |
| **LLM** | Groq API (`GROQ_API_KEY`) |
| **Database** | MongoDB (`MONGO_URI`), database name **`archipelago`** |
| **Optional** | Composio (`COMPOSIO_API_KEY` / `COMPOSIO_EKEY`) for OAuth integrations |

---

## Prerequisites

- **Node.js** (LTS) and **npm**
- **Python 3.11+** (for creating `backend/venv`)
- **MongoDB** reachable at your `MONGO_URI` if you use features that persist or load graphs from the database
- **Groq API key** for architecture generation and LLM-backed query features

---

## Quick start (Windows)

From the repository root:

1. **Backend environment**

   ```bat
   cd backend
   setup_venv.bat
   ```

2. **Configure secrets**

   Create `backend/.env` (see [Environment variables](#environment-variables)). At minimum you typically need `GROQ_API_KEY` and `MONGO_URI` for full functionality.

3. **Start backend and frontend together**

   ```bat
   start_all.bat
   ```

   This starts:

   - Backend: Uvicorn with reload (from `backend\venv`)
   - Frontend: `npm start` in `frontend`

4. **Open the app**

   - Frontend: [http://localhost:3000](http://localhost:3000)
   - API: [http://127.0.0.1:8000](http://127.0.0.1:8000) — root returns a short JSON status

---

## Manual run (any OS)

**Backend** (always use the project venv, not global Python):

```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend**:

```bash
cd frontend
npm install
npm start
```

The frontend is configured to call the API at `http://127.0.0.1:8000` (see `frontend/src/services/api.js`). CORS allows `http://localhost:3000` and `http://127.0.0.1:3000`.

---

## Environment variables

Create **`backend/.env`** (never commit it; it is gitignored).

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | For LLM features | Groq API key for chat, architecture blueprints, and related endpoints |
| `MONGO_URI` | For DB-backed graphs | MongoDB connection string |
| `COMPOSIO_API_KEY` or `COMPOSIO_EKEY` | Optional | Composio for GitHub / Notion / Slack style integrations |
| `REPO_STORAGE_DIR` | Optional | Where cloned repos are stored; if unset, temp storage may be used |
| `LOG_LEVEL` | Optional | Default `INFO` |
| `API_HOST` / `API_PORT` | Optional | Defaults `0.0.0.0` / `8000` |
| `GROQ_ARCHITECTURE_MAX_TOKENS` | Optional | Caps completion tokens for architecture calls (helps with Groq on-demand TPM limits; default in code is conservative) |

### MongoDB database name

The app uses the MongoDB database **`archipelago`**. If you previously used an older database named `mangobytes`, copy or rename that database in MongoDB, or export/import collections into `archipelago`.

---

## Project layout

```
<repo-root>/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app + routers
│   │   ├── api/             # parse, graph, query, architecture, org, integrations, …
│   │   ├── agents/          # graph + architecture agents
│   │   ├── core/            # db, llm, config
│   │   └── …
│   ├── requirements.txt
│   ├── setup_venv.bat       # Windows: create venv + pip install
│   └── run_dev.bat          # Windows: uvicorn with reload
├── frontend/
│   ├── src/
│   │   ├── pages/           # Landing, Dashboard, KnowledgeGraph, Hub, …
│   │   ├── components/
│   │   └── services/api.js
│   └── package.json
├── start_all.bat            # Windows: backend (venv) + frontend
└── README.md
```

---

## Useful routes (frontend)

| Path | Purpose |
|------|---------|
| `/` | Landing — connect GitHub or start from a text blueprint |
| `/dashboard` | Parse repos / orgs and list parsed graphs |
| `/graph?repo=…` | Knowledge graph + chat + documentation check |
| `/hub` | Architecture hub (metrics, charts, graph) |
| `/architecture` | Architecture Studio |
| `/blueprint` | Greenfield blueprint flow |
| `/connect-github` | GitHub connection flow |
| `/health` | Health check page (if implemented) |

---

## API overview

The FastAPI app title is **“Archipelago — Living Knowledge Graph”**. Routers include (non-exhaustive):

- `/api/parse/` — Parse repositories and list parsed graphs
- `/api/graph/…` — Visualization and saved graph data
- `/api/query/…` — Ask and doc-diff
- `/architecture/…` — Blueprint generation
- `/api/org/…`, `/api/integrations/…`, `/api/…/learning-path`, timeline routes as implemented in `app/api`

Interactive docs: **http://127.0.0.1:8000/docs** (when the server is running).

---

## Groq rate limits

Groq’s free / on-demand tiers enforce **tokens per minute (TPM)**. Very large prompts or high `max_tokens` can return `413` or rate-limit errors. The architecture agent uses a configurable cap (`GROQ_ARCHITECTURE_MAX_TOKENS`) to stay within typical limits; upgrade your Groq tier or reduce request size if you still hit limits.

---

## Contributing

Issues and pull requests are welcome. Use `backend/venv` (or an equivalent local venv) for Python dependencies so versions stay aligned with `requirements.txt`.
