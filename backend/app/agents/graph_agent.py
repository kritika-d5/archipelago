import networkx as nx
from typing import Dict, List, Any, Optional
import logging
from app.schemas.graph_schema import CodebaseGraph, DependencyType, CodeElementType, SubgraphContext

logger = logging.getLogger(__name__)


class KnowledgeGraphBuilder:
    def __init__(self):
        self.graph = nx.DiGraph()
    
    def build_graph(self, parsed_data: Dict[str, Any]) -> nx.DiGraph:
        self.graph.clear()
        self._add_services(parsed_data.get("services", {}))
        self._add_schemas(parsed_data.get("schemas", {}))
        self._add_endpoints(parsed_data.get("endpoints", []))
        self._add_fields(parsed_data.get("fields", {}))
        self._add_imports(parsed_data.get("imports", {}))
        self._add_service_schema_relations(parsed_data)
        self._add_endpoint_service_relations(parsed_data)
        self._add_schema_field_relations(parsed_data)
        return self.graph
    
    def build_from_codebase_graph(self, codebase_graph: CodebaseGraph) -> nx.DiGraph:
        self.graph.clear()
        
        # Add all code elements
        for element in codebase_graph.elements:
            node_data = {
                "name": element.name,
                "type": element.type.value,
                "file_path": element.file_path,
                "line_start": element.line_start,
                "line_end": element.line_end,
                "language": element.language.value,
                "docstring": element.docstring,
                "code_snippet": element.code_snippet
            }
            # Add agent/workflow specific metadata
            if element.id in codebase_graph.agent_info:
                node_data["agent_info"] = codebase_graph.agent_info[element.id].dict()
            if element.id in codebase_graph.workflow_info:
                node_data["workflow_info"] = codebase_graph.workflow_info[element.id].dict()
            
            self.graph.add_node(element.id, **node_data)
        
        # Add modules
        for module in codebase_graph.modules:
            self.graph.add_node(
                module.id,
                name=module.name,
                type="module",
                file_path=module.file_path,
                language=module.language.value,
                docstring=module.docstring
            )
        
        # Add database schemas as nodes
        for db_schema in codebase_graph.database_schemas:
            schema_node_id = f"database_schema:{db_schema.name}"
            self.graph.add_node(
                schema_node_id,
                name=db_schema.name,
                type="database_schema",
                database_language=db_schema.database_language.value,
                orm_framework=db_schema.orm_framework,
                table_count=len(db_schema.tables)
            )
            
            # Add tables as nodes and link to schema
            for table in db_schema.tables:
                table_node_id = f"database_table:{db_schema.name}:{table.name}"
                self.graph.add_node(
                    table_node_id,
                    name=table.name,
                    type="database_table",
                    schema_name=db_schema.name,
                    column_count=len(table.columns)
                )
                self.graph.add_edge(
                    schema_node_id,
                    table_node_id,
                    relation="contains",
                    dependency_type="contains"
                )
        
        # Add dependencies
        for dep in codebase_graph.dependencies:
            if dep.source_id in self.graph and dep.target_id in self.graph:
                self.graph.add_edge(
                    dep.source_id,
                    dep.target_id,
                    relation=dep.dependency_type.value,
                    dependency_type=dep.dependency_type.value,
                    strength=dep.strength,
                    context=dep.context,
                    line_number=dep.line_number
                )
        
        # Add module-element relationships
        for module in codebase_graph.modules:
            for element_id in module.element_ids:
                if element_id in self.graph:
                    self.graph.add_edge(
                        module.id,
                        element_id,
                        relation="contains",
                        dependency_type="contains",
                        strength=1.0
                    )
        
        # Add agent-workflow relationships
        for workflow_id, workflow_info in codebase_graph.workflow_info.items():
            for agent_id in workflow_info.agents:
                if workflow_id in self.graph and agent_id in self.graph:
                    self.graph.add_edge(
                        workflow_id,
                        agent_id,
                        relation="uses_agent",
                        dependency_type=DependencyType.USES_AGENT.value
                    )
        
        # Add database relationships (detect queries in code)
        self._add_database_relationships(codebase_graph)
        
        logger.info(f"Built graph with {self.graph.number_of_nodes()} nodes and {self.graph.number_of_edges()} edges")
        return self.graph
    
    def _add_database_relationships(self, codebase_graph: CodebaseGraph):
        """Add relationships between code elements and database tables."""
        # Find elements that might query databases
        for element in codebase_graph.elements:
            if element.code_snippet:
                code_lower = element.code_snippet.lower()
                # Check for database operations
                if any(op in code_lower for op in ['select', 'insert', 'update', 'delete', 'query', 'save', 'get']):
                    # Try to match with database tables
                    for db_schema in codebase_graph.database_schemas:
                        for table in db_schema.tables:
                            table_node_id = f"database_table:{db_schema.name}:{table.name}"
                            if table.name.lower() in code_lower and table_node_id in self.graph:
                                # Determine operation type
                                if 'select' in code_lower or 'get' in code_lower or 'query' in code_lower:
                                    dep_type = DependencyType.READS_FROM_DATABASE.value
                                elif 'insert' in code_lower or 'save' in code_lower or 'create' in code_lower:
                                    dep_type = DependencyType.WRITES_TO_DATABASE.value
                                else:
                                    dep_type = DependencyType.QUERIES_DATABASE.value
                                
                                self.graph.add_edge(
                                    element.id,
                                    table_node_id,
                                    relation=dep_type,
                                    dependency_type=dep_type
                                )
    
    def _add_services(self, services: Dict[str, Any]):
        for service_name, service_data in services.items():
            self.graph.add_node(
                service_name,
                type="Service",
                file_path=service_data.get("file_path", ""),
                methods=service_data.get("methods", []),
                line_number=service_data.get("line_number", 0)
            )
    
    def _add_schemas(self, schemas: Dict[str, Any]):
        for schema_name, schema_data in schemas.items():
            self.graph.add_node(
                schema_name,
                type="Schema",
                file_path=schema_data.get("file_path", ""),
                methods=schema_data.get("methods", []),
                line_number=schema_data.get("line_number", 0)
            )
    
    def _add_endpoints(self, endpoints: List[Dict[str, Any]]):
        for endpoint in endpoints:
            endpoint_name = endpoint.get("name", "")
            endpoint_id = f"{endpoint.get('file_path', '')}::{endpoint_name}"
            self.graph.add_node(
                endpoint_id,
                type="Endpoint",
                name=endpoint_name,
                file_path=endpoint.get("file_path", ""),
                decorators=endpoint.get("decorators", []),
                parameters=endpoint.get("parameters", []),
                line_number=endpoint.get("line_number", 0)
            )
    
    def _add_fields(self, fields: Dict[str, Any]):
        for schema_name, schema_fields in fields.items():
            for field_name, field_data in schema_fields.items():
                field_id = f"{schema_name}.{field_name}"
                self.graph.add_node(
                    field_id,
                    type="Field",
                    field_type=field_data.get("type", "Any"),
                    parent_schema=schema_name
                )
    
    def _add_imports(self, imports: Dict[str, Any]):
        for file_path, import_list in imports.items():
            for imp in import_list:
                import_name = imp.split(".")[-1]
                if import_name not in self.graph:
                    self.graph.add_node(
                        import_name,
                        type="Import",
                        source_file=file_path
                    )
    
    def _add_service_schema_relations(self, parsed_data: Dict[str, Any]):
        services = parsed_data.get("services", {})
        schemas = parsed_data.get("schemas", {})
        for service_name, service_data in services.items():
            service_file = service_data.get("file_path", "")
            imports = parsed_data.get("imports", {}).get(service_file, [])
            for schema_name in schemas.keys():
                if any(schema_name.lower() in imp.lower() for imp in imports):
                    self.graph.add_edge(service_name, schema_name, relation="uses")
    
    def _add_endpoint_service_relations(self, parsed_data: Dict[str, Any]):
        endpoints = parsed_data.get("endpoints", [])
        services = parsed_data.get("services", {})
        for endpoint in endpoints:
            endpoint_file = endpoint.get("file_path", "")
            endpoint_name = endpoint.get("name", "")
            endpoint_id = f"{endpoint_file}::{endpoint_name}"
            for param in endpoint.get("parameters", []):
                param_type = param.get("type", "").lower()
                for service_name in services.keys():
                    if service_name.lower() in param_type:
                        self.graph.add_edge(endpoint_id, service_name, relation="calls")
    
    def _add_schema_field_relations(self, parsed_data: Dict[str, Any]):
        fields = parsed_data.get("fields", {})
        for schema_name, schema_fields in fields.items():
            for field_name in schema_fields.keys():
                field_id = f"{schema_name}.{field_name}"
                if field_id in self.graph:
                    self.graph.add_edge(schema_name, field_id, relation="contains")
    
    def _categorize_node(self, node_data: Dict[str, Any]) -> str:
        node_type = node_data.get("type", "unknown").lower()
        name = node_data.get("name", "").lower()
        file_path = node_data.get("file_path", "").lower()
        
        # Check explicit type first
        if node_type == "agent":
            return "agent"
        elif node_type == "workflow":
            return "workflow"
        elif node_type == "database_schema":
            return "database_schema"
        elif node_type == "database_table":
            return "database_table"
        elif node_type == "database_column":
            return "database_column"
        elif node_type == "api_endpoint":
            return "api"
        elif "agent" in name or "agent" in file_path or node_data.get("agent_info"):
            return "agent"
        elif "workflow" in name or "workflow" in file_path or node_data.get("workflow_info"):
            return "workflow"
        elif node_type == "class":
            return "class"
        elif node_type in ["function", "method"]:
            return "function"
        elif "dockerfile" in file_path or "docker-compose" in file_path:
            return "docker"
        elif "k8s" in file_path or "kubernetes" in file_path or file_path.endswith((".yaml", ".yml")) and ("deployment" in file_path or "service" in file_path):
            return "kubernetes"
        elif "api" in name or "endpoint" in name or "route" in name:
            return "api"
        elif node_type == "module":
            return "module"
        else:
            return node_type
    
    def get_graph_for_visualization(self, codebase_graph: CodebaseGraph,
                                    filter_important_only: bool = False,
                                    min_degree: int = 0) -> Dict[str, Any]:
        """Element-level "files" view: every module/class/function/method as a node.

        `min_degree` prunes low-connectivity nodes so the whole-repo view is usable:
        degree is counted from *dependency* edges only (containment nesting is ignored),
        so a class connected purely by "this module contains it" is treated as a leaf.
        `filter_important_only` is a convenience alias that applies a sensible default
        threshold when no explicit `min_degree` is given.
        """
        graph = self.build_from_codebase_graph(codebase_graph)
        nodes = []
        edges = []

        if filter_important_only and min_degree <= 0:
            min_degree = 2  # "hubs only" default

        # Dependency degree ignores structural "contains" edges — those are nesting, not
        # dependencies, and would keep every leaf element alive at min_degree >= 1.
        dep_degree = {n: 0 for n in graph.nodes()}
        for s, t, d in graph.edges(data=True):
            rel = d.get("dependency_type", d.get("relation", ""))
            if rel == "contains":
                continue
            dep_degree[s] = dep_degree.get(s, 0) + 1
            dep_degree[t] = dep_degree.get(t, 0) + 1

        keep_ids = {n for n in graph.nodes() if dep_degree.get(n, 0) >= min_degree} \
            if min_degree > 0 else set(graph.nodes())

        # Track node degrees for layout (not filtering)
        node_degrees = {}
        for node_id in graph.nodes():
            node_degrees[node_id] = graph.degree(node_id)

        for node_id, data in graph.nodes(data=True):
            if node_id not in keep_ids:
                continue
            category = self._categorize_node(data)

            node_info = {
                "data": {
                    "id": node_id,
                    "label": data.get("name", node_id),
                    "type": data.get("type", "unknown"),
                    "category": category,
                    "file_path": data.get("file_path", ""),
                    "language": data.get("language", ""),
                    "docstring": data.get("docstring", "")[:200] if data.get("docstring") else "",
                    "degree": node_degrees.get(node_id, 0),  # Add degree for layout
                }
            }
            
            # Add agent-specific info
            if category == "agent" and "agent_info" in data:
                agent_info = data["agent_info"]
                node_info["data"]["agent_type"] = agent_info.get("agent_type", "")
                node_info["data"]["llm_provider"] = agent_info.get("llm_provider", "")
                node_info["data"]["capabilities"] = agent_info.get("capabilities", [])
            
            # Add workflow-specific info
            if category == "workflow" and "workflow_info" in data:
                workflow_info = data["workflow_info"]
                node_info["data"]["workflow_type"] = workflow_info.get("workflow_type", "")
                node_info["data"]["steps"] = workflow_info.get("steps", [])
            
            # Add database-specific info
            if category == "database_schema":
                node_info["data"]["database_language"] = data.get("database_language", "")
                node_info["data"]["orm_framework"] = data.get("orm_framework", "")
                node_info["data"]["table_count"] = data.get("table_count", 0)
            
            if category == "database_table":
                node_info["data"]["schema_name"] = data.get("schema_name", "")
                node_info["data"]["column_count"] = data.get("column_count", 0)
            
            nodes.append(node_info)
        
        # Include edges between surviving nodes only
        for source, target, data in graph.edges(data=True):
            if source not in keep_ids or target not in keep_ids:
                continue
            edges.append({
                "data": {
                    "id": f"{source}-{target}",
                    "source": source,
                    "target": target,
                    "dependency_type": data.get("dependency_type", data.get("relation", "unknown")),
                    "relation": data.get("relation", data.get("dependency_type", "unknown")),
                    "strength": data.get("strength", 1.0)
                }
            })
        
        # Count entity types
        entity_counts = {}
        for node in nodes:
            category = node["data"].get("category", "unknown")
            entity_counts[category] = entity_counts.get(category, 0) + 1
        
        return {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "repository_name": codebase_graph.metadata.repository_name,
                "entity_counts": entity_counts,
                "database_languages": [lang.value for lang in codebase_graph.metadata.database_languages],
                "agents_count": entity_counts.get("agent", 0),
                "workflows_count": entity_counts.get("workflow", 0),
                "database_schemas_count": entity_counts.get("database_schema", 0),
                "database_tables_count": entity_counts.get("database_table", 0)
            }
        }
    
    def get_architecture_view(self, codebase_graph: CodebaseGraph, depth: int = 2) -> Dict[str, Any]:
        """Aggregate the file-level graph into a high-level architecture view: files/elements are
        grouped by folder (to `depth` path segments) into module nodes, and dependencies between
        groups become weighted edges. Turns a 100+ node file hairball into ~10-20 readable nodes."""
        graph = self.build_from_codebase_graph(codebase_graph)

        def group_of(data: Dict[str, Any]):
            fp = (data.get("file_path") or "").replace("\\", "/").strip("/")
            if not fp:
                return None
            dir_parts = fp.split("/")[:-1]  # drop filename
            if not dir_parts:
                return "(root)"
            return "/".join(dir_parts[:depth])

        # Adapt depth so we get a useful number of groups (avoid 1 giant node or 100 tiny ones)
        def group_count(d):
            seen = set()
            for _, data in graph.nodes(data=True):
                fp = (data.get("file_path") or "").replace("\\", "/").strip("/")
                parts = fp.split("/")[:-1]
                seen.add("/".join(parts[:d]) if parts else "(root)")
            return len(seen)
        for d in (depth, depth + 1, depth + 2, 1):
            if 4 <= group_count(d) <= 30:
                depth = d
                break

        groups: Dict[str, Dict[str, Any]] = {}
        node_group: Dict[str, str] = {}
        for nid, data in graph.nodes(data=True):
            g = group_of(data)
            if g is None:
                continue
            node_group[nid] = g
            info = groups.setdefault(g, {"files": set(), "elements": 0, "langs": set()})
            if data.get("type") == "module":
                info["files"].add(data.get("file_path", ""))
            else:
                info["elements"] += 1
            if data.get("language"):
                info["langs"].add(data.get("language"))

        edge_weights: Dict[tuple, int] = {}
        for s, t, edata in graph.edges(data=True):
            ga, gb = node_group.get(s), node_group.get(t)
            if not ga or not gb or ga == gb:
                continue
            rel = edata.get("dependency_type", edata.get("relation", ""))
            if rel == "contains":  # module->element containment isn't an architecture dependency
                continue
            edge_weights[(ga, gb)] = edge_weights.get((ga, gb), 0) + 1

        nodes = []
        for gid, info in groups.items():
            nodes.append({"data": {
                "id": gid,
                "label": gid.split("/")[-1] or gid,
                "type": "module",
                "category": "module",
                "file_count": len(info["files"]),
                "element_count": info["elements"],
                "language": next(iter(info["langs"]), "unknown"),
                "degree": 0,
            }})

        edges = []
        for (ga, gb), w in edge_weights.items():
            edges.append({"data": {
                "id": f"{ga}=>{gb}",
                "source": ga,
                "target": gb,
                "dependency_type": "import",
                "relation": "depends on",
                "weight": w,
            }})

        degree: Dict[str, int] = {}
        for e in edges:
            degree[e["data"]["source"]] = degree.get(e["data"]["source"], 0) + 1
            degree[e["data"]["target"]] = degree.get(e["data"]["target"], 0) + 1
        for n in nodes:
            n["data"]["degree"] = degree.get(n["data"]["id"], 0)

        return {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "repository_name": codebase_graph.metadata.repository_name,
                "graph_type": "architecture",
                "group_depth": depth,
            },
        }

    def get_module_dependency_view(self, codebase_graph: CodebaseGraph, min_degree: int = 1) -> Dict[str, Any]:
        """Module-to-module IMPORT graph — the "what depends on what" view.

        This is the readable middle tier between the folder-level architecture view and the
        full element-level files view: nodes are files (modules), edges are the imports between
        them, and nothing else. No containment nesting, no per-function calls. Modules whose
        dependency degree is below `min_degree` (default 1 = keep only connected files) are
        pruned so isolated leaves and pure external-import files drop out.
        """
        graph = self.build_from_codebase_graph(codebase_graph)

        # Collapse to module->module IMPORT edges, accumulating a weight per pair.
        dep_pairs: Dict[tuple, int] = {}
        for s, t, d in graph.edges(data=True):
            rel = d.get("dependency_type", d.get("relation", ""))
            if rel != "import" or s == t:
                continue
            if graph.nodes[s].get("type") != "module" or graph.nodes[t].get("type") != "module":
                continue
            dep_pairs[(s, t)] = dep_pairs.get((s, t), 0) + 1

        degree: Dict[str, int] = {}
        for (s, t) in dep_pairs:
            degree[s] = degree.get(s, 0) + 1
            degree[t] = degree.get(t, 0) + 1

        keep = {n for n in degree if degree[n] >= min_degree}

        nodes = []
        for nid in keep:
            data = graph.nodes[nid]
            nodes.append({"data": {
                "id": nid,
                "label": data.get("name", nid),
                "type": "module",
                "category": "module",
                "file_path": data.get("file_path", ""),
                "language": data.get("language", ""),
                "degree": degree.get(nid, 0),
            }})

        edges = []
        for (s, t), w in dep_pairs.items():
            if s in keep and t in keep:
                edges.append({"data": {
                    "id": f"{s}=>{t}",
                    "source": s,
                    "target": t,
                    "dependency_type": "import",
                    "relation": "imports",
                    "weight": w,
                }})

        return {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "repository_name": codebase_graph.metadata.repository_name,
                "graph_type": "modules",
                "min_degree": min_degree,
            },
        }

    def get_insights(self, codebase_graph: CodebaseGraph) -> Dict[str, Any]:
        """Compute real, single-repo knowledge-engineering insights from a parsed codebase:
        composition (languages / element types / dependency types), the most-connected and
        most-depended-upon modules, circular dependencies, isolated modules, entry points, and
        a set of plain-language observations. This is what makes the Architecture Hub useful for
        an individual repository (org graphs already carry their own REST/event statistics)."""
        def _val(x):
            return x.value if hasattr(x, "value") else str(x)

        CODE_LANGS = {"python", "javascript", "typescript", "java", "cpp", "go", "rust"}
        elements = codebase_graph.elements
        deps = codebase_graph.dependencies
        # Only real source files count as modules. Non-code files (.css/.html/.json/.md/config) are
        # parsed as modules too and would otherwise inflate the file count and the "isolated"
        # (dead-code) list.
        modules = [m for m in codebase_graph.modules if _val(m.language) in CODE_LANGS]
        module_ids = {m.id for m in modules}
        id_to_name = {m.id: m.name for m in modules}

        # Element type + language + dependency-type composition
        type_counts: Dict[str, int] = {}
        for e in elements:
            t = _val(e.type)
            type_counts[t] = type_counts.get(t, 0) + 1

        lang_counts: Dict[str, int] = {}
        for m in modules:
            lang = _val(m.language)
            if lang and lang != "unknown":
                lang_counts[lang] = lang_counts.get(lang, 0) + 1

        dep_counts: Dict[str, int] = {}
        for d in deps:
            dt = _val(d.dependency_type)
            if dt == "contains":
                continue
            dep_counts[dt] = dep_counts.get(dt, 0) + 1

        # Module-to-module import graph for connectivity / cycle analysis
        mod_graph = nx.DiGraph()
        for m in modules:
            mod_graph.add_node(m.id)
        for d in deps:
            if (d.dependency_type == DependencyType.IMPORT
                    and d.source_id in module_ids and d.target_id in module_ids
                    and d.source_id != d.target_id):
                mod_graph.add_edge(d.source_id, d.target_id)

        top_modules = []
        for nid, deg in sorted(mod_graph.degree, key=lambda x: x[1], reverse=True):
            if deg <= 0:
                continue
            top_modules.append({
                "name": id_to_name.get(nid, nid),
                "degree": deg,
                "fan_in": mod_graph.in_degree(nid),
                "fan_out": mod_graph.out_degree(nid),
            })
            if len(top_modules) >= 10:
                break

        core_modules = [
            {"name": id_to_name.get(nid, nid), "dependents": d}
            for nid, d in sorted(mod_graph.in_degree, key=lambda x: x[1], reverse=True)[:6]
            if d > 0
        ]

        try:
            cycles = [c for c in nx.simple_cycles(mod_graph) if len(c) > 1]
        except Exception:
            cycles = []
        circular = [[id_to_name.get(n, n) for n in cyc] for cyc in cycles[:12]]

        isolated = [id_to_name.get(nid, nid) for nid in mod_graph.nodes if mod_graph.degree(nid) == 0]
        max_fan_out = max((mod_graph.out_degree(n) for n in mod_graph.nodes), default=0)
        god_module = None
        if max_fan_out >= 6:
            god_module = next((id_to_name.get(n, n) for n in mod_graph.nodes
                               if mod_graph.out_degree(n) == max_fan_out), None)

        # Folder / layer breakdown
        folder_counts: Dict[str, int] = {}
        for m in modules:
            parts = (m.file_path or "").replace("\\", "/").strip("/").split("/")
            folder = parts[0] if len(parts) > 1 else "(root)"
            folder_counts[folder] = folder_counts.get(folder, 0) + 1
        folders = sorted(
            [{"name": k, "files": v} for k, v in folder_counts.items()],
            key=lambda x: x["files"], reverse=True
        )[:8]

        # Real entry points: source files whose stem is a conventional entry name. (The stored
        # metadata.main_entry_points uses a loose substring match that catches App.css, index.html,
        # and any file containing "index" — so we recompute here from code files only.)
        entry_stems = {"main", "__main__", "index", "app", "server", "cli", "manage", "wsgi", "asgi", "run"}
        entry_points = [m.file_path for m in modules if (m.name or "").lower() in entry_stems][:8]
        db_langs = [_val(l) for l in (codebase_graph.metadata.database_languages or [])]

        functions = type_counts.get("function", 0) + type_counts.get("method", 0)
        classes = type_counts.get("class", 0)
        agents = type_counts.get("agent", 0)
        workflows = type_counts.get("workflow", 0)
        db_tables = type_counts.get("database_table", 0)

        # Plain-language observations
        insights: List[str] = []
        if circular:
            insights.append(f"{len(circular)} circular import chain(s) detected — breaking these improves testability and build times.")
        if god_module:
            insights.append(f"`{god_module}` imports {max_fan_out} other modules — a potential 'god module'; consider splitting its responsibilities.")
        if core_modules:
            top = core_modules[0]
            insights.append(f"`{top['name']}` is the most depended-upon module ({top['dependents']} dependents) — changes here have the widest blast radius.")
        if len(isolated) > 0:
            insights.append(f"{len(isolated)} source file(s) have no resolved internal imports — usually entry points or leaf modules (some cross-file imports may not resolve).")
        if agents:
            insights.append(f"{agents} AI agent(s) detected — this looks like an LLM/agentic codebase.")
        if db_tables:
            insights.append(f"{db_tables} database model(s) found" + (f" ({', '.join(db_langs)})." if db_langs else "."))
        if len(lang_counts) > 1:
            insights.append(f"Polyglot codebase spanning {len(lang_counts)} languages: {', '.join(lang_counts.keys())}.")
        if not insights:
            insights.append("No structural issues detected — the dependency graph is clean.")

        return {
            "metrics": {
                "files": len(modules),
                "elements": len(elements),
                "classes": classes,
                "functions": functions,
                "agents": agents,
                "workflows": workflows,
                "db_tables": db_tables,
                "languages": len(lang_counts),
                "circular_deps": len(circular),
                "isolated": len(isolated),
                "max_fan_out": max_fan_out,
                "entry_points": len(entry_points),
                "internal_imports": mod_graph.number_of_edges(),
            },
            "language_breakdown": [{"name": k, "value": v} for k, v in sorted(lang_counts.items(), key=lambda x: -x[1])],
            "dependency_breakdown": [{"name": k, "value": v} for k, v in sorted(dep_counts.items(), key=lambda x: -x[1])],
            "element_breakdown": [{"name": k, "value": v} for k, v in sorted(type_counts.items(), key=lambda x: -x[1])],
            "top_modules": top_modules,
            "core_modules": core_modules,
            "circular_dependencies": circular,
            "isolated_modules": isolated[:12],
            "entry_points": entry_points,
            "folders": folders,
            "insights": insights,
            "repository_name": codebase_graph.metadata.repository_name,
        }

    def get_subgraph(self, codebase_graph: CodebaseGraph, element_ids: List[str], depth: int = 2) -> Dict[str, Any]:
        graph = self.build_from_codebase_graph(codebase_graph)
        subgraph_nodes = set(element_ids)
        for _ in range(depth):
            new_nodes = set()
            for node_id in subgraph_nodes:
                new_nodes.update(graph.predecessors(node_id))
                new_nodes.update(graph.successors(node_id))
            subgraph_nodes.update(new_nodes)
        
        subgraph = graph.subgraph(subgraph_nodes)
        nodes = []
        edges = []
        
        for node_id, data in subgraph.nodes(data=True):
            nodes.append({
                "data": {
                    "id": node_id,
                    "label": data.get("name", node_id),
                    "type": data.get("type", "unknown"),
                    "file_path": data.get("file_path", ""),
                    "language": data.get("language", ""),
                }
            })
        
        for source, target, data in subgraph.edges(data=True):
            edges.append({
                "data": {
                    "id": f"{source}-{target}",
                    "source": source,
                    "target": target,
                    "dependency_type": data.get("dependency_type", data.get("relation", "unknown")),
                }
            })
        
        return {"nodes": nodes, "edges": edges}
    
    def find_impact_chain(self, codebase_graph: CodebaseGraph, element_id: str, max_depth: int = 5) -> List[Dict[str, Any]]:
        graph = self.build_from_codebase_graph(codebase_graph)
        impact_chain = []
        
        def traverse_dependents(node_id: str, depth: int, path: List[str]):
            if depth > max_depth or node_id in path:
                return
            dependents = list(graph.successors(node_id))
            for dependent_id in dependents:
                edge_data = graph.get_edge_data(node_id, dependent_id)
                impact_chain.append({
                    "source": node_id,
                    "target": dependent_id,
                    "depth": depth,
                    "dependency_type": edge_data.get("dependency_type", edge_data.get("relation", "unknown")),
                    "strength": edge_data.get("strength", 1.0)
                })
                traverse_dependents(dependent_id, depth + 1, path + [node_id])
        
        traverse_dependents(element_id, 0, [])
        return impact_chain
    
    def extract_subgraph_context(self, codebase_graph: CodebaseGraph, element_id: str, 
                                 max_depth: int = 3) -> SubgraphContext:
        """
        Extract structured subgraph context for a given element.
        This is the main method for "What happens if I modify X?" queries.
        """
        graph = self.build_from_codebase_graph(codebase_graph)
        
        # Find target element
        target_element = codebase_graph.get_element_by_id(element_id)
        if not target_element:
            # Try to find by name
            for elem in codebase_graph.elements:
                if elem.name == element_id or element_id in elem.name:
                    target_element = elem
                    element_id = elem.id
                    break
        
        if not target_element:
            return SubgraphContext(target_element_id=element_id)
        
        # Collect all related nodes
        visited = set()
        direct_dependents = []
        transitive_dependents = []
        incoming_dependencies = []
        outgoing_dependencies = []
        affected_apis = []
        database_tables = []
        database_operations = []
        agents_involved = []
        workflows_involved = []
        related_files = {target_element.file_path}
        
        # Traverse outgoing dependencies (what this element depends on)
        def traverse_outgoing(node_id: str, depth: int):
            if depth > max_depth or node_id in visited:
                return
            visited.add(node_id)
            predecessors = list(graph.predecessors(node_id))
            for pred_id in predecessors:
                if pred_id not in visited:
                    if depth == 0:
                        direct_dependents.append(pred_id)
                    else:
                        transitive_dependents.append(pred_id)
                    traverse_outgoing(pred_id, depth + 1)
        
        # Traverse incoming dependencies (what depends on this element)
        def traverse_incoming(node_id: str, depth: int):
            if depth > max_depth or node_id in visited:
                return
            visited.add(node_id)
            successors = list(graph.successors(node_id))
            for succ_id in successors:
                if succ_id not in visited:
                    if depth == 0:
                        incoming_dependencies.append(succ_id)
                    else:
                        transitive_dependents.append(succ_id)
                    
                    # Check node type
                    node_data = graph.nodes.get(succ_id, {})
                    node_type = node_data.get("type", "")
                    
                    # Check if it's an API endpoint
                    if node_type == "api_endpoint" or "endpoint" in node_type.lower():
                        affected_apis.append(succ_id)
                    
                    # Check if it's an agent
                    if node_type == "agent" or element_id in codebase_graph.agent_info:
                        agents_involved.append(succ_id)
                    
                    # Check if it's a workflow
                    if node_type == "workflow" or element_id in codebase_graph.workflow_info:
                        workflows_involved.append(succ_id)
                    
                    # Check database relationships
                    edge_data = graph.get_edge_data(node_id, succ_id)
                    if edge_data:
                        dep_type = edge_data.get("dependency_type", "")
                        if "database" in dep_type.lower():
                            database_tables.append(succ_id)
                            if "read" in dep_type.lower():
                                database_operations.append("read")
                            elif "write" in dep_type.lower():
                                database_operations.append("write")
                            else:
                                database_operations.append("query")
                    
                    # Track related files
                    file_path = node_data.get("file_path", "")
                    if file_path:
                        related_files.add(file_path)
                    
                    traverse_incoming(succ_id, depth + 1)
        
        traverse_outgoing(element_id, 0)
        visited.clear()
        traverse_incoming(element_id, 0)
        
        # Remove duplicates
        direct_dependents = list(set(direct_dependents))
        transitive_dependents = list(set(transitive_dependents))
        incoming_dependencies = list(set(incoming_dependencies))
        outgoing_dependencies = list(set(outgoing_dependencies))
        affected_apis = list(set(affected_apis))
        database_tables = list(set(database_tables))
        database_operations = list(set(database_operations))
        agents_involved = list(set(agents_involved))
        workflows_involved = list(set(workflows_involved))
        
        # Build impact summary
        impact_summary = f"Modifying {target_element.name} affects:\n"
        if direct_dependents:
            impact_summary += f"- {len(direct_dependents)} direct dependents\n"
        if transitive_dependents:
            impact_summary += f"- {len(transitive_dependents)} transitive dependents\n"
        if affected_apis:
            impact_summary += f"- {len(affected_apis)} API endpoints\n"
        if database_tables:
            impact_summary += f"- {len(database_tables)} database tables\n"
        if agents_involved:
            impact_summary += f"- {len(agents_involved)} agents\n"
        if workflows_involved:
            impact_summary += f"- {len(workflows_involved)} workflows\n"
        
        return SubgraphContext(
            target_service=target_element.name,
            target_element_id=element_id,
            direct_dependents=direct_dependents,
            transitive_dependents=transitive_dependents,
            incoming_dependencies=incoming_dependencies,
            outgoing_dependencies=outgoing_dependencies,
            affected_apis=affected_apis,
            database_tables=database_tables,
            database_operations=database_operations,
            agents_involved=agents_involved,
            workflows_involved=workflows_involved,
            related_files=list(related_files),
            impact_summary=impact_summary
        )


GraphBuilder = KnowledgeGraphBuilder
