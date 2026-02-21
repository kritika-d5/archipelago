import logging
from fastapi import APIRouter, HTTPException
from typing import Optional, Dict, Any
from urllib.parse import unquote
from pathlib import Path
from app.agents.graph_agent import GraphBuilder
from app.api.parse import parsed_graphs
from app.core.db import save_graph, get_graph, get_all_graphs  # IMPORT DB FUNCTIONS
from app.knowledge_graph.code_parser import parse_repository as simple_parse_repository
from app.agents.graph_agent import KnowledgeGraphBuilder
from app.core.utils import clone_or_pull_repo
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("/{repo_key:path}/visualize")
async def get_graph_visualization(repo_key: str, depth: Optional[int] = None):
    try:
        decoded_key = unquote(repo_key)
    except Exception:
        decoded_key = repo_key
    
    logger.info(f"Requested key (raw): '{repo_key}'")
    logger.info(f"Requested key (decoded): '{decoded_key}'")
    logger.info(f"Available keys: {list(parsed_graphs.keys())}")
    
    actual_key = None
    possible_keys = [decoded_key, repo_key]
    
    for test_key in possible_keys:
        if test_key in parsed_graphs:
            actual_key = test_key
            logger.info(f"Found graph with key: {actual_key}")
            break
    
    if actual_key is None:
        for stored_key in parsed_graphs.keys():
            if stored_key == decoded_key or stored_key == repo_key:
                actual_key = stored_key
                logger.info(f"Matched by exact comparison: {actual_key}")
                break
            if stored_key.replace('://', '') == decoded_key.replace('://', ''):
                actual_key = stored_key
                logger.info(f"Matched by normalized comparison: {actual_key}")
                break
    
    if actual_key is None:
        available_keys = list(parsed_graphs.keys())
        error_msg = f"Graph not found. Requested: '{decoded_key}' (raw: '{repo_key}'). Available: {available_keys}"
        logger.error(error_msg)
        raise HTTPException(status_code=404, detail=error_msg)
    
    graph_data = parsed_graphs[actual_key]["graph"]
    builder = GraphBuilder()
    
    if depth:
        # Get subgraph with specific depth
        all_element_ids = [elem.id for elem in graph_data.elements[:50]]
        visualization = builder.get_subgraph(graph_data, all_element_ids, depth=depth)
    else:
        # Get full graph
        visualization = builder.get_graph_for_visualization(graph_data)
    
    # SAVE TO MONGODB
    save_graph_to_db(actual_key, visualization)
    
    return visualization


def save_graph_to_db(graph_name: str, graph_data: dict):
    """Helper function to save graph to MongoDB"""
    try:
        save_graph(
            graph_name=graph_name,
            graph_dict=graph_data,
            timestamp=datetime.now()
        )
        logger.info(f"Graph '{graph_name}' saved to MongoDB")
    except Exception as e:
        logger.error(f"Failed to save graph to MongoDB: {str(e)}")


# NEW ENDPOINT: Get all saved graphs from MongoDB
@router.get("/saved/all")
async def get_all_saved_graphs():
    """Retrieve all graphs stored in MongoDB"""
    try:
        graphs = get_all_graphs()
        return {
            "count": len(graphs),
            "graphs": graphs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve graphs: {str(e)}")


# NEW ENDPOINT: Get specific graph from MongoDB
@router.get("/saved/{graph_name}")
async def get_saved_graph(graph_name: str):
    """Retrieve a specific graph from MongoDB by name"""
    try:
        graph_doc = get_graph(graph_name)
        if not graph_doc:
            raise HTTPException(status_code=404, detail=f"Graph '{graph_name}' not found in database")
        return graph_doc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve graph: {str(e)}")


@router.get("/{repo_key:path}/element/{element_id}")
async def get_element_details(repo_key: str, element_id: str):
    decoded_key = unquote(repo_key)
    actual_key = decoded_key if decoded_key in parsed_graphs else (repo_key if repo_key in parsed_graphs else None)
    if actual_key is None:
        for key in parsed_graphs.keys():
            if key == decoded_key or key == repo_key:
                actual_key = key
                break
    
    if actual_key not in parsed_graphs:
        raise HTTPException(status_code=404, detail="Graph not found")
    
    graph_data = parsed_graphs[actual_key]["graph"]
    element = graph_data.get_element_by_id(element_id)
    
    if not element:
        raise HTTPException(status_code=404, detail="Element not found")
    
    # Get dependencies
    dependencies = graph_data.get_dependencies_for_element(element_id)
    dependents = graph_data.get_dependents_of_element(element_id)
    
    return {
        "element": element,
        "dependencies": dependencies,
        "dependents": dependents
    }


@router.get("/{repo_key:path}/file/{file_path:path}")
async def get_file_elements(repo_key: str, file_path: str):
    decoded_key = unquote(repo_key)
    actual_key = decoded_key if decoded_key in parsed_graphs else (repo_key if repo_key in parsed_graphs else None)
    if actual_key is None:
        for key in parsed_graphs.keys():
            if key == decoded_key or key == repo_key:
                actual_key = key
                break
    
    if actual_key not in parsed_graphs:
        raise HTTPException(status_code=404, detail="Graph not found")
    
    graph_data = parsed_graphs[actual_key]["graph"]
    elements = graph_data.get_elements_by_file(file_path)
    
    return {
        "file_path": file_path,
        "elements": elements
    }


@router.get("/{repo_key:path}/impact/{element_id}")
async def get_impact_chain(repo_key: str, element_id: str, max_depth: int = 5):
    decoded_key = unquote(repo_key)
    actual_key = decoded_key if decoded_key in parsed_graphs else (repo_key if repo_key in parsed_graphs else None)
    if actual_key is None:
        for key in parsed_graphs.keys():
            if key == decoded_key or key == repo_key:
                actual_key = key
                break
    
    if actual_key not in parsed_graphs:
        raise HTTPException(status_code=404, detail="Graph not found")
    
    graph_data = parsed_graphs[actual_key]["graph"]
    builder = GraphBuilder()
    
    impact_chain = builder.find_impact_chain(graph_data, element_id, max_depth)
    
    return {
        "element_id": element_id,
        "impact_chain": impact_chain,
        "total_impacts": len(impact_chain)
    }


@router.post("/generate-graph")
async def generate_graph(repo_url: str) -> Dict[str, Any]:
    """
    Generate a knowledge graph from a repository and save it to MongoDB.
    
    Args:
        repo_url: Git repository URL to analyze
        
    Returns:
        Dictionary containing nodes, edges, and stats of the knowledge graph
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
        
        # Parse the repository using simple parser
        parsed_data = simple_parse_repository(str(local_path))
        
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
        
        # Prepare graph data for MongoDB
        graph_data = {
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
        
        # Save to MongoDB
        graph_name = f"{repo_url}:main"
        save_graph_to_db(graph_name, graph_data)
        logger.info(f"Graph saved to MongoDB with name: {graph_name}")
        
        return graph_data
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating graph: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error generating graph: {str(e)}"
        )