import logging
from fastapi import APIRouter, HTTPException
from typing import Optional, Dict, Any
from urllib.parse import unquote
from pathlib import Path
from app.agents.graph_agent import GraphBuilder, KnowledgeGraphBuilder
from app.api.parse import parsed_graphs
from app.core.db import save_graph, save_parsed_data, get_graph, get_all_graphs
from app.knowledge_graph.code_parser import parse_repository as simple_parse_repository
from app.core.utils import clone_or_pull_repo
from app.schemas.graph_schema import SubgraphContext
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("/{repo_key:path}/visualize")
async def get_graph_visualization(repo_key: str, depth: Optional[int] = None, 
                                  important_only: bool = False):
    try:
        decoded_key = unquote(repo_key)
    except Exception:
        decoded_key = repo_key
    
    logger.info(f"Requested key (raw): '{repo_key}'")
    logger.info(f"Requested key (decoded): '{decoded_key}'")
    
    # Check if it's an organization graph (stored in MongoDB)
    if decoded_key.startswith("org:") or repo_key.startswith("org:"):
        org_key = decoded_key if decoded_key.startswith("org:") else repo_key
        logger.info(f"Loading organization graph: {org_key}")
        
        from app.core.db import get_graph
        graph_doc = get_graph(org_key)
        
        if not graph_doc:
            raise HTTPException(status_code=404, detail=f"Organization graph '{org_key}' not found in MongoDB")
        
        graph_data = graph_doc.get("graph_data", {})
        
        # Convert organization graph format to visualization format
        visualization = convert_org_graph_to_visualization(graph_data, org_key)
        return visualization
    
    # Handle regular repository graphs
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
    
    # Use legacy builder (original approach)
    builder = GraphBuilder()
    if depth:
        all_element_ids = [elem.id for elem in graph_data.elements[:50]]
        visualization = builder.get_subgraph(graph_data, all_element_ids, depth=depth)
    else:
        visualization = builder.get_graph_for_visualization(graph_data, filter_important_only=False)
    
    # SAVE TO MONGODB
    save_graph_to_db(actual_key, visualization)
    
    return visualization


