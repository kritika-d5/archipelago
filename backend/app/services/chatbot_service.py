"""
Onboarding chatbot: full structured context injection, no chunking.
Answers only from provided graph, repo_data, violations, summaries, docs.
"""
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an AI architectural onboarding assistant helping a new engineer understand a microservices organization.
Use ONLY the provided graph, repository data, violations, summaries, and documentation below.
Do not hallucinate. Do not invent services, APIs, or dependencies.
If the answer cannot be derived from the context, say: "This is not defined in the current architecture."
Be concise and accurate."""


def build_full_context(
    global_graph: Dict[str, Any],
    repo_data: Dict[str, Dict[str, Any]],
    violations: List[Dict[str, Any]],
    llm_summaries: Optional[Dict[str, Any]] = None,
    notion_docs: str = "",
) -> str:
    """
    Build a single context string from all sources (no chunking).
    Used as the injected context for the onboarding chatbot.
    """
    parts = []

    parts.append("=== GLOBAL GRAPH ===")
    parts.append(json.dumps(global_graph, indent=2)[:12000])
    parts.append("")

    parts.append("=== REPOSITORY DATA (per service) ===")
    parts.append(json.dumps(repo_data, indent=2)[:12000])
    parts.append("")

    parts.append("=== VIOLATIONS ===")
    parts.append(json.dumps(violations, indent=2)[:4000])
    parts.append("")

    if llm_summaries:
        parts.append("=== SUMMARIES ===")
        parts.append(json.dumps(llm_summaries, indent=2)[:8000])
        parts.append("")

    if notion_docs and notion_docs.strip():
        parts.append("=== DOCUMENTATION ===")
        parts.append(notion_docs[:8000])
        parts.append("")

    return "\n".join(parts)


def chat(
    client,
    model: str,
    user_message: str,
    context: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    Send user message with full context. No retrieval/chunking.
    conversation_history: list of {"role": "user"|"assistant", "content": "..."}
    """
    if conversation_history is None:
        conversation_history = []

    user_content = f"""Use the following context to answer the question. If the answer is not in the context, reply: "This is not defined in the current architecture."

CONTEXT:
{context}

QUESTION: {user_message}"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *[
            {"role": m["role"], "content": m["content"]}
            for m in conversation_history[-10:]
        ],
        {"role": "user", "content": user_content},
    ]

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.2,
            max_tokens=1500,
        )
        return response.choices[0].message.content or "No response."
    except Exception as e:
        logger.error(f"Chatbot LLM error: {e}")
        raise
