"""
Flow service: detect 2-3 major flows (high outgoing degree, event emission, traverse downstream).
"""
import networkx as nx
from typing import Dict, Any, List, Set, Tuple
from app.services.graph_service import build_nx_graph


def _out_degree(G: nx.DiGraph, n: str) -> int:
    return G.out_degree(n)


def _has_event_out(G: nx.DiGraph, n: str) -> bool:
    for _, _, data in G.out_edges(n, data=True):
        if data.get("type") == "EVENT":
            return True
    return False


def _traverse_downstream_path(
    G: nx.DiGraph,
    start: str,
    max_length: int = 10,
    preferred: Set[str] = None,
) -> List[str]:
    """Traverse one downstream path from start; prefer REST/EVENT edges."""
    if preferred is None:
        preferred = {"REST", "EVENT"}
    path = [start]
    visited = {start}
    current = start
    while len(path) < max_length:
        out = list(G.out_edges(current, data=True))
        out.sort(
            key=lambda x: (
                0 if x[2].get("type") in preferred else 1,
                x[1],
            )
        )
        next_node = None
        for _, v, _ in out:
            if v not in visited:
                next_node = v
                break
        if next_node is None:
            break
        path.append(next_node)
        visited.add(next_node)
        current = next_node
    return path


def get_major_flows(
    global_graph: Dict[str, Any],
    max_flows: int = 3,
    min_path_length: int = 2,
) -> List[Dict[str, Any]]:
    """
    Identify 2-3 major flows. Algorithm:
    - Build graph excluding violation edges.
    - Consider nodes with high outgoing degree or event emission as flow starters.
    - Traverse downstream to get path, convert to readable flow.
    Returns list of { "path": ["auth-service", "order-service", ...], "path_ids": [...] }.
    """
    G = build_nx_graph(global_graph, exclude_violation_edges=True)
    if G.number_of_nodes() == 0:
        return []

    # Score nodes as flow starters: high out-degree + event producer
    candidates: List[Tuple[int, str]] = []
    for n in G.nodes():
        out_d = _out_degree(G, n)
        event_bonus = 5 if _has_event_out(G, n) else 0
        score = out_d + event_bonus
        if score > 0:
            candidates.append((score, n))

    candidates.sort(key=lambda x: (-x[0], x[1]))
    seen_paths: Set[tuple] = set()
    flows: List[Dict[str, Any]] = []

    for _, start in candidates[: max_flows * 2]:  # try more starters
        if len(flows) >= max_flows:
            break
        path = _traverse_downstream_path(G, start)
        if len(path) < min_path_length:
            continue
        path_tup = tuple(path)
        if path_tup in seen_paths:
            continue
        seen_paths.add(path_tup)
        flows.append({
            "path": path,
            "path_ids": path,
        })

    return flows[:max_flows]
