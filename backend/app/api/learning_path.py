"""
Learning Path + AI Onboarding API.
GET /api/org/{org_id}/learning-path
GET /api/org/{org_id}/flows
POST /api/org/{org_id}/chat
"""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from app.core.db import get_graph, get_parsed_data, get_org_learning_metadata, save_org_learning_metadata
from app.services.graph_service import get_main_flow_highlight
from app.services.flow_service import get_major_flows
from app.services.learning_path_service import compute_learning_path
from app.services.chatbot_service import build_full_context, chat as chatbot_chat
from app.services.onboarding_summary_service import generate_system_overview

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/org", tags=["learning-path"])


def _org_key(org_id: str) -> str:
    if org_id.startswith("org:"):
        return org_id
    return f"org:{org_id}"


def _load_org_data(org_id: str) -> tuple:
    org_key = _org_key(org_id)
    graph_doc = get_graph(org_key)
    parsed_doc = get_parsed_data(org_key)
    if not graph_doc or not graph_doc.get("graph_data"):
        raise HTTPException(status_code=404, detail=f"Organization graph not found: {org_id}")
    if not parsed_doc or not parsed_doc.get("parsed_data"):
        raise HTTPException(status_code=404, detail=f"Organization repo data not found: {org_id}")

    global_graph = graph_doc["graph_data"]
    repo_data = parsed_doc["parsed_data"]
    violations = global_graph.get("violations", [])
    return global_graph, repo_data, violations, org_key


@router.get("/{org_id}/learning-path")
async def get_learning_path(org_id: str) -> Dict[str, Any]:
    """
    Returns learning path (topological order + service details), system overview summary,
    main flow highlight path, and graph/metadata for the frontend.
    """
    global_graph, repo_data, violations, org_key = _load_org_data(org_id)

    # Learning path (pure graph)
    path_result = compute_learning_path(global_graph, repo_data, violations)

    # Main flow highlight (longest path, no violation edges)
    main_flow = get_main_flow_highlight(global_graph)

    # Optional: LLM system overview (cache in org_learning_metadata)
    llm_summary_text = None
    meta = get_org_learning_metadata(org_key)
    if meta and meta.get("llm_summaries", {}).get("system_overview"):
        llm_summary_text = meta["llm_summaries"]["system_overview"]
    else:
        try:
            from app.core.llm import LLMService
            llm = LLMService()
            notion_docs = (meta or {}).get("notion_docs", "") or ""
            llm_summary_text = generate_system_overview(
                llm.client,
                llm.model,
                global_graph,
                repo_data,
                violations,
                notion_docs,
            )
            if llm_summary_text:
                save_org_learning_metadata(
                    org_key,
                    llm_summaries={"system_overview": llm_summary_text},
                    notion_docs=meta.get("notion_docs", "") if meta else "",
                )
        except Exception as e:
            logger.warning(f"Could not generate system overview: {e}")

    return {
        "org_id": org_id,
        "global_graph": global_graph,
        "learning_order": path_result["learning_order"],
        "service_details": path_result["service_details"],
        "main_flow_highlight": main_flow,
        "system_overview_summary": llm_summary_text or "",
        "violations": violations,
        "metadata": {
            "total_services": len(global_graph.get("nodes", [])),
            "total_edges": len(global_graph.get("edges", [])),
            "total_violations": len(violations),
        },
    }


def _describe_flow_with_llm(client, model: str, path: List[str]) -> Dict[str, str]:
    """Generate a short title and readable description for a flow path."""
    try:
        path_str = " → ".join(path)
        prompt = f"""Given this service chain: {path_str}
Return a JSON object with two keys: "title" (short flow name, e.g. "Order Placement Flow") and "description" (2-4 sentences explaining the flow). No other text."""
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You output only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=300,
        )
        import json
        text = (response.choices[0].message.content or "").strip()
        # Extract JSON if wrapped in markdown
        if "```" in text:
            text = text.split("```")[1].replace("json", "").strip()
        out = json.loads(text)
        return {"title": out.get("title", " → ".join(path)), "description": out.get("description", "")}
    except Exception as e:
        logger.warning(f"Flow description failed: {e}")
        return {"title": " → ".join(path), "description": ""}


@router.get("/{org_id}/flows")
async def get_flows(org_id: str) -> Dict[str, Any]:
    """Returns 2-3 major flows with optional LLM-generated title and description."""
    global_graph, _, _, _ = _load_org_data(org_id)
    flows = get_major_flows(global_graph, max_flows=3, min_path_length=2)
    try:
        from app.core.llm import LLMService
        llm = LLMService()
        for f in flows:
            desc = _describe_flow_with_llm(llm.client, llm.model, f["path"])
            f["title"] = desc["title"]
            f["description"] = desc["description"]
    except Exception as e:
        logger.warning(f"Flow descriptions skipped: {e}")
        for f in flows:
            f.setdefault("title", " → ".join(f["path"]))
            f.setdefault("description", "")
    return {"org_id": org_id, "flows": flows}


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = None


@router.post("/{org_id}/chat")
async def post_chat(org_id: str, body: ChatRequest) -> Dict[str, Any]:
    """
    Onboarding chatbot: full context injection, no chunking.
    Answers only from global graph, repo data, violations, summaries, docs.
    """
    global_graph, repo_data, violations, org_key = _load_org_data(org_id)

    meta = get_org_learning_metadata(org_key)
    llm_summaries = (meta or {}).get("llm_summaries") if meta else None
    notion_docs = (meta or {}).get("notion_docs", "") or ""

    context = build_full_context(
        global_graph,
        repo_data,
        violations,
        llm_summaries=llm_summaries,
        notion_docs=notion_docs,
    )

    try:
        from app.core.llm import LLMService
        llm = LLMService()
    except Exception as e:
        raise HTTPException(status_code=503, detail="LLM service unavailable")

    history = []
    if body.history:
        history = [{"role": m.role, "content": m.content} for m in body.history]

    answer = chatbot_chat(llm.client, llm.model, body.message, context, conversation_history=history)

    return {"answer": answer, "org_id": org_id}
