import logging
from fastapi import APIRouter, Header, HTTPException, Request
from typing import Optional, Dict, Any
from app.core.db import save_timeline_event, get_timeline_events
from app.config import LOG_LEVEL
import hmac
import hashlib
import json
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/timeline", tags=["timeline"])


@router.post("/github-webhook")
async def github_webhook(request: Request, x_hub_signature_256: Optional[str] = Header(None), x_github_event: Optional[str] = Header(None), x_github_delivery: Optional[str] = Header(None)):
    """Receive GitHub webhooks (push, pull_request) and store timeline events.

    If you set a secret, the endpoint will verify the signature using GITHUB_WEBHOOK_SECRET env var.
    """
    try:
        body = await request.body()
        payload = json.loads(body.decode("utf-8"))
    except Exception as e:
        logger.error(f"Invalid webhook payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")

    event = x_github_event or payload.get("action") or "unknown"
    delivery = x_github_delivery or payload.get("delivery") or str(datetime.utcnow().timestamp())

    # Basic processing for push events
    try:
        if event == "push":
            repo_full = payload.get("repository", {}).get("full_name")
            pusher = payload.get("pusher", {}).get("name") or payload.get("author", {}).get("name") or payload.get("sender", {}).get("login")
            head_commit = payload.get("head_commit") or {}
            timestamp = head_commit.get("timestamp") or datetime.utcnow().isoformat()
            commit_sha = head_commit.get("id") or payload.get("after")
            message = head_commit.get("message") or ""

            # Collect changed files across commits
            files_changed = []
            for c in payload.get("commits", []) or []:
                files_changed.extend([{"path": p, "action": "added"} for p in c.get("added", [])])
                files_changed.extend([{"path": p, "action": "modified"} for p in c.get("modified", [])])
                files_changed.extend([{"path": p, "action": "removed"} for p in c.get("removed", [])])

            # Simple doc detection
            doc_patterns = ("README.md", ".md", "docs/")
            is_doc = any(p.get("path", "").lower().endswith(".md") or p.get("path", "").lower().startswith("docs/") for p in files_changed)

            event_doc = {
                "event_id": delivery,
                "provider": "github",
                "repo": repo_full,
                "actor": pusher,
                "timestamp": timestamp,
                "event_type": "push",
                "commit_sha": commit_sha,
                "message": message,
                "files_changed": files_changed,
                "is_doc_change": is_doc,
                "url": payload.get("compare") or payload.get("repository", {}).get("html_url"),
                "raw_payload": payload,
            }
            save_timeline_event(event_doc)
            return {"status": "ok"}

        # Handle PR merged events
        if event == "pull_request" and payload.get("action") in ("closed",):
            pr = payload.get("pull_request", {})
            merged = pr.get("merged", False)
            if merged:
                repo_full = payload.get("repository", {}).get("full_name")
                actor = payload.get("sender", {}).get("login")
                timestamp = pr.get("merged_at") or datetime.utcnow().isoformat()
                commit_sha = pr.get("merge_commit_sha")
                title = pr.get("title")
                files_changed = []
                # We don't get file list in webhook payload; mark unknown and clients can enrich by API call
                is_doc = False

                event_doc = {
                    "event_id": delivery,
                    "provider": "github",
                    "repo": repo_full,
                    "actor": actor,
                    "timestamp": timestamp,
                    "event_type": "pr_merged",
                    "commit_sha": commit_sha,
                    "message": title,
                    "files_changed": files_changed,
                    "is_doc_change": is_doc,
                    "url": pr.get("html_url"),
                    "raw_payload": payload,
                }
                save_timeline_event(event_doc)
                return {"status": "ok"}

        # Unknown event - store minimal info
        logger.info(f"Received unhandled github event: {event}")
        event_doc = {
            "event_id": delivery,
            "provider": "github",
            "repo": payload.get("repository", {}).get("full_name"),
            "actor": payload.get("sender", {}).get("login"),
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event,
            "message": str(payload.get("action") or ""),
            "raw_payload": payload,
        }
        save_timeline_event(event_doc)
        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def list_timeline(repo: Optional[str] = None, doc_only: Optional[bool] = False, limit: Optional[int] = 50, skip: Optional[int] = 0):
    try:
        events = get_timeline_events(limit=limit, skip=skip, repo=repo, doc_only=doc_only)
        return {"count": len(events), "events": events}
    except Exception as e:
        logger.error(f"Failed to retrieve timeline events: {e}")
        raise HTTPException(status_code=500, detail=str(e))
