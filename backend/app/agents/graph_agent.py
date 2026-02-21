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
    
    def get_graph_for_visualization(self, codebase_graph: CodebaseGraph, filter_important_only: bool = False) -> Dict[str, Any]:
        graph = self.build_from_codebase_graph(codebase_graph)
        nodes = []
        edges = []
        
        # Track node degrees for layout (not filtering)
        node_degrees = {}
        for node_id in graph.nodes():
            node_degrees[node_id] = graph.degree(node_id)
        
        for node_id, data in graph.nodes(data=True):
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
        
        # Include all edges
        for source, target, data in graph.edges(data=True):
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
