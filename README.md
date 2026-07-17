# Archipelago

**Archipelago** is an engineering knowledge platform that turns GitHub repositories (and whole organizations) into a **living knowledge graph**. Explore dependencies visually across multiple zoom levels, ask natural-language questions about the codebase, compare (and sync) documentation against the graph, generate architecture blueprints with an LLM, and get real code-intelligence insights in an architecture hub.

---

## Features

- **Repository & organization parsing** — Clone and analyze a single repo or an entire GitHub org (Python + JS/TS); results are persisted for visualization and queries. Interrupted clones self-heal on the next attempt.
- **Knowledge graph** — Interactive Cytoscape graph with three views: **Dependencies** (module import graph, laid out left-to-right via dagre), **Architecture** (folder-grouped), and **Files** (every element). Includes a connectivity slider to hide low-degree nodes, click-to-focus, and a fit-to-screen layout. The Ask/Docs side panel expands to fullscreen.
- **Ask the graph** — Natural-language Q&A scoped to the selected repo or `org:…` graph (`/api/query/ask`).
- **Documentation check + Notion sync** — Paste docs or pull a **Notion** page, diff it against the graph, and apply suggested edits straight back to the Notion page (`/api/query/doc-diff`, `/api/integrations/notion/update`).
- **Architecture Hub** — Per-repository **code insights**: composition (functions/classes/AI agents/DB models), most-connected and most-depended-upon modules, circular-dependency and god-module detection, entry points, folder structure, and plain-language observations (`/api/graph/{key}/insights`). Organization graphs show REST/event/violation statistics. The assistant chat expands to fullscreen.
- **Architecture Studio & blueprints** — Greenfield/brownfield architecture blueprints (JSON + Mermaid) via the LLM.
- **Integrations** — Optional Composio-powered GitHub and Notion flows (when configured).
- **Learning path & timeline** — Organization-level learning path and GitHub timeline endpoints.

---

## Tech stack

| Layer | Technologies |
|--------|----------------|
| **Frontend** | React 19, React Router, Axios, Cytoscape (+ dagre & cose-bilkent layouts), Recharts, React Markdown, Mermaid |
| **Backend** | Python 3.11+, FastAPI, Uvicorn, Pydantic v2 |
| **Graph / parsing** | NetworkX, GitPython, custom parsers |
| **LLM** | Groq API (`GROQ_API_KEY`) |
| **Database** | MongoDB (`MONGO_URI`) for persisted graphs and org data |
| **Optional** | Composio (`COMPOSIO_API_KEY` / `COMPOSIO_EKEY`) for OAuth integrations |

---

## Prerequisites

- **Node.js** (LTS) and **npm**
- **Python 3.11+** (for creating `backend/venv`)
- **MongoDB** reachable at your `MONGO_URI` if you use features that persist or load graphs from the database
- **Groq API key** for architecture generation and LLM-backed query features

---

## Quick start (Windows)

From the repo root:

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
| `FRONTEND_PUBLIC_URL` | Production | Public site URL for OAuth return (e.g. `https://app.vercel.app`). Defaults to `http://localhost:3000`. |
| `CORS_ORIGINS` | Production | Comma-separated browser origins allowed to call the API (e.g. your Vercel URL). |
| `REPO_STORAGE_DIR` | Optional | Where cloned repos are stored; if unset, temp storage may be used |
| `LOG_LEVEL` | Optional | Default `INFO` |
| `API_HOST` / `API_PORT` | Optional | Defaults `0.0.0.0` / `8000` |
| `GROQ_ARCHITECTURE_MAX_TOKENS` | Optional | Caps completion tokens for architecture calls (helps with Groq on-demand TPM limits; default in code is conservative) |

---

## Project layout

```
Archipelago/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app + routers
│   │   ├── api/             # parse, graph, query, architecture, org, integrations, …
│   │   ├── agents/          # graph_agent (views, insights) + architecture agents
│   │   ├── knowledge_graph/ # code_parser, repo_manager (clone/self-heal)
│   │   ├── core/            # db, llm, config
│   │   └── …
│   ├── requirements.txt
│   ├── setup_venv.bat       # Windows: create venv + pip install
│   └── run_dev.bat          # Windows: uvicorn with reload
├── frontend/
│   ├── src/
│   │   ├── pages/           # Landing, Dashboard, KnowledgeGraph, ArchitectureDashboard (Hub), …
│   │   ├── components/      # DashboardLayout, LoadingModal, NotionDocModal
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
| `/graph?repo=…` | Knowledge graph (Dependencies / Architecture / Files views) + Ask/Docs panel |
| `/hub` | Architecture Hub — per-repo insights & charts, or org REST/event stats |
| `/architecture` | Architecture Studio (reachable by URL; not in the top nav) |
| `/blueprint` | Greenfield blueprint flow ("Start with Words") |
| `/connect-github` | GitHub connection + parse flow |
| `/health` | System health page |

---

## API overview

The FastAPI app title is **“Archipelago — Living Knowledge Graph”**. Routers include (non-exhaustive):

- `/api/parse/` — Parse repositories and list parsed graphs
- `/api/graph/{key}/visualize?view=modules|architecture|files` — Graph views for the explorer
- `/api/graph/{key}/insights` — Per-repository code-intelligence insights (Hub)
- `/api/query/ask`, `/api/query/doc-diff` — Q&A and documentation diff
- `/api/integrations/…` — GitHub / Notion connection, pages, and `notion/update` (apply doc edits)
- `/architecture/…` — Blueprint generation
- `/api/org/…`, `/api/…/learning-path`, timeline routes as implemented in `app/api`

Interactive docs: **http://127.0.0.1:8000/docs** (when the server is running).


