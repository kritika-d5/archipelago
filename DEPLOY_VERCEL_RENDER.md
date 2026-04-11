# Deploy Archipelago on **Render** (API) + **Vercel** (frontend)

Overview: **Render** runs the Python/FastAPI backend. **Vercel** builds and hosts the React app. The browser calls your Render URL; CORS must allow your Vercel domain.

---

## 1. MongoDB

Use [MongoDB Atlas](https://www.mongodb.com/atlas) (or any reachable MongoDB). Copy the connection string for **`MONGO_URI`**.

---

## 2. Deploy the API on Render

1. Push this repo to GitHub/GitLab/Bitbucket.
2. Open [Render Dashboard](https://dashboard.render.com) → **New +** → **Blueprint** (or **Web Service**).
3. **If using Blueprint**: connect the repo; Render detects `render.yaml` at the repo root.
4. **If using Web Service manually**:
   - **Runtime**: Python 3
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. In **Environment**, add (use **Secret** where noted):
   | Key | Example / notes |
   |-----|-----------------|
   | `MONGO_URI` | Atlas connection string (Secret) |
   | `GROQ_API_KEY` | For LLM features (Secret) |
   | `CORS_ORIGINS` | Your Vercel URLs (see below) |
   | `FRONTEND_PUBLIC_URL` | **Required for “Connect GitHub” (Composio)** — your Vercel site root, e.g. `https://your-app.vercel.app` (no trailing slash). If unset, OAuth redirects to `http://localhost:3000/connect-callback`. |
   | `COMPOSIO_API_KEY` | Optional (needed for GitHub/Notion connect) |
6. Deploy and wait for a **public URL**, e.g. `https://archipelago-api-xxxx.onrender.com`.

### `CORS_ORIGINS` (required for the browser)

Comma-separated list, **no spaces** (or spaces are trimmed). Include every origin that will load the React app, for example:

```text
https://your-app.vercel.app,https://your-custom-domain.com
```

After your first Vercel deploy, copy the production URL (and preview URL if you use previews) and add them here, then **redeploy** the Render service or save env to apply.

Local dev still works: `localhost:3000` and `127.0.0.1:3000` are always allowed in code.

### Render free tier

The service **spins down** after inactivity; the first request can take ~30–60s. Upgrade for always-on if needed.

---

## 3. Deploy the frontend on Vercel

1. Go to [Vercel](https://vercel.com) → **Add New** → **Project** → import the same Git repo.
2. **Configure Project**:
   - **Root Directory**: `frontend` (important)
   - **Framework Preset**: Create React App (or “Other” with `npm run build` / output `build`)
   - **Build Command**: `npm run build`
   - **Output Directory**: `build`
3. **Environment Variables** (Production — and Preview if you use previews):

   | Name | Value |
   |------|--------|
   | `REACT_APP_API_URL` | `https://archipelago-api-xxxx.onrender.com` (your Render URL, **no trailing slash**) |

   Create React App bakes this in at **build time**. Change it → trigger a **redeploy** on Vercel.

4. Deploy. Your app URL will look like `https://your-app.vercel.app`.

5. Put that URL (and custom domain if any) into Render’s **`CORS_ORIGINS`**, redeploy Render if needed.

`frontend/vercel.json` adds SPA **rewrites** so client-side routes (e.g. `/hub`, `/graph`) work on refresh.

---

## 4. Verify

1. Open `https://your-api.onrender.com/` → JSON welcome message.
2. Open `https://your-api.onrender.com/docs` → Swagger.
3. Open the Vercel site → Dashboard / Health; network tab should show XHR to the Render host, not `127.0.0.1`.

---

## 5. Optional: custom domain

- **Vercel**: Project → Settings → Domains.
- **Render**: Web Service → Settings → Custom Domain.
- Update **`CORS_ORIGINS`** to include the new HTTPS origin.

---

## 6. Composio / “Connect GitHub” redirect

The API builds the OAuth return URL as **`{FRONTEND_PUBLIC_URL}/connect-callback`**. If **`FRONTEND_PUBLIC_URL`** is missing on Render, it defaults to **`http://localhost:3000`**, so after login you land on localhost (what you saw).

**Fix:** On Render, set:

`FRONTEND_PUBLIC_URL=https://your-app.vercel.app`

(no path, no trailing slash). Redeploy the service.

In the [Composio dashboard](https://app.composio.dev), if your app has **allowed redirect URLs**, add:

`https://your-app.vercel.app/connect-callback`

---

## 7. Troubleshooting

| Issue | What to check |
|--------|----------------|
| OAuth opens localhost after GitHub login | Set **`FRONTEND_PUBLIC_URL`** on Render to your Vercel URL; redeploy. |
| CORS errors in browser | `CORS_ORIGINS` on Render matches the exact Vercel URL (scheme + host, no path). |
| API calls fail / wrong host | `REACT_APP_API_URL` on Vercel; rebuild after changes. |
| 502 / timeout on Render | Cold start (free tier) or crash on boot — check Render **Logs**; confirm `MONGO_URI` and imports. |
| Mongo connection errors | Atlas **Network Access** allows `0.0.0.0/0` (or Render outbound IPs). |

---

## Repo files added for this flow

- `render.yaml` — Render Blueprint for the API (`rootDir: backend`).
- `frontend/vercel.json` — SPA fallback rewrites.
- `frontend/src/services/api.js` — uses `REACT_APP_API_URL` when set.
- `backend/app/config.py` + `main.py` — `CORS_ORIGINS` and `FRONTEND_PUBLIC_URL` (Composio callback) support.
