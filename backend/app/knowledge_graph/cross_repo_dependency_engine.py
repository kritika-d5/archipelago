"""
Cross-Repository Dependency Engine.
Analyzes dependencies between repositories in an organization.
"""
import networkx as nx
from typing import List, Dict, Set, Any, Optional
import logging

logger = logging.getLogger(__name__)


class CrossRepoDependencyEngine:
    """Engine for detecting cross-repository dependencies."""
    
    def __init__(self):
        """Initialize dependency engine."""
        self.graph = nx.DiGraph()
        self.repo_data = {}
        self.violations = []
    
    def analyze_organization(self, repos_data: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze all repositories and build dependency graph.
        
        Args:
            repos_data: Dictionary mapping repo names to their parsed data
            
        Returns:
            Global dependency graph with nodes and edges
        """
        self.repo_data = repos_data
        self.graph.clear()
        self.violations = []
        
        # Add all repositories as nodes
        for repo_name, repo_info in repos_data.items():
            repo_type = self._determine_repo_type(repo_name, repo_info)
            self.graph.add_node(
                repo_name,
                type=repo_type,
                language=repo_info.get("language", "unknown"),
                services=repo_info.get("services", []),
                endpoints=len(repo_info.get("api_endpoints", []))
            )
        
        # Detect dependencies
        self._detect_import_dependencies()
        self._detect_rest_dependencies()
        self._detect_event_dependencies()
        self._detect_db_access_violations()
        self._detect_circular_dependencies()
        
        # Build result
        return self._build_result()
    
    def _determine_repo_type(self, repo_name: str, repo_info: Dict[str, Any]) -> str:
        """Determine if repo is a service, library, or shared."""
        name_lower = repo_name.lower()
        if 'shared' in name_lower or 'contract' in name_lower:
            return "library"
        elif 'service' in name_lower:
            return "service"
        else:
            return "service"  # Default to service
    
    def _detect_import_dependencies(self):
        """Detect dependencies via imports (shared-contracts, etc.)."""
        for repo_name, repo_info in self.repo_data.items():
            imports = repo_info.get("imports", [])
            shared_imports = repo_info.get("shared_imports", [])
            
            # Check for shared-contracts imports
            for imp in shared_imports:
                if 'shared' in imp.lower() or 'contract' in imp.lower():
                    # Find shared-contracts repo
                    for other_repo in self.repo_data.keys():
                        if 'shared' in other_repo.lower() or 'contract' in other_repo.lower():
                            self.graph.add_edge(
                                repo_name,
                                other_repo,
                                type="IMPORT",
                                dependency_type="library"
                            )
            
            # Check for direct cross-repo imports
            for imp in imports:
                # Look for patterns like ../other-service or /other-service
                for other_repo in self.repo_data.keys():
                    if other_repo != repo_name and other_repo in imp:
                        self.graph.add_edge(
                            repo_name,
                            other_repo,
                            type="IMPORT",
                            dependency_type="direct"
                        )
    
    def _detect_rest_dependencies(self):
        """Detect REST API dependencies between services."""
        for repo_name, repo_info in self.repo_data.items():
            external_calls = repo_info.get("external_calls", [])
            
            for call in external_calls:
                target = call.get("target", "")
                # Extract service name from target (e.g., "auth-service" from "http://auth-service/validate")
                target_service = self._extract_service_name(target)
                
                if target_service:
                    # Find matching repo
                    for other_repo in self.repo_data.keys():
                        if target_service in other_repo.lower() or other_repo.lower() in target_service:
                            self.graph.add_edge(
                                repo_name,
                                other_repo,
                                type="REST",
                                endpoint=call.get("endpoint", ""),
                                dependency_type="api"
                            )
    
    def _detect_event_dependencies(self):
        """Detect event-driven dependencies."""
        # Map events to producers and consumers
        event_producers = {}  # event_name -> [repo_names]
        event_consumers = {}  # event_name -> [repo_names]
        
        for repo_name, repo_info in self.repo_data.items():
            # Events produced
            events_produced = repo_info.get("events_produced", [])
            for event in events_produced:
                if event not in event_producers:
                    event_producers[event] = []
                event_producers[event].append(repo_name)
            
            # Events consumed
            events_consumed = repo_info.get("events_consumed", [])
            for event in events_consumed:
                if event not in event_consumers:
                    event_consumers[event] = []
                event_consumers[event].append(repo_name)
        
        # Create edges: producer -> consumer via events
        for event, producers in event_producers.items():
            consumers = event_consumers.get(event, [])
            for producer in producers:
                for consumer in consumers:
                    if producer != consumer:
                        self.graph.add_edge(
                            producer,
                            consumer,
                            type="EVENT",
                            event_name=event,
                            dependency_type="event_driven"
                        )
    
    def _detect_db_access_violations(self):
        """Detect cross-domain database access violations."""
        for repo_name, repo_info in self.repo_data.items():
            imports = repo_info.get("imports", [])
            
            # Check for imports that access other services' DB models
            for imp in imports:
                for other_repo in self.repo_data.keys():
                    if other_repo != repo_name:
                        # Check if import references other repo's DB
                        if other_repo in imp and ('db' in imp.lower() or 'model' in imp.lower()):
                            violation = {
                                "type": "DB_ACCESS",
                                "from": repo_name,
                                "to": other_repo,
                                "import": imp,
                                "severity": "high"
                            }
                            self.violations.append(violation)
                            
                            # Add edge with violation flag
                            if not self.graph.has_edge(repo_name, other_repo):
                                self.graph.add_edge(
                                    repo_name,
                                    other_repo,
                                    type="DB_ACCESS",
                                    violation=True,
                                    dependency_type="violation"
                                )
    
    def _detect_circular_dependencies(self):
        """Detect circular dependencies between repositories."""
        try:
            # Find all simple cycles
            cycles = list(nx.simple_cycles(self.graph))
            
            for cycle in cycles:
                if len(cycle) >= 2:
                    violation = {
                        "type": "CIRCULAR",
                        "repos": cycle,
                        "severity": "medium"
                    }
                    self.violations.append(violation)
                    
                    # Mark edges in cycle
                    for i in range(len(cycle)):
                        from_repo = cycle[i]
                        to_repo = cycle[(i + 1) % len(cycle)]
                        
                        if self.graph.has_edge(from_repo, to_repo):
                            # Update edge to mark as circular
                            edge_data = self.graph[from_repo][to_repo]
                            edge_data['circular'] = True
        except Exception as e:
            logger.debug(f"Error detecting cycles: {str(e)}")
    
    def _extract_service_name(self, target: str) -> Optional[str]:
        """Extract service name from target string."""
        # Patterns: "auth-service", "http://auth-service", "auth-service/validate"
        patterns = [
            r'([\w-]+-service)',
            r'([\w-]+_service)',
        ]
        
        import re
        for pattern in patterns:
            match = re.search(pattern, target, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
    
    def _build_result(self) -> Dict[str, Any]:
        """Build final result structure."""
        nodes = []
        edges = []
        
        # Build nodes
        for node_id, node_data in self.graph.nodes(data=True):
            nodes.append({
                "id": node_id,
                "type": node_data.get("type", "service"),
                "language": node_data.get("language", "unknown"),
                "services": node_data.get("services", []),
                "endpoints": node_data.get("endpoints", 0)
            })
        
        # Build edges
        for from_node, to_node, edge_data in self.graph.edges(data=True):
            edge = {
                "from": from_node,
                "to": to_node,
                "type": edge_data.get("type", "UNKNOWN"),
                "dependency_type": edge_data.get("dependency_type", "")
            }
            
            # Add additional metadata
            if "event_name" in edge_data:
                edge["event_name"] = edge_data["event_name"]
            if "endpoint" in edge_data:
                edge["endpoint"] = edge_data["endpoint"]
            if edge_data.get("violation"):
                edge["violation"] = True
            if edge_data.get("circular"):
                edge["circular"] = True
            
            edges.append(edge)
        
        return {
            "nodes": nodes,
            "edges": edges,
            "violations": self.violations,
            "statistics": {
                "total_repos": len(nodes),
                "total_dependencies": len(edges),
                "rest_dependencies": len([e for e in edges if e["type"] == "REST"]),
                "event_dependencies": len([e for e in edges if e["type"] == "EVENT"]),
                "import_dependencies": len([e for e in edges if e["type"] == "IMPORT"]),
                "violations": len(self.violations)
            }
        }

