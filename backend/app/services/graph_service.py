"""
Graph service: build networkx graph from stored org data, compute longest path for flow highlight.
"""
import networkx as nx
from typing import Dict, Any, List, Optional, Set, Tuple

# Edge types we prefer for "main" flow (exclude violations)
PREFERRED_FLOW_TYPES = {"REST", "EVENT"}


def build_nx_graph(global_graph: Dict[str, Any], exclude_violation_edges: bool = True) -> nx.DiGraph:
    """
    Build a networkx DiGraph from global_graph (nodes + edges from MongoDB).
    If exclude_violation_edges, edges with violation=True or type DB_ACCESS are not added.
    """
    G = nx.DiGraph()
    nodes = global_graph.get("nodes", [])
    edges = global_graph.get("edges", [])

    for n in nodes:
        node_id = n.get("id")
        if node_id:
            G.add_node(
                node_id,
                type=n.get("type", "service"),
                language=n.get("language", "unknown"),
                services=n.get("services", []),
                endpoints=n.get("endpoints", 0),
            )

    for e in edges:
        from_id = e.get("from")
        to_id = e.get("to")
        if not from_id or not to_id:
            continue
        if exclude_violation_edges and (e.get("violation") or e.get("type") == "DB_ACCESS"):
            continue
        if not G.has_node(from_id) or not G.has_node(to_id):
            continue
        edge_type = e.get("type", "UNKNOWN")
        G.add_edge(
            from_id,
            to_id,
            type=edge_type,
            event_name=e.get("event_name", ""),
            endpoint=e.get("endpoint", ""),
            violation=e.get("violation", False),
        )

    return G


def longest_directed_path(
    G: nx.DiGraph,
    preferred_edge_types: Optional[Set[str]] = None,
) -> List[str]:
    """
    Find longest simple directed path. Prefer edges with type in preferred_edge_types
    (e.g. REST, EVENT) by using them first when building paths.
    Returns list of node ids in order.
    """
    if preferred_edge_types is None:
        preferred_edge_types = PREFERRED_FLOW_TYPES

    if G.number_of_nodes() == 0:
        return []
    if G.number_of_nodes() == 1:
        return list(G.nodes())

    best_path: List[str] = []

    def path_weight(path: List[str]) -> int:
        """Prefer paths that use preferred edge types; break ties by length."""
        score = len(path) * 1000
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            if G.has_edge(u, v):
                et = G.edges[u, v].get("type", "")
                if et in preferred_edge_types:
                    score += 10
        return score

    # Try each node as start (DAG longest path is tractable; general digraph we use simple DFS)
    for start in G.nodes():
        stack: List[Tuple[List[str], Set[str]]] = [([start], {start})]
        while stack:
            path, visited = stack.pop()
            if len(path) > len(best_path) or (
                len(path) == len(best_path) and path_weight(path) > path_weight(best_path)
            ):
                best_path = path[:]
            u = path[-1]
            # Prefer preferred edge types when expanding
            out_edges = list(G.out_edges(u, data=True))
            out_edges.sort(key=lambda x: (0 if x[2].get("type") in preferred_edge_types else 1, x[1]))
            for _, v, _ in out_edges:
                if v not in visited:
                    stack.append((path + [v], visited | {v}))

    return best_path


def get_main_flow_highlight(global_graph: Dict[str, Any]) -> List[str]:
    """
    Returns the main linear chain (longest directed path excluding violation edges,
    preferring REST + EVENT). Used to highlight the primary flow in the UI.
    """
    G = build_nx_graph(global_graph, exclude_violation_edges=True)
    return longest_directed_path(G, preferred_edge_types=PREFERRED_FLOW_TYPES)
