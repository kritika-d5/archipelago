"""
Graph API endpoints for knowledge graph generation.
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from pathlib import Path

from app.knowledge_graph.code_parser import parse_repository
from app.knowledge_graph.graph_builder import KnowledgeGraphBuilder
from app.core.utils import clone_or_pull_repo

router = APIRouter(prefix="/graph", tags=["graph"])


@router.post("/generate-graph")
def generate_graph(repo_url: str) -> Dict[str, Any]:
    """
    Generate a knowledge graph from a repository.
    
    Args:
        repo_url: Git repository URL to analyze
        
    Returns:
        Dictionary containing nodes and edges of the knowledge graph
    """
    try:
        # Create temporary directory for cloned repository
        repos_dir = Path("./repos")
        repos_dir.mkdir(exist_ok=True)
        
        # Use repo name from URL as directory name
        repo_name = repo_url.split("/")[-1].replace(".git", "")
        local_path = repos_dir / "temp" / repo_name
        
        # Clone or pull the repository
        success = clone_or_pull_repo(repo_url, str(local_path))
        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to clone or pull repository: {repo_url}"
            )
        
        # Parse the repository
        parsed_data = parse_repository(str(local_path))
        
        # Build the graph
        builder = KnowledgeGraphBuilder()
        graph = builder.build_graph(parsed_data)
        
        # Convert graph to serializable format
        nodes = [
            {
                "id": node_id,
                **node_data
            }
            for node_id, node_data in graph.nodes(data=True)
        ]
        
        edges = [
            {
                "source": source,
                "target": target,
                **edge_data
            }
            for source, target, edge_data in graph.edges(data=True)
        ]
        
        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "services": len([n for n in nodes if n.get("type") == "Service"]),
                "schemas": len([n for n in nodes if n.get("type") == "Schema"]),
                "endpoints": len([n for n in nodes if n.get("type") == "Endpoint"])
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating graph: {str(e)}"
        )


@router.get("/health")
def graph_health():
    """Health check endpoint for graph service."""
    return {"status": "healthy", "service": "graph"}

