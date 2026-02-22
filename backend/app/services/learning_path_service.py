"""
Learning path service: topological sort, service weight = in+out edges, learning_order + service_details.
Uses pure graph logic (no AI).
"""
import networkx as nx
from typing import Dict, Any, List
from app.services.graph_service import build_nx_graph


def compute_learning_path(
    global_graph: Dict[str, Any],
    repo_data: Dict[str, Dict[str, Any]],
    violations: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Generate learning order and service details.
    - Remove violation edges for ordering.
    - Topological sort; break ties by service weight (incoming + outgoing edges).
    - Build service_details from repo_data + graph + violations.
    """
    G = build_nx_graph(global_graph, exclude_violation_edges=True)
    nodes = global_graph.get("nodes", [])
    edges = global_graph.get("edges", [])

    # Violations affecting a service: from or to this service
    def violations_for_service(service_id: str) -> List[Dict[str, Any]]:
        out = []
        for v in violations:
            if v.get("from") == service_id or v.get("to") == service_id:
                out.append(v)
            if "repos" in v and service_id in v["repos"]:
                out.append(v)
        return out

    # In/out degree (on graph without violation edges)
    in_deg = dict(G.in_degree())
    out_deg = dict(G.out_degree())
    weight = {n: in_deg.get(n, 0) + out_deg.get(n, 0) for n in G.nodes()}

    try:
        # Topological order; for multiple valid orders, prefer lower weight first (fewer deps first)
        topo = list(nx.topological_sort(G))
    except Exception:
        # Cycle present or graph changed: use node order by weight (foundation services first)
        topo = list(G.nodes())

    # Stable sort by weight ascending so "foundation" services come first when no strict order
    topo.sort(key=lambda n: (weight.get(n, 0), n))

    learning_order = topo

    # Build service_details for each node
    service_details = []
    for node_id in learning_order:
        node_data = next((n for n in nodes if n.get("id") == node_id), {})
        repo_info = repo_data.get(node_id, {})

        # Incoming/outgoing from full graph (including violation edges for display)
        incoming = [e["from"] for e in edges if e.get("to") == node_id]
        outgoing = [e["to"] for e in edges if e.get("from") == node_id]

        apis = [ep.get("path") or ep.get("method", "") + " " + ep.get("path", "") for ep in repo_info.get("api_endpoints", [])]
        if not apis and isinstance(repo_info.get("api_endpoints", []), list):
            apis = [str(ep) for ep in repo_info.get("api_endpoints", [])[:20]]

        service_details.append({
            "id": node_id,
            "name": node_id,
            "purpose": _derive_purpose(node_id, repo_info, node_data),
            "apis": apis[:30],
            "events_produced": repo_info.get("events_produced", []),
            "events_consumed": repo_info.get("events_consumed", []),
            "db_models": repo_info.get("db_models", []) or repo_info.get("database_access", []),
            "incoming_dependencies": list(dict.fromkeys(incoming)),
            "outgoing_dependencies": list(dict.fromkeys(outgoing)),
            "violations": violations_for_service(node_id),
            "documentation_link": repo_info.get("documentation_link") or "",
            "language": node_data.get("language", repo_info.get("language", "unknown")),
            "services": node_data.get("services", repo_info.get("services", [])),
        })

    return {
        "learning_order": learning_order,
        "service_details": service_details,
    }


def _derive_purpose(service_id: str, repo_info: Dict[str, Any], node_data: Dict[str, Any]) -> str:
    """Derive a short purpose from repo data or node."""
    if repo_info.get("purpose"):
        return repo_info["purpose"]
    services = node_data.get("services", []) or repo_info.get("services", [])
    if services:
        names = [s.get("name", s) if isinstance(s, dict) else s for s in services[:3]]
        return f"Provides: {', '.join(str(n) for n in names)}."
    return f"Microservice: {service_id}."
