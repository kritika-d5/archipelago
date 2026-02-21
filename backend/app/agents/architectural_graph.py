"""
AI Architectural Reasoning Engine
Transforms noisy codebase graphs into clean, meaningful architectural representations.
"""
import networkx as nx
from typing import Dict, List, Any, Optional, Set, Tuple
import logging
from collections import defaultdict
from app.schemas.graph_schema import CodebaseGraph, CodeElement, CodeElementType, DependencyType

logger = logging.getLogger(__name__)

# ALLOWED NODE TYPES - Architectural focus but inclusive
ALLOWED_NODE_TYPES = {
    "model",           # Business models
    "database_table",  # Database tables
    "api_endpoint",    # API endpoints
    "service",         # Business services
    "module",          # Top-level modules
    "class",           # Important classes
    "function",        # Key functions
    "method"           # Important methods
}

# FRAMEWORK NOISE PATTERNS - Explicitly exclude (but allow viewsets as they map to endpoints)
EXCLUDED_PATTERNS = {
    "migration", "config", "package.json", "vite", 
    "helper", "generated", "static", "asset", "test_", "__pycache__",
    "__init__", "setup.py", "requirements.txt"
}

# LAYER MAPPINGS
ARCHITECTURAL_LAYERS = {
    "business": {"model", "service", "class", "function", "method"},
    "api": {"api_endpoint"},
    "database": {"database_table", "database_schema"}
}


