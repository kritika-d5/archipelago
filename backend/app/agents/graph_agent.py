import networkx as nx
from typing import Dict, List, Any, Optional
import logging
from app.schemas.graph_schema import CodebaseGraph

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
        
        for element in codebase_graph.elements:
            self.graph.add_node(
                element.id,
                name=element.name,
                type=element.type.value,
                file_path=element.file_path,
                line_start=element.line_start,
                line_end=element.line_end,
                language=element.language.value,
                docstring=element.docstring,
                code_snippet=element.code_snippet
            )
        
        for module in codebase_graph.modules:
            self.graph.add_node(
                module.id,
                name=module.name,
                type="module",
                file_path=module.file_path,
                language=module.language.value,
                docstring=module.docstring
            )
        
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
        
        logger.info(f"Built graph with {self.graph.number_of_nodes()} nodes and {self.graph.number_of_edges()} edges")
        return self.graph
    
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
        
        if "agent" in name or "agent" in file_path:
            return "agent"
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
    
    def get_graph_for_visualization(self, codebase_graph: CodebaseGraph) -> Dict[str, Any]:
        graph = self.build_from_codebase_graph(codebase_graph)
        nodes = []
        edges = []
        
        for node_id, data in graph.nodes(data=True):
            category = self._categorize_node(data)
            nodes.append({
                "data": {
                    "id": node_id,
                    "label": data.get("name", node_id),
                    "type": data.get("type", "unknown"),
                    "category": category,
                    "file_path": data.get("file_path", ""),
                    "language": data.get("language", ""),
                    "docstring": data.get("docstring", "")[:200] if data.get("docstring") else "",
                }
            })
        
        for source, target, data in graph.edges(data=True):
            edges.append({
                "data": {
                    "id": f"{source}-{target}",
                    "source": source,
                    "target": target,
                    "dependency_type": data.get("dependency_type", data.get("relation", "unknown")),
                    "relation": data.get("relation", "unknown"),
                    "strength": data.get("strength", 1.0)
                }
            })
        
        return {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "repository_name": codebase_graph.metadata.repository_name
            }
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


GraphBuilder = KnowledgeGraphBuilder