def convert_org_graph_to_visualization(org_graph: Dict[str, Any], org_key: str) -> Dict[str, Any]:
    """
    Convert organization dependency graph format to frontend visualization format.
    
    Organization format:
    - nodes: [{id, type, language, services, endpoints}]
    - edges: [{from, to, type, dependency_type, event_name?, endpoint?, violation?, circular?}]
    
    Visualization format (Cytoscape):
    - nodes: [{"data": {id, label, type, category, ...}}]
    - edges: [{"data": {id, source, target, relation, dependency_type, ...}}]
    - metadata: {total_nodes, total_edges, repository_name}
    """
    nodes = []
    edges = []
    
    # First pass: collect all node IDs and calculate degrees
    node_ids = set()
    node_degrees = {}
    
    for node in org_graph.get("nodes", []):
        node_id = node.get("id", "")
        if node_id:
            node_ids.add(node_id)
            node_degrees[node_id] = 0
    
    # Calculate degrees from edges
    for edge in org_graph.get("edges", []):
        from_node = edge.get("from", "")
        to_node = edge.get("to", "")
        if from_node in node_degrees:
            node_degrees[from_node] += 1
        if to_node in node_degrees:
            node_degrees[to_node] += 1
    
    # Convert nodes - wrap in "data" property for Cytoscape
    for node in org_graph.get("nodes", []):
        node_id = node.get("id", "")
        if not node_id:
            continue
            
        node_type = node.get("type", "service")
        
        # Determine category based on type
        category_map = {
            "service": "api",
            "library": "module"
        }
        category = category_map.get(node_type, "api")
        
        # Build label - use node ID as primary label
        services = node.get("services", [])
        if services:
            label = f"{node_id}\n({', '.join(services[:2])})"
        else:
            label = node_id
        
        nodes.append({
            "data": {
                "id": node_id,
                "label": label,
                "type": node_type,
                "category": category,
                "language": node.get("language", "unknown"),
                "services": services,
                "endpoints": node.get("endpoints", 0),
                "degree": node_degrees.get(node_id, 0)
            }
        })
    
    # Convert edges - wrap in "data" property for Cytoscape
    for idx, edge in enumerate(org_graph.get("edges", [])):
        from_node = edge.get("from", "")
        to_node = edge.get("to", "")
        edge_type = edge.get("type", "UNKNOWN")
        
        if not from_node or not to_node:
            continue
        
        # Build relation label
        relation_parts = [edge_type]
        if edge.get("event_name"):
            relation_parts.append(f"Event: {edge['event_name']}")
        if edge.get("endpoint"):
            relation_parts.append(edge["endpoint"])
        if edge.get("violation"):
            relation_parts.append("(VIOLATION)")
        if edge.get("circular"):
            relation_parts.append("(CIRCULAR)")
        
        relation = " | ".join(relation_parts)
        
        # Map edge type to dependency_type for styling
        dependency_type_map = {
            "REST": "rest",
            "EVENT": "event",
            "IMPORT": "import",
            "DB_ACCESS": "db_access",
            "CIRCULAR": "circular"
        }
        dependency_type = dependency_type_map.get(edge_type, edge.get("dependency_type", ""))
        
        edges.append({
            "data": {
                "id": f"{from_node}-{to_node}-{idx}",
                "source": from_node,
                "target": to_node,
                "relation": relation,
                "dependency_type": dependency_type,
                "type": edge_type,
                "strength": 1.0,
                "violation": edge.get("violation", False),
                "circular": edge.get("circular", False),
                "event_name": edge.get("event_name", ""),
                "endpoint": edge.get("endpoint", "")
            }
        })
    
    # Extract organization name
    org_name = org_key.replace("org:", "") if org_key.startswith("org:") else org_key
    
    return {
        "nodes": nodes,
        "edges": edges,
        "metadata": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "repository_name": f"Organization: {org_name}",
            "graph_type": "organization",
            "statistics": org_graph.get("statistics", {}),
            "violations": org_graph.get("violations", [])
        }
    }


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
        error_msg = f"Failed to save graph to MongoDB: {str(e)}"
        logger.error(error_msg)
        # Re-raise so the API can return proper error
        raise HTTPException(status_code=500, detail=error_msg)


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
        
        # Save UI-ready graph data to 'graphs' collection
        save_graph_to_db(graph_name, graph_data)
        logger.info(f"Graph saved to MongoDB 'graphs' collection with name: {graph_name}")
        
        # Save raw parsed data to 'parsed_data' collection
        try:
            save_parsed_data(graph_name, parsed_data)
            logger.info(f"Parsed data saved to MongoDB 'parsed_data' collection")
        except Exception as e:
            logger.error(f"Failed to save parsed data to MongoDB: {str(e)}")
        
        return graph_data
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating graph: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error generating graph: {str(e)}"
        )


@router.get("/db/test")
async def test_db_connection():
    """Test MongoDB connection and return status."""
    from app.core.db import test_connection
    return test_connection()


