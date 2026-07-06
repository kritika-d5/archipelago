"""
Per-browser session identity.

Anonymous exploration must keep working (no login required), but each browser needs
its own stable, unguessable id so its Composio (GitHub/Notion) connection and, later,
its stored graphs are isolated from every other visitor. The frontend generates this id
once and sends it on every request as the `X-Session-Id` header.

Phase 0.3+ will map this session id to a persistent `owner_id` and, on login, to a user.
"""
import re
from typing import Optional

from fastapi import Header, HTTPException

# UUIDs, url-safe tokens, etc. Bounded length; no characters that could be unsafe to pass
# through to Composio's user_id or into a Mongo query.
_SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{8,128}$")


def get_session_id(x_session_id: Optional[str] = Header(default=None)) -> str:
    """FastAPI dependency: return the validated per-browser session id.

    Raises 400 if the header is missing or malformed so the client knows to (re)generate
    one rather than silently sharing a single global identity.
    """
    token = (x_session_id or "").strip()
    if not _SESSION_RE.match(token):
        raise HTTPException(
            status_code=400,
            detail="Missing or invalid X-Session-Id header. Reload the app to generate a session.",
        )
    return token
