"""Diagnose why JS/TS import edges aren't resolving for a repo.

Shows the tsconfig/jsconfig aliases it loaded, how many import specifiers resolve to a module,
and samples of the local-looking ones that DON'T resolve (relative or aliased). That reveals
alias/baseUrl mismatches (e.g. code under src/ vs root).

Usage (from backend/, venv active):
    python scripts/js_diag.py C:\\path\\to\\cloned\\devtrack
"""
import sys
import posixpath
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.knowledge_graph.code_parser import CodeParser  # noqa: E402


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/js_diag.py <path>")
        sys.exit(1)
    path = Path(sys.argv[1])
    p = CodeParser()
    g = p.parse_repository(path, repo_url="local", branch="main")

    base_url, aliases = p._load_js_path_config(path)
    print(f"\n=== JS import diagnosis: {path} ===")
    print("baseUrl:", base_url)
    print("aliases:", aliases or "(none found in tsconfig/jsconfig)")

    # sample of the module file layout so we can see src/ vs root
    js_mods = [m for m in g.modules if m.metadata.get("js_imports") is not None
               or m.file_path.endswith((".js", ".jsx", ".ts", ".tsx"))]
    print(f"\nJS/TS modules: {len(js_mods)}  (sample paths)")
    for m in js_mods[:8]:
        print("  ", m.file_path.replace("\\", "/"))

    js_index = {p._strip_js_ext(m.file_path.replace("\\", "/")): m.id for m in g.modules}
    resolved = 0
    unresolved = []
    for m in g.modules:
        specs = m.metadata.get("js_imports") or []
        base_dir = posixpath.dirname(m.file_path.replace("\\", "/"))
        for spec in specs:
            tid = p._resolve_js_spec(spec, base_dir, js_index, base_url, aliases)
            if tid:
                resolved += 1
            elif spec.startswith(".") or spec.startswith("@") or spec.startswith("~"):
                unresolved.append((m.file_path.replace("\\", "/"), spec))

    print(f"\nresolved import edges: {resolved}")
    print(f"UNRESOLVED local-looking imports: {len(unresolved)} (sample below)")
    for fp, spec in unresolved[:30]:
        print(f"  {fp}\n     imports -> {spec}")


if __name__ == "__main__":
    main()
