"""Local parser smoke-test — parse a folder and print node/edge stats.

No MongoDB, no network, no deploy: it runs the same CodeParser + graph builder the API uses,
so it's the fastest way to check whether a change produces edges without touching prod.

Usage (from the backend/ directory, with the venv active):
    python scripts/parse_local.py <path-to-a-local-repo-or-folder>
    python scripts/parse_local.py ../frontend/src
"""
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.knowledge_graph.code_parser import CodeParser  # noqa: E402
from app.agents.graph_agent import KnowledgeGraphBuilder  # noqa: E402


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/parse_local.py <path>")
        sys.exit(1)
    path = Path(sys.argv[1])
    if not path.exists():
        print(f"Path not found: {path}")
        sys.exit(1)

    graph = CodeParser().parse_repository(path, repo_url="local", branch="main")
    viz = KnowledgeGraphBuilder().get_graph_for_visualization(graph)

    print(f"\n=== {path} ===")
    print(f"modules={len(graph.modules)} elements={len(graph.elements)} "
          f"dependencies={len(graph.dependencies)}")
    print("dependency types:", dict(Counter(d.dependency_type.value for d in graph.dependencies)))
    print(f"visualization -> nodes={len(viz['nodes'])} edges={len(viz['edges'])}")

    node_categories = Counter(n["data"].get("category", "?") for n in viz["nodes"])
    print("node categories:", dict(node_categories))

    print("\nsample import edges:")
    for dep in [d for d in graph.dependencies if d.dependency_type.value == "import"][:8]:
        print(f"  {dep.source_id} -> {dep.target_id}")


if __name__ == "__main__":
    main()
