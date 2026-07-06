# Archipelago — Remediation Plan

Assessment of the deployed (Vercel + Render) build, prioritized. Each item cites the
file(s) to change. Phases are ordered by "fix the dangerous thing first, then make the
core feature actually work, then make it survive Render."

Design constraints (from product owner):
- Anonymous users must still be able to **explore** and **connect GitHub / Notion** without logging in.
- **Login is optional** and exists only to **save progress** (graphs, connections) across sessions/devices.
- Keep it simple.

---

## Phase 0 — Stop the data leak (do before anything else)

> **Status:**
> - 0.1 ✅ DONE (2026-07-06) — per-session `X-Session-Id` identity; Composio entity is now
>   per-session via `connected_accounts.link()` (switched off the Tool Router flow that a
>   scoped key can't use); `composio==0.17.1` / `pydantic==2.13.4` pinned. Connect flow is
>   idempotent (reuses the active connection; non-mutating `/status/{toolkit}` probe replaces
>   the page-load `connect-url` call that was stacking duplicate accounts); `tools.execute`
>   targets a specific `connected_account_id` so listing works with >1 connection. Requires a
>   write-scoped project key + per-toolkit `COMPOSIO_AUTH_CONFIG_*` env vars.
> - 0.2a ✅ DONE (2026-07-06) — Mongo `graphs` / `parsed_data` / `org_learning_metadata`
>   documents carry `owner_id` (= session id); every read/write in db.py filters by it, and
>   `session_id` is threaded through parse, graph, organization, architecture, query,
>   learning_path. Health endpoint (0.3) folded in: graph scan is now per-owner and only runs
>   when a valid session is present; stopped leaking Mongo collection names.
>   - **Caveats / follow-ups:** (a) Data written before 0.2a has no `owner_id` and is now
>     invisible (safe to purge). (b) `timeline` (webhook events) intentionally NOT session-scoped
>     yet — separate pass.
> - 0.2b ✅ DONE (2026-07-06) — removed the global in-memory `parsed_graphs` dict entirely.
>   Single-repo graphs are now reconstructed on demand from the per-owner `parsed_data`
>   collection via `load_codebase_graph(repo_key, owner_id)` (CodebaseGraph round-trips through
>   Mongo since its indexes are model fields). This isolates single-repo graphs per owner AND
>   makes them survive Render restarts / multiple workers — **also closes Phase 2.1's durability
>   gap** for graph state. Threaded through graph.py (visualize, element, file, impact, explain,
>   subgraph), query.py (ask, what-if), and parse.py (list/get/json/delete + scoped `delete_graph`).
> - Remaining: 0.4 (validate clone URLs), 0.5 (error leakage), Phase 2.2 (background parse job).

The app is currently an open proxy to whatever GitHub/Notion account is connected, and
the health endpoint exposes every user's data. Because connecting must work *without*
login, the fix is **per-session identity**, not "require auth."

### 0.1 Per-session identity for isolation
- Generate a random, unguessable `session_id` per browser on first visit (frontend:
  create in `localStorage`, send as an `X-Session-Id` header on every API call via
  `frontend/src/services/api.js`).
- Backend: a small dependency that reads/validates `X-Session-Id` and yields it to handlers.
- **Composio entity must be this `session_id`**, not the constant.
  - `backend/app/api/integrations.py:10` — remove `COMPOSIO_ENTITY_ID = "archipelago_default"`.
  - Thread the session id into `get_connect_url`, `list_github_repos`, `list_github_orgs`,
    `list_notion_pages`, `get_notion_page_content`, `update_notion_page`
    (all `user_id=` calls at integrations.py:42, 69).
  - Result: each browser has its own isolated GitHub/Notion connection.

### 0.2 Namespace all stored data by owner
- Add an `owner_id` field (= `session_id`, later linked to a `user_id` on login) to every
  document written by `backend/app/core/db.py` (`save_graph`, `save_parsed_data`,
  `save_org_learning_metadata`, `save_timeline_event`).
- Change the unique key from `graph_name` alone to `(owner_id, graph_name)` so two sessions
  analyzing the same repo don't overwrite each other (db.py:54, 72).
- Filter **every** read by `owner_id`: `get_graph`, `get_all_graphs`, `get_parsed_data`,
  `get_timeline_events` (db.py:89, 104, 119, 194).

### 0.3 Lock down the health endpoint
- `backend/app/api/health.py:53` `db.graphs.find({})` scans everyone's graphs. Options:
  - Scope it to the caller's `owner_id`, OR
  - Split into a public liveness probe (`{status, api:"up"}` only) and an
    admin-only diagnostics route gated by an `ADMIN_TOKEN` env var.
- Stop returning Mongo collection names / error strings to anonymous callers (health.py:170-175).

### 0.4 Validate repo URLs before cloning (SSRF / DoS)
- `backend/app/knowledge_graph/repo_manager.py:34` clones any URL. Add:
  - Allow-list scheme+host (`https://github.com/...` only for now).
  - `--depth 1` shallow clone, a clone timeout, and a max on-disk size / file count.
  - Reject `file://`, `git://`, ssh, and localhost/private IPs.

### 0.5 Stop leaking internal errors
- Replace `raise HTTPException(500, detail=str(e))` with a logged exception + generic
  message across `integrations.py`, `parse.py`, etc.

---

## Phase 1 — Make the graph actually show dependencies

This is the "barely shows anything / no dependencies mapped" problem. Root causes are in
the parser and a split data model.

### 1.1 Resolve dependency edges to real node IDs
`backend/app/knowledge_graph/code_parser.py`:
- **Function calls (line ~362):** target is hardcoded to the same file
  (`function:{rel_path}:{name}`). Build a symbol table first (name → defining file), then
  resolve calls across files. Drop or mark-as-external anything unresolved instead of
  emitting a dangling edge.
- **Inheritance (line ~297):** target `class:{base}` has no path and never matches a real
  node. Resolve base classes against the symbol table / imports.
- **Imports → edges (line ~172):** imports are stored as strings but never become edges.
  Emit module→module `IMPORT` edges (this is the single highest-value change for a useful graph).
- Net rule: **never emit an edge whose target node doesn't exist** — that's why the UI shows
  isolated nodes today.

### 1.2 Unify the two graph models
- Single-repo parse emits `CodebaseGraph` (`elements`/`dependencies`), but flow/health/arch
  expect `nodes`/`edges` with `type` in {REST, EVENT, IMPORT, DB_ACCESS}
  (`graph_service.py:20`, `cross_repo_dependency_engine.py:226`).
- Pick ONE canonical shape (recommend `nodes`/`edges`) and add an adapter so a single repo's
  module/import graph flows through the same visualization + violation logic as org graphs.

### 1.3 Broaden language coverage (or set expectations)
- `code_parser.py:391` only parses Python; everything else returns an empty module. Either:
  - Add a real parser for JS/TS (e.g. tree-sitter) — biggest coverage win, OR
  - Short term: surface a clear "language not yet supported" state in the UI so an empty
    graph isn't mistaken for a bug.

### 1.4 Improve cross-repo detection (lower priority)
- `cross_repo_dependency_engine.py` infers edges by substring-matching repo names in import
  strings (lines 66-182). Fragile. Improve once single-repo import resolution (1.1) exists,
  since it can reuse the resolved import data.

---

## Phase 2 — Survive Render (reliability)

### 2.1 Remove in-memory state
- `backend/app/api/parse.py:13` keeps results in a process-memory dict; Render sleeps/restarts
  and (with >1 worker) reads miss → 404. Read/write graphs from Mongo only.

### 2.2 Make parsing a background job
- `parse.py:17` clones + parses synchronously on the event loop; `BackgroundTasks` is imported
  but unused. Large repos exceed Render's request timeout (502). Move to a background task with
  a `job_id`, a `GET /status/{job_id}` poll endpoint, and a "processing" UI state.

### 2.3 Lazy DB reconnect
- `backend/app/core/db.py:38` connects once at import; if Mongo is down at boot, `db` stays
  `None` forever. Add reconnect-on-use.

### 2.4 Clean up clones
- `repo_manager.py:24` clones into temp with no eviction; add cleanup after parse and/or a size cap.

---

## Phase 3 — Optional login (save progress)

Only after Phase 0's session identity exists. Login *claims* a session; it does not gate exploration.

- Simple email + password (or magic link). Minimal user collection.
- On login, associate the current `session_id`'s `owner_id` with the `user_id` so previously
  saved graphs/connections carry over; on future logins, reuse the same `owner_id`.
- Anonymous users keep working exactly as before — they just can't persist across devices.
- Never gate `/connect-url`, repo listing, or parse behind login.

---

## Phase 4 — Hygiene

- Remove committed build artifacts: `frontend/build/**` and `**/__pycache__/*.pyc` are tracked.
  Add to `.gitignore` and `git rm --cached`.
- `code_parser.py:217` method-detection is O(n²) per file — track class scope in one pass.
- Standardize timestamps on timezone-aware UTC (`db.py` mixes `datetime.now()` / `utcnow()`).
- Revisit CORS (`main.py:19`, `allow_credentials=True` + `["*"]`) once auth/origins are locked.

---

## Suggested execution order
1. Phase 0 (0.1 → 0.5) — safety. Consider gating the public URL until 0.1–0.3 land.
2. Phase 1.1 + 1.2 — makes the core feature visibly work.
3. Phase 2.1 + 2.2 — durability on Render.
4. Phase 1.3, Phase 3, Phase 4 — coverage, persistence, cleanup.
