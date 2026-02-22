"""
Generate LLM system overview summary for onboarding (architecture paragraph, services, patterns, flows).
"""
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

OVERVIEW_PROMPT = """You are a senior engineer writing architectural documentation.
Based ONLY on the following data, produce a clear system overview.

GLOBAL GRAPH (nodes and edges):
{graph_snippet}

REPOSITORY DATA (summary):
{repo_snippet}

VIOLATIONS (if any):
{violations_snippet}

DOCUMENTATION (if any):
{docs_snippet}

Produce:
1. Overview paragraph (2-4 sentences) describing the architecture.
2. List of services (names and one-line role).
3. Core architectural pattern (e.g. microservices, event-driven).
4. Primary dependency chain (e.g. auth → order → payment).
5. Event-driven relationships (who publishes what, who consumes).

Format as clear markdown. Do not invent services or dependencies not present in the data."""


def generate_system_overview(
    client,
    model: str,
    global_graph: Dict[str, Any],
    repo_data: Dict[str, Dict[str, Any]],
    violations: list,
    notion_docs: str = "",
) -> str:
    """Generate system overview text using LLM. Used for Section 1 — System Overview."""
    graph_snippet = json.dumps(
        {"nodes": global_graph.get("nodes", [])[:50], "edges": global_graph.get("edges", [])[:80]},
        indent=2,
    )[:6000]
    repo_snippet = json.dumps(
        {k: {"services": v.get("services", [])[:5], "api_endpoints": (v.get("api_endpoints") or [])[:10]} for k, v in list(repo_data.items())[:15]},
        indent=2,
    )[:4000]
    violations_snippet = json.dumps(violations[:20], indent=2)[:2000]
    docs_snippet = (notion_docs or "")[:2000]

    prompt = OVERVIEW_PROMPT.format(
        graph_snippet=graph_snippet,
        repo_snippet=repo_snippet,
        violations_snippet=violations_snippet,
        docs_snippet=docs_snippet,
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You write concise, accurate technical documentation. Use only the provided data."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=1500,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        logger.error(f"Overview generation failed: {e}")
        return ""
