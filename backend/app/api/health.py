"""
Health and platform diagnostics: MongoDB, stored graphs, architecture violations, LLM summary.
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends

from app.config import GROQ_API_KEY
from app.core.session import get_optional_session_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/health", tags=["health"])


def _violation_detail(v: Any, graph_name: str) -> Optional[Dict[str, Any]]:
    """Normalize a single violation entry to a dict for the API."""
    if v is None:
        return None
    if isinstance(v, dict):
        detail = (
            v.get("message")
            or v.get("description")
            or v.get("summary")
            or v.get("type")
            or str(v)
        )
        out = {"graph_name": graph_name, "detail": detail}
        for key in ("type", "from", "to", "severity", "circular"):
            if key in v and v[key] is not None:
                out[key] = v[key]
        return out
    return {"graph_name": graph_name, "detail": str(v)}


def _collect_graph_violations(owner_id: str) -> Dict[str, Any]:
    """Scan a single owner's MongoDB graphs for metadata violations and flagged edges."""
    violations: List[Dict[str, Any]] = []
    graph_names: List[str] = []

    try:
        from app.core import db as db_module

        if db_module.db is None:
            return {
                "stored_graphs": 0,
                "graph_names": [],
                "violations": [],
                "violation_count": 0,
                "mongo_error": "Database not initialized (check MONGO_URI)",
            }

        cursor = db_module.db.graphs.find({"owner_id": owner_id}, {"graph_name": 1, "graph_data": 1})
        for doc in cursor:
            name = doc.get("graph_name") or "unknown"
            graph_names.append(name)
            gd = doc.get("graph_data") or {}
            meta = gd.get("metadata") or {}
            raw = meta.get("violations")
            if isinstance(raw, list):
                for item in raw:
                    norm = _violation_detail(item, name)
                    if norm:
                        violations.append(norm)
            elif raw is not None:
                norm = _violation_detail(raw, name)
                if norm:
                    violations.append(norm)

            for edge in gd.get("edges") or []:
                data = edge.get("data", edge) if isinstance(edge, dict) else {}
                if not isinstance(data, dict):
                    continue
                if data.get("violation") or data.get("circular"):
                    src = data.get("source", "?")
                    tgt = data.get("target", "?")
                    rel = data.get("relation") or data.get("dependency_type") or "dependency"
                    flag = "circular" if data.get("circular") else "violation"
                    violations.append(
                        {
                            "graph_name": name,
                            "detail": f"[{flag}] {src} → {tgt} ({rel})",
                            "type": flag,
                            "from": src,
                            "to": tgt,
                        }
                    )

        return {
            "stored_graphs": len(graph_names),
            "graph_names": graph_names[:50],
            "violations": violations[:200],
            "violation_count": len(violations),
            "mongo_error": None,
        }
    except Exception as e:
        logger.exception("Health: failed to scan graphs")
        return {
            "stored_graphs": 0,
            "graph_names": [],
            "violations": [],
            "violation_count": 0,
            "mongo_error": str(e),
        }


def _llm_health_summary(payload: Dict[str, Any]) -> Optional[str]:
    """Ask Groq for a short narrative given aggregated stats."""
    if not GROQ_API_KEY:
        return None
    try:
        from app.core.llm import LLMService

        svc = LLMService()
        viol = payload.get("violations") or []
        sample = viol[:25]
        lines = [f"- {v.get('graph_name')}: {v.get('detail')}" for v in sample]
        sample_block = "\n".join(lines) if lines else "(none listed)"
        names_sample = ", ".join((payload.get("graph_names") or [])[:15]) or "none"

        user_prompt = f"""Platform health snapshot for engineers:

- Service: Archipelago API
- MongoDB connected: {payload.get("mongodb_connected")}
- Stored graphs in DB: {payload.get("stored_graphs", 0)}
- Total violation records collected: {payload.get("violation_count", 0)}
- Graph names (sample): {names_sample}

Violation samples:
{sample_block}

Write 2 short paragraphs (no markdown headings):
1) Overall posture and data availability
2) Architecture / graph risks from violations (if any), and one concrete next step. If there are zero violations, say so clearly and suggest preventive habits."""

        resp = svc.client.chat.completions.create(
            model=svc.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a concise SRE/architecture analyst. Plain text only, no bullet stars if you can use sentences.",
                },
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.35,
            max_tokens=500,
        )
        msg = resp.choices[0].message
        return (msg.content or "").strip() or None
    except Exception as e:
        logger.warning("Health LLM summary failed: %s", e)
        return f"(LLM summary unavailable: {str(e)[:200]})"


@router.get("/")
def health_check(session_id: Optional[str] = Depends(get_optional_session_id)):
    """
    Extended health: API up, Mongo ping, and — only when a valid X-Session-Id is present —
    that caller's own graph/violation scan plus an optional Groq narrative. Without a session
    the endpoint still works as a liveness probe but exposes no per-user data.
    """
    mongodb_connected = False
    mongo_detail: Optional[Dict[str, Any]] = None
    mongo_error: Optional[str] = None

    try:
        from app.core import db as db_module

        if db_module.client is not None and db_module.db is not None:
            db_module.client.admin.command("ping")
            mongodb_connected = True
    except Exception as e:
        mongo_error = str(e)
        logger.warning("Health: MongoDB ping failed: %s", e)

    # Per-owner graph scan only when the caller presents a valid session.
    if session_id:
        graph_info = _collect_graph_violations(session_id)
    else:
        graph_info = {
            "stored_graphs": 0,
            "graph_names": [],
            "violations": [],
            "violation_count": 0,
            "mongo_error": None,
        }
    if graph_info.get("mongo_error") and not mongo_error:
        mongo_error = graph_info["mongo_error"]

    violation_count = int(graph_info.get("violation_count") or 0)
    stored_graphs = int(graph_info.get("stored_graphs") or 0)

    payload_for_llm = {
        "mongodb_connected": mongodb_connected,
        "stored_graphs": stored_graphs,
        "violation_count": violation_count,
        "violations": graph_info.get("violations") or [],
        "graph_names": graph_info.get("graph_names") or [],
    }

    llm_summary: Optional[str] = None
    if GROQ_API_KEY and mongodb_connected:
        llm_summary = _llm_health_summary(payload_for_llm)
    elif not GROQ_API_KEY:
        llm_summary = None

    # Overall API is "up" if this handler runs; data plane may be degraded
    if not mongodb_connected:
        status = "degraded"
    elif violation_count > 0:
        status = "healthy_with_violations"
    else:
        status = "healthy"

    return {
        "status": status,
        "service": "Archipelago",
        "api": "up",
        "mongodb_connected": mongodb_connected,
        "mongodb": mongo_detail,
        "mongodb_error": mongo_error,
        "groq_configured": bool(GROQ_API_KEY),
        "stored_graphs": stored_graphs,
        "graph_names": graph_info.get("graph_names") or [],
        "violation_count": violation_count,
        "violations": graph_info.get("violations") or [],
        "llm_health_summary": llm_summary,
    }