@router.get("/{repo_key:path}/explain")
async def explain_project(repo_key: str):
    """
    Get LLM-generated explanation of the project including database schema.
    Supports both in-memory graphs and MongoDB organization graphs.
    """
    try:
        decoded_key = unquote(repo_key)
    except Exception:
        decoded_key = repo_key
    
    logger.info(f"Requesting explanation for: {decoded_key}")
    
    # Check if it's an organization graph (stored in MongoDB)
    if decoded_key.startswith("org:") or repo_key.startswith("org:"):
        org_key = decoded_key if decoded_key.startswith("org:") else repo_key
        logger.info(f"Loading organization graph for explanation: {org_key}")
        
        graph_doc = get_graph(org_key)
        
        if not graph_doc:
            raise HTTPException(status_code=404, detail=f"Organization graph '{org_key}' not found")
        
        org_graph = graph_doc.get("graph_data", {})
        
        # Use LLM service to explain organization graph
        try:
            from app.core.llm import LLMService
            llm_service = LLMService()
            
            # Create a simple explanation for organization graph
            nodes = org_graph.get("nodes", [])
            edges = org_graph.get("edges", [])
            
            explanation = llm_service.explain_organization_graph(org_graph, org_key)
            return {
                "explanation": explanation, 
                "repository_name": org_key,
                "node_count": len(nodes),
                "edge_count": len(edges)
            }
        except Exception as e:
            logger.error(f"Error generating explanation for org graph: {e}")
            # Fallback: return basic info
            nodes = org_graph.get("nodes", [])
            edges = org_graph.get("edges", [])
            node_types = {}
            for node in nodes:
                node_type = node.get("type", "unknown")
                node_types[node_type] = node_types.get(node_type, 0) + 1
            
            return {
                "explanation": f"Organization Graph: {org_key}\n\nServices: {len(nodes)}\nDependencies: {len(edges)}\nNode Types: {node_types}\n\nNote: Full LLM explanation unavailable.",
                "repository_name": org_key,
                "node_count": len(nodes),
                "edge_count": len(edges)
            }
    
    # Find the graph in parsed_graphs (in-memory cache)
    actual_key = None
    for test_key in [decoded_key, repo_key]:
        if test_key in parsed_graphs:
            actual_key = test_key
            break
    
    if actual_key is None:
        for stored_key in parsed_graphs.keys():
            if stored_key == decoded_key or stored_key == repo_key:
                actual_key = stored_key
                break
            if stored_key.replace('://', '') == decoded_key.replace('://', ''):
                actual_key = stored_key
                break
    
    if actual_key is None:
        raise HTTPException(status_code=404, detail=f"Graph not found for key: {decoded_key}")
    
    graph_data = parsed_graphs[actual_key]["graph"]
    
    # Use LLM service to explain project
    try:
        from app.core.llm import LLMService
        llm_service = LLMService()
        explanation = llm_service.explain_project(graph_data)
        return {"explanation": explanation, "repository_name": graph_data.metadata.repository_name}
    except Exception as e:
        logger.error(f"Error generating explanation: {e}")
        # Fallback: return basic info
        return {
            "explanation": f"Project: {graph_data.metadata.repository_name}\n\nDatabase Languages: {', '.join([lang.value for lang in graph_data.metadata.database_languages]) if graph_data.metadata.database_languages else 'None detected'}\n\nDatabase Schemas: {len(graph_data.database_schemas)}\n\nNote: LLM explanation unavailable. {str(e)}",
            "repository_name": graph_data.metadata.repository_name
        }


@router.get("/{repo_key:path}/subgraph/{element_id:path}")
async def get_subgraph_context(repo_key: str, element_id: str, max_depth: int = 3):
    """
    Extract subgraph context for a given element.
    Returns structured context showing what would be affected if the element is modified.
    """
    try:
        decoded_key = unquote(repo_key)
    except Exception:
        decoded_key = repo_key
    
    # Find the graph
    actual_key = None
    for test_key in [decoded_key, repo_key]:
        if test_key in parsed_graphs:
            actual_key = test_key
            break
    
    if actual_key is None:
        for stored_key in parsed_graphs.keys():
            if stored_key == decoded_key or stored_key == repo_key:
                actual_key = stored_key
                break
            if stored_key.replace('://', '') == decoded_key.replace('://', ''):
                actual_key = stored_key
                break
    
    if actual_key is None:
        raise HTTPException(status_code=404, detail=f"Graph not found for key: {decoded_key}")
    
    graph_data = parsed_graphs[actual_key]["graph"]
    builder = GraphBuilder()
    
    # Extract subgraph context
    context = builder.extract_subgraph_context(graph_data, element_id, max_depth=max_depth)
    
    return context.dict()