import logging
from fastapi import APIRouter, HTTPException
from typing import Optional
from urllib.parse import unquote
from app.agents.graph_agent import GraphBuilder
from app.api.parse import parsed_graphs

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
    
    return visualization


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