class ArchitecturalGraphBuilder:
    """
    Builds clean architectural graphs focusing on meaningful business logic.
    """
    
    def __init__(self):
        self.graph = nx.DiGraph()
        self.node_mappings = {}  # Framework → Core mappings
        self.impact_scores = {}
        self.critical_paths = []
    
    def build_architectural_graph(self, codebase_graph: CodebaseGraph, 
                                  demo_mode: bool = False,
                                  max_nodes: int = 50) -> Dict[str, Any]:
        """
        Build a clean architectural graph with strict filtering.
        
        Args:
            codebase_graph: Full codebase graph
            demo_mode: If True, show only top models and workflows
            max_nodes: Maximum nodes to include
            
        Returns:
            Clean architectural graph with metadata
        """
        self.graph.clear()
        self.node_mappings.clear()
        
        # Step 1: Filter and categorize nodes
        architectural_nodes = self._extract_architectural_nodes(codebase_graph)
        
        # Step 2: Collapse framework noise
        architectural_nodes = self._collapse_framework_noise(architectural_nodes, codebase_graph)
        
        # Step 3: Build clean graph - include all architectural nodes
        for node_id, node_data in architectural_nodes.items():
            # Include if it's an allowed type OR if it's a class/function
            node_type = node_data.get("type", "unknown")
            if node_type in ALLOWED_NODE_TYPES or node_type in ["class", "function", "method"]:
                self.graph.add_node(node_id, **node_data)
        
        # Step 4: Add meaningful edges only
        self._add_architectural_edges(codebase_graph, architectural_nodes)
        
        # Step 5: Calculate impact scores
        self._calculate_impact_scores(codebase_graph)
        
        # Step 6: Detect critical paths
        self._detect_critical_paths()
        
        # Step 7: Apply demo mode or node limit
        if demo_mode:
            self._apply_demo_mode()
        elif len(self.graph.nodes()) > max_nodes:
            self._apply_node_limit(max_nodes)
        
        # Step 8: Build visualization data
        return self._build_visualization_data(codebase_graph)
    
    def _extract_architectural_nodes(self, codebase_graph: CodebaseGraph) -> Dict[str, Dict]:
        """Extract architectural nodes - be more inclusive."""
        nodes = {}
        
        for element in codebase_graph.elements:
            node_type = self._classify_node_type(element)
            
            # Include if it's an allowed type OR if it's a class/function that might be important
            if node_type in ALLOWED_NODE_TYPES:
                # Check if it's excluded by pattern (but be less strict)
                if not self._is_excluded(element):
                    nodes[element.id] = {
                        "name": element.name,
                        "type": node_type,
                        "original_type": element.type.value,
                        "file_path": element.file_path,
                        "layer": self._get_layer(node_type),
                        "docstring": element.docstring,
                        "code_snippet": element.code_snippet
                    }
            # Also include classes that might be models but weren't classified
            elif element.type == CodeElementType.CLASS and not self._is_excluded(element):
                # Check if it looks like a model (capitalized name, not a serializer/admin)
                if element.name[0].isupper() and "serializer" not in element.name.lower():
                    nodes[element.id] = {
                        "name": element.name,
                        "type": "class",
                        "original_type": element.type.value,
                        "file_path": element.file_path,
                        "layer": "business",
                        "docstring": element.docstring,
                        "code_snippet": element.code_snippet
                    }
        
        # Add database tables
        for schema in codebase_graph.database_schemas:
            schema_id = f"schema:{schema.name}"
            nodes[schema_id] = {
                "name": schema.name,
                "type": "database_schema",
                "layer": "database",
                "database_language": schema.database_language.value,
                "orm_framework": schema.orm_framework,
                "table_count": len(schema.tables)
            }
            
            for table in schema.tables:
                table_id = f"table:{schema.name}:{table.name}"
                nodes[table_id] = {
                    "name": table.name,
                    "type": "database_table",
                    "layer": "database",
                    "schema_name": schema.name,
                    "columns": [col.name for col in table.columns],
                    "primary_keys": table.primary_keys,
                    "foreign_keys": list(table.foreign_keys.keys())
                }
        
        return nodes
    
    def _classify_node_type(self, element: CodeElement) -> str:
        """Classify element into architectural type."""
        name_lower = element.name.lower()
        file_path_lower = element.file_path.lower()
        type_lower = element.type.value.lower()
        
        # Check for explicit types
        if type_lower == "database_table":
            return "database_table"
        
        # Exclude only truly noisy patterns
        if any(pattern in name_lower for pattern in ["__pycache__", "test_", "migration"]):
            return "unknown"
        
        # Check for models (Django, SQLAlchemy patterns)
        if any(pattern in name_lower for pattern in ["model", "entity"]):
            # But exclude serializers
            if "serializer" not in name_lower:
                return "model"
        
        # Check if it's a schema (Pydantic, etc.) but not a serializer
        if "schema" in name_lower and "serializer" not in name_lower:
            # Check if it's actually a model by looking at base classes
            if element.code_snippet:
                code_lower = element.code_snippet.lower()
                if any(base in code_lower for base in ["basemodel", "models.model", "db.model"]):
                    return "model"
        
        # Check for services
        if any(pattern in name_lower for pattern in ["service", "manager", "handler", "controller"]):
            if "viewset" not in name_lower and "serializer" not in name_lower:
                return "service"
        
        # Check for API endpoints - look in file path and decorators
        if any(pattern in file_path_lower for pattern in ["api", "endpoint", "route", "view"]):
            if "serializer" not in name_lower and "admin" not in name_lower:
                # Check for route decorators
                if element.code_snippet:
                    code_lower = element.code_snippet.lower()
                    if any(decorator in code_lower for decorator in ["@router", "@app.route", "@api_view", "@action", "@get", "@post", "@put", "@delete"]):
                        return "api_endpoint"
        
        # Check for viewsets (Django REST) - map to endpoints
        if "viewset" in name_lower and "serializer" not in name_lower:
            return "api_endpoint"
        
        # Check for classes that might be models
        if element.type == CodeElementType.CLASS:
            # Check if it inherits from common model bases
            if element.code_snippet:
                code_lower = element.code_snippet.lower()
                if any(base in code_lower for base in ["models.model", "db.model", "basemodel", "declarative_base"]):
                    return "model"
            # Otherwise it's a regular class
            if "serializer" not in name_lower and "admin" not in name_lower:
                return "class"
        
        # Check for functions/methods
        if element.type == CodeElementType.FUNCTION:
            return "function"
        if element.type == CodeElementType.METHOD:
            return "method"
        
        # Default: check if it's a module
        if element.type == CodeElementType.MODULE:
            return "module"
        
        return "unknown"
    
    def _is_excluded(self, element: CodeElement) -> bool:
        """Check if element should be excluded - be less strict."""
        name_lower = element.name.lower()
        file_path_lower = element.file_path.lower()
        
        # Only exclude if it's clearly noise
        for pattern in EXCLUDED_PATTERNS:
            # Be more specific - only exclude if pattern is a significant part of the name/path
            if pattern in name_lower:
                # Don't exclude if it's just part of a larger word
                if f"_{pattern}_" in name_lower or name_lower.startswith(pattern + "_") or name_lower.endswith("_" + pattern):
                    return True
            if pattern in file_path_lower:
                # Exclude config files, migrations, etc. in file paths
                if f"/{pattern}" in file_path_lower or f"\\{pattern}" in file_path_lower:
                    return True
        
        # Explicitly exclude serializers and admin classes
        if "serializer" in name_lower and name_lower.endswith("serializer"):
            return True
        if "admin" in name_lower and ("admin" in name_lower.split("_") or name_lower.startswith("admin")):
            return True
        
        return False
    
    def _is_allowed_node(self, node_data: Dict) -> bool:
        """Check if node is in allowed types - expanded to include classes."""
        node_type = node_data.get("type")
        return node_type in ALLOWED_NODE_TYPES or node_type in ["class", "function", "method"]
    
    def _get_layer(self, node_type: str) -> str:
        """Get architectural layer for node type."""
        for layer, types in ARCHITECTURAL_LAYERS.items():
            if node_type in types:
                return layer
        return "unknown"
    
    def _collapse_framework_noise(self, nodes: Dict[str, Dict], 
                                  codebase_graph: CodebaseGraph) -> Dict[str, Dict]:
        """Map framework artifacts to core entities - but keep more nodes."""
        collapsed = {}
        mappings = {}
        
        for node_id, node_data in nodes.items():
            name = node_data["name"]
            node_type = node_data["type"]
            
            # Map serializers to models (but keep the serializer node too for now)
            if "serializer" in name.lower() and name.lower().endswith("serializer"):
                # Try to find underlying model
                model_name = name.replace("Serializer", "").replace("serializer", "")
                # Find matching model node
                for other_id, other_data in nodes.items():
                    if other_data["name"] == model_name and other_data["type"] in ["model", "class"]:
                        mappings[node_id] = other_id
                        # Don't continue - keep serializer as class type
                        node_data["type"] = "class"
                        node_data["mapped_to"] = other_id
                        break
            
            # Map viewsets to API endpoints (but also keep viewset as class)
            if "viewset" in name.lower() and name.lower().endswith("viewset"):
                # Create API endpoint representation
                api_name = name.replace("ViewSet", "").replace("viewset", "")
                api_id = f"api:{api_name.lower()}"
                if api_id not in collapsed:
                    collapsed[api_id] = {
                        "name": f"/{api_name.lower()}/",
                        "type": "api_endpoint",
                        "layer": "api",
                        "original_viewset": name
                    }
                mappings[node_id] = api_id
                # Also keep viewset as class
                node_data["type"] = "class"
                node_data["mapped_to"] = api_id
            
            # Keep all other nodes
            collapsed[node_id] = node_data
        
        self.node_mappings = mappings
        return collapsed
    
    def _add_architectural_edges(self, codebase_graph: CodebaseGraph, 
                                nodes: Dict[str, Dict]):
        """Add only meaningful architectural edges."""
        # Map dependencies through framework mappings
        for dep in codebase_graph.dependencies:
            source_id = dep.source_id
            target_id = dep.target_id
            
            # Apply mappings
            source_id = self.node_mappings.get(source_id, source_id)
            target_id = self.node_mappings.get(target_id, target_id)
            
            # Only add if both nodes exist and are meaningful
            if source_id in self.graph and target_id in self.graph:
                # Skip only very low-value edges
                if dep.dependency_type in [DependencyType.IMPORT, DependencyType.REFERENCE]:
                    if dep.strength < 0.3:  # Lower threshold to include more edges
                        continue
                
                self.graph.add_edge(
                    source_id,
                    target_id,
                    relation=dep.dependency_type.value,
                    strength=dep.strength,
                    context=dep.context
                )
        
        # Add explicit architectural relationships
        self._add_model_to_table_edges(nodes)
        self._add_api_to_model_edges(nodes)
        self._add_service_to_model_edges(nodes)
    
    def _add_model_to_table_edges(self, nodes: Dict[str, Dict]):
        """Connect models to their database tables."""
        for node_id, node_data in nodes.items():
            if node_data["type"] == "model" and node_id in self.graph:
                model_name = node_data["name"]
                # Find matching table (exact match or table name matches model)
                for table_id, table_data in nodes.items():
                    if table_data["type"] == "database_table" and table_id in self.graph:
                        table_name = table_data["name"]
                        # Match if names are similar (case-insensitive)
                        if (table_name.lower() == model_name.lower() or 
                            table_name.lower().replace("_", "") == model_name.lower().replace("_", "")):
                            self.graph.add_edge(
                                node_id,
                                table_id,
                                relation="maps_to",
                                strength=1.0
                            )
                            break
    
    def _add_api_to_model_edges(self, nodes: Dict[str, Dict]):
        """Connect API endpoints to models they use."""
        for node_id, node_data in nodes.items():
            if node_data["type"] == "api_endpoint" and node_id in self.graph:
                # Find models mentioned in API name or path
                api_name = node_data["name"].lower()
                for model_id, model_data in nodes.items():
                    if model_data["type"] == "model" and model_id in self.graph:
                        model_name = model_data["name"].lower()
                        if model_name in api_name or api_name.replace("/", "").replace("api", "") == model_name:
                            self.graph.add_edge(
                                node_id,
                                model_id,
                                relation="uses",
                                strength=0.8
                            )
    
    def _add_service_to_model_edges(self, nodes: Dict[str, Dict]):
        """Connect services to models they operate on."""
        for node_id, node_data in nodes.items():
            if node_data["type"] == "service" and node_id in self.graph:
                service_name = node_data["name"].lower()
                # Find models with similar names
                for model_id, model_data in nodes.items():
                    if model_data["type"] == "model" and model_id in self.graph:
                        model_name = model_data["name"].lower()
                        # Check if service operates on this model
                        if model_name in service_name or service_name.replace("service", "") == model_name:
                            self.graph.add_edge(
                                node_id,
                                model_id,
                                relation="operates_on",
                                strength=0.9
                            )
    
    def _calculate_impact_scores(self, codebase_graph: CodebaseGraph):
        """Calculate weighted impact scores for each node."""
        # First pass: calculate raw scores
        raw_scores = {}
        for node_id in self.graph.nodes():
            score = 0.0
            node_data = self.graph.nodes[node_id]
            node_type = node_data.get("type")
            
            # Count foreign key references (weight: 2)
            if node_type == "database_table":
                fk_count = len(node_data.get("foreign_keys", []))
                score += fk_count * 2
            elif node_type == "model":
                # Count how many tables reference this model (FK relationships)
                fk_refs = sum(1 for nid, ndata in self.graph.nodes(data=True)
                            if ndata.get("type") == "database_table" and 
                            node_data.get("name", "").lower() in [fk.lower() for fk in ndata.get("foreign_keys", [])])
                score += fk_refs * 2
            
            # Count API usage (weight: 3)
            api_edges = [e for e in self.graph.in_edges(node_id) 
                        if self.graph.nodes[e[0]].get("type") == "api_endpoint"]
            score += len(api_edges) * 3
            
            # Count service usage (weight: 3)
            service_edges = [e for e in self.graph.in_edges(node_id)
                            if self.graph.nodes[e[0]].get("type") == "service"]
            score += len(service_edges) * 3
            
            # Count outgoing edges to important nodes (weight: 1)
            important_outgoing = sum(1 for e in self.graph.out_edges(node_id)
                                   if self.graph.nodes[e[1]].get("type") in ["model", "service", "api_endpoint"])
            score += important_outgoing * 1
            
            raw_scores[node_id] = score
        
        # Normalize to 10 (use max score as reference)
        if raw_scores:
            max_score = max(raw_scores.values())
            if max_score > 0:
                for node_id, score in raw_scores.items():
                    self.impact_scores[node_id] = min(10.0, (score / max_score) * 10)
            else:
                for node_id in raw_scores:
                    self.impact_scores[node_id] = 0.0
        else:
            for node_id in self.graph.nodes():
                self.impact_scores[node_id] = 0.0
    
    def _detect_critical_paths(self):
        """Detect critical workflow chains."""
        # Find high-impact nodes
        high_impact = [nid for nid, score in self.impact_scores.items() if score > 7.0]
        
        # Find paths between high-impact nodes
        paths = []
        for i, source in enumerate(high_impact):
            for target in high_impact[i+1:]:
                try:
                    if nx.has_path(self.graph, source, target):
                        path = nx.shortest_path(self.graph, source, target)
                        if len(path) > 1:
                            paths.append({
                                "source": self.graph.nodes[source]["name"],
                                "target": self.graph.nodes[target]["name"],
                                "path": [self.graph.nodes[n]["name"] for n in path],
                                "length": len(path)
                            })
                except:
                    pass
        
        self.critical_paths = paths[:5]  # Top 5 paths
    
    def _apply_demo_mode(self):
        """Apply demo mode: show only top models and workflows."""
        # Get top 10 nodes by impact score
        top_nodes = sorted(self.impact_scores.items(), key=lambda x: x[1], reverse=True)[:10]
        top_node_ids = {nid for nid, _ in top_nodes}
        
        # Keep only top nodes and their immediate neighbors
        nodes_to_keep = set(top_node_ids)
        for node_id in top_node_ids:
            nodes_to_keep.update(self.graph.predecessors(node_id))
            nodes_to_keep.update(self.graph.successors(node_id))
        
        # Create subgraph
        self.graph = self.graph.subgraph(nodes_to_keep).copy()
    
    def _apply_node_limit(self, max_nodes: int):
        """Limit graph to top N nodes by impact - but be more inclusive."""
        if len(self.graph.nodes()) <= max_nodes:
            return
        
        # Get top nodes by impact (take more than max to have buffer)
        top_nodes = sorted(self.impact_scores.items(), key=lambda x: x[1], reverse=True)[:max_nodes * 2]
        top_node_ids = {nid for nid, _ in top_nodes}
        
        # Keep top nodes and their immediate connections (more neighbors)
        nodes_to_keep = set(top_node_ids)
        for node_id in top_node_ids:
            # Add more immediate neighbors
            nodes_to_keep.update(list(self.graph.predecessors(node_id))[:3])
            nodes_to_keep.update(list(self.graph.successors(node_id))[:3])
        
        # If still over limit, prioritize but keep more
        if len(nodes_to_keep) > max_nodes:
            # Prioritize by impact score, but keep top 80% of max_nodes
            prioritized = sorted(nodes_to_keep, 
                               key=lambda nid: self.impact_scores.get(nid, 0), 
                               reverse=True)[:int(max_nodes * 1.2)]  # Allow 20% overflow
            nodes_to_keep = set(prioritized)
        
        self.graph = self.graph.subgraph(nodes_to_keep).copy()
    
    def _build_visualization_data(self, codebase_graph: CodebaseGraph) -> Dict[str, Any]:
        """Build visualization data with architectural metadata."""
        nodes = []
        edges = []
        
        for node_id, data in self.graph.nodes(data=True):
            nodes.append({
                "data": {
                    "id": node_id,
                    "label": data.get("name", node_id),
                    "type": data.get("type", "unknown"),
                    "layer": data.get("layer", "unknown"),
                    "impact_score": round(self.impact_scores.get(node_id, 0), 1),
                    "file_path": data.get("file_path", ""),
                }
            })
        
        for source, target, data in self.graph.edges(data=True):
            edges.append({
                "data": {
                    "id": f"{source}-{target}",
                    "source": source,
                    "target": target,
                    "relation": data.get("relation", "unknown"),
                    "strength": data.get("strength", 1.0)
                }
            })
        
        # Calculate statistics
        node_types = defaultdict(int)
        for node in nodes:
            node_types[node["data"]["type"]] += 1
        
        # Find most central entity
        most_central = max(self.impact_scores.items(), key=lambda x: x[1], default=(None, 0))
        most_central_name = self.graph.nodes[most_central[0]]["name"] if most_central[0] else "N/A"
        
        return {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "core_models": node_types.get("model", 0),
                "api_endpoints": node_types.get("api_endpoint", 0),
                "database_tables": node_types.get("database_table", 0),
                "services": node_types.get("service", 0),
                "critical_paths": len(self.critical_paths),
                "most_central_entity": most_central_name,
                "most_central_score": round(most_central[1], 1) if most_central[0] else 0,
                "critical_paths_detail": self.critical_paths[:3]
            }
        }
    
    def extract_smart_subgraph(self, codebase_graph: CodebaseGraph, 
                              element_name: str, max_depth: int = 2) -> Dict[str, Any]:
        """
        Extract focused subgraph with intelligent reasoning.
        """
        # Find target element
        target_id = None
        for node_id, data in self.graph.nodes(data=True):
            if data.get("name", "").lower() == element_name.lower():
                target_id = node_id
                break
        
        if not target_id:
            return {"error": f"Element '{element_name}' not found"}
        
        # Extract subgraph with depth limit
        subgraph_nodes = {target_id}
        for depth in range(max_depth):
            new_nodes = set()
            for node_id in subgraph_nodes:
                new_nodes.update(self.graph.predecessors(node_id))
                new_nodes.update(self.graph.successors(node_id))
            subgraph_nodes.update(new_nodes)
        
        subgraph = self.graph.subgraph(subgraph_nodes)
        
        # Build structured analysis
        target_data = self.graph.nodes[target_id]
        impact_score = self.impact_scores.get(target_id, 0)
        
        # Count usage
        api_count = len([e for e in subgraph.in_edges(target_id) 
                        if subgraph.nodes[e[0]].get("type") == "api_endpoint"])
        service_count = len([e for e in subgraph.in_edges(target_id)
                            if subgraph.nodes[e[0]].get("type") == "service"])
        
        # Find database table
        db_table = None
        for node_id in subgraph.successors(target_id):
            if subgraph.nodes[node_id].get("type") == "database_table":
                db_table = subgraph.nodes[node_id]["name"]
                break
        
        # Determine risk level
        if impact_score >= 8.0:
            risk_level = "High"
        elif impact_score >= 5.0:
            risk_level = "Medium"
        else:
            risk_level = "Low"
        
        return {
            "component": target_data.get("name"),
            "type": target_data.get("type"),
            "used_in_apis": [subgraph.nodes[e[0]]["name"] 
                            for e in subgraph.in_edges(target_id)
                            if subgraph.nodes[e[0]].get("type") == "api_endpoint"],
            "services": [subgraph.nodes[e[0]]["name"]
                        for e in subgraph.in_edges(target_id)
                        if subgraph.nodes[e[0]].get("type") == "service"],
            "database": {
                "table": db_table,
                "foreign_keys": target_data.get("foreign_keys", [])
            } if target_data.get("type") == "model" else None,
            "impact_score": round(impact_score, 1),
            "risk_level": risk_level,
            "analysis": self._generate_analysis(target_data, impact_score, api_count, service_count)
        }
    
    def _generate_analysis(self, target_data: Dict, score: float, 
                          api_count: int, service_count: int) -> List[str]:
        """Generate intelligent analysis points."""
        analysis = []
        
        node_type = target_data.get("type")
        name = target_data.get("name", "")
        
        if node_type == "model":
            if score >= 8.0:
                analysis.append("Central business entity")
            if api_count > 0:
                analysis.append(f"Exposed through {api_count} API endpoint(s)")
            if service_count > 0:
                analysis.append(f"Used by {service_count} service(s)")
            if target_data.get("foreign_keys"):
                analysis.append(f"Referenced by {len(target_data['foreign_keys'])} other entities")
        
        return analysis
