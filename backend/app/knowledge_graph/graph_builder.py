"""
Graph Builder for Knowledge Graph
Converts parsed data into NetworkX graph structure.
"""
import networkx as nx
from typing import Dict, Any


class KnowledgeGraphBuilder:
    """
    Builds a knowledge graph from parsed code data.
    """
    
    def __init__(self):
        """Initialize the graph builder with an empty directed graph."""
        self.graph = nx.DiGraph()
    
    def build_graph(self, parsed_data: Dict[str, Any]) -> nx.DiGraph:
        """
        Build the knowledge graph from parsed data.
        
        Args:
            parsed_data: Dictionary containing services, schemas, endpoints, etc.
            
        Returns:
            NetworkX DiGraph representing the knowledge graph
        """
        # Clear existing graph
        self.graph.clear()
        
        # Add nodes and edges for different entity types
        self._add_services(parsed_data.get("services", {}))
        self._add_schemas(parsed_data.get("schemas", {}))
        self._add_endpoints(parsed_data.get("endpoints", []))
        self._add_fields(parsed_data.get("fields", {}))
        self._add_imports(parsed_data.get("imports", {}))
        
        # Add relationships
        self._add_service_schema_relations(parsed_data)
        self._add_endpoint_service_relations(parsed_data)
        self._add_schema_field_relations(parsed_data)
        
        return self.graph
    
    def _add_services(self, services: Dict[str, Any]):
        """Add service nodes to the graph."""
        for service_name, service_data in services.items():
            self.graph.add_node(
                service_name,
                type="Service",
                file_path=service_data.get("file_path", ""),
                methods=service_data.get("methods", []),
                line_number=service_data.get("line_number", 0)
            )
    
    def _add_schemas(self, schemas: Dict[str, Any]):
        """Add schema nodes to the graph."""
        for schema_name, schema_data in schemas.items():
            self.graph.add_node(
                schema_name,
                type="Schema",
                file_path=schema_data.get("file_path", ""),
                methods=schema_data.get("methods", []),
                line_number=schema_data.get("line_number", 0)
            )
    
    def _add_endpoints(self, endpoints: List[Dict[str, Any]]):
        """Add endpoint nodes to the graph."""
        for endpoint in endpoints:
            endpoint_name = endpoint.get("name", "")
            # Create unique identifier for endpoints
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
        """Add field nodes to the graph."""
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
        """Add import relationships to the graph."""
        for file_path, import_list in imports.items():
            for imp in import_list:
                # Extract module/class name from import
                import_name = imp.split(".")[-1]
                
                # Add import node if it doesn't exist
                if import_name not in self.graph:
                    self.graph.add_node(
                        import_name,
                        type="Import",
                        source_file=file_path
                    )
    
    def _add_service_schema_relations(self, parsed_data: Dict[str, Any]):
        """Add relationships between services and schemas."""
        services = parsed_data.get("services", {})
        schemas = parsed_data.get("schemas", {})
        
        # Check if services use schemas (by checking imports or method signatures)
        for service_name, service_data in services.items():
            service_file = service_data.get("file_path", "")
            imports = parsed_data.get("imports", {}).get(service_file, [])
            
            # Find schemas that might be used by this service
            for schema_name in schemas.keys():
                # Check if schema is imported or referenced
                if any(schema_name.lower() in imp.lower() for imp in imports):
                    self.graph.add_edge(
                        service_name,
                        schema_name,
                        relation="uses"
                    )
    
    def _add_endpoint_service_relations(self, parsed_data: Dict[str, Any]):
        """Add relationships between endpoints and services."""
        endpoints = parsed_data.get("endpoints", [])
        services = parsed_data.get("services", {})
        
        for endpoint in endpoints:
            endpoint_file = endpoint.get("file_path", "")
            endpoint_name = endpoint.get("name", "")
            endpoint_id = f"{endpoint_file}::{endpoint_name}"
            
            # Check endpoint parameters for service types
            for param in endpoint.get("parameters", []):
                param_type = param.get("type", "").lower()
                for service_name in services.keys():
                    if service_name.lower() in param_type:
                        self.graph.add_edge(
                            endpoint_id,
                            service_name,
                            relation="calls"
                        )
    
    def _add_schema_field_relations(self, parsed_data: Dict[str, Any]):
        """Add relationships between schemas and their fields."""
        fields = parsed_data.get("fields", {})
        
        for schema_name, schema_fields in fields.items():
            for field_name in schema_fields.keys():
                field_id = f"{schema_name}.{field_name}"
                if field_id in self.graph:
                    self.graph.add_edge(
                        schema_name,
                        field_id,
                        relation="contains"
                    )

