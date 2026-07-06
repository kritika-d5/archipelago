import time
import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import Dict, Any
from app.schemas.graph_schema import ParsingRequest, ParsingResponse
from app.knowledge_graph.repo_manager import RepositoryManager
from app.knowledge_graph.code_parser import CodeParser
from app.core.db import save_graph, save_parsed_data
from app.core.session import get_session_id
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/parse", tags=["parsing"])
parsed_graphs: Dict[str, Any] = {}


@router.post("/", response_model=ParsingResponse)
async def parse_repository(request: ParsingRequest, background_tasks: BackgroundTasks, session_id: str = Depends(get_session_id)):
    start_time = time.time()
    
    try:
        repo_url = request.repository_url
        
        # Check if URL is an organization (not a specific repo)
        # Organization URLs: https://github.com/org-name (no repo name after)
        # Or: https://github.com/orgs/org-name
        is_organization = False
        org_name = None
        
        # Normalize URL - remove protocol and github.com
        normalized_url = repo_url.rstrip('/').replace('https://github.com/', '').replace('http://github.com/', '').replace('github.com/', '')
        
        # Check URL pattern first
        if '/orgs/' in repo_url:
            # Format: https://github.com/orgs/org-name
            org_name = repo_url.split('/orgs/')[-1].rstrip('/').split('/')[0]
            is_organization = True
            logger.info(f"Detected organization URL pattern: {org_name}")
        else:
            # Check if it's just organization URL (no repo name)
            # Format: https://github.com/org-name (only 1 part after github.com)
            url_parts = [p for p in normalized_url.split('/') if p]
            if len(url_parts) == 1 and url_parts[0]:
                # Single part - treat as organization (URL pattern indicates organization)
                org_name = url_parts[0]
                is_organization = True
                logger.info(f"Detected organization URL pattern (single part): {org_name}. Will attempt organization analysis.")
        
        # Route to organization analysis if detected
        if is_organization and org_name:
            logger.info(f"Detected organization URL, routing to organization analysis: {org_name}")
            # Route to organization analysis
            from app.api.organization import analyze_organization
            try:
                org_result = await analyze_organization(org_name, session_id)
                
                # Store organization result in parsed_graphs with org key
                org_key = f"org:{org_name}"
                parsed_graphs[org_key] = {
                    "graph": None,  # Organizations don't have single graph
                    "organization_result": org_result,
                    "parsed_at": datetime.now()
                }
                
                # MongoDB is already saved in analyze_organization, but ensure the data structure is correct
                # Save with graph_data field for consistency with /visualize endpoint
                try:
                    dependency_graph = org_result.get("dependency_graph", {})
                    graph_data_for_viz = {
                        "nodes": dependency_graph.get("nodes", []),
                        "edges": dependency_graph.get("edges", []),
                        "statistics": dependency_graph.get("statistics", {}),
                        "violations": dependency_graph.get("violations", [])
                    }
                    # Update/ensure MongoDB has the right structure
                    save_graph(org_key, graph_data_for_viz, session_id, timestamp=datetime.now())
                    logger.info(f"Saved organization graph_data to MongoDB: {org_key}")
                except Exception as e:
                    logger.error(f"Failed to save organization graph_data to MongoDB: {str(e)}")
                
                # Return success response with organization data
                parsing_time = time.time() - start_time
                logger.info(f"Organization analysis complete in {parsing_time:.2f}s")
                
                return ParsingResponse(
                    success=True,
                    graph=None,
                    parsing_time=parsing_time,
                    files_parsed=org_result.get("summary", {}).get("total_repos", 0)
                )
            except Exception as e:
                logger.error(f"Organization analysis failed: {str(e)}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to analyze organization '{org_name}': {str(e)}"
                )
        
        # Single repository parsing (existing logic)
        repo_manager = RepositoryManager()
        parser = CodeParser(
            include_tests=request.include_tests,
            include_vendor=request.include_vendor,
            languages=request.languages,
            max_file_size=request.max_file_size
        )
        
        logger.info(f"Cloning/updating repository: {repo_url}")
        repo_path = repo_manager.clone_or_update(repo_url, request.branch)
        
        commit_hash = repo_manager.get_commit_hash(repo_path)
        branch = repo_manager.get_branch(repo_path) or request.branch
        
        logger.info(f"Parsing repository: {repo_path}")
        graph = parser.parse_repository(
            repo_path,
            repo_url=request.repository_url,
            branch=branch,
            commit_hash=commit_hash
        )
        
        graph_key = f"{request.repository_url}:{branch or 'main'}"
        parsed_graphs[graph_key] = {
            "graph": graph,
            "repo_path": str(repo_path),
            "parsed_at": graph.metadata.parsed_at
        }
        
        logger.info(f"Graph stored with key: {graph_key}")
        logger.info(f"Available keys: {list(parsed_graphs.keys())}")
        
        # Save UI-ready graph data to 'graphs' collection
        try:
            graph_json = graph.model_dump(mode='json')
            save_graph(graph_key, graph_json, session_id, timestamp=datetime.now())
            logger.info(f"Graph data saved to MongoDB 'graphs' collection")
        except Exception as e:
            logger.error(f"Failed to save graph to MongoDB: {str(e)}")
        
        # Save raw parsed data to 'parsed_data' collection
        try:
            raw_data = graph.model_dump(mode='json')
            save_parsed_data(graph_key, raw_data, session_id)
            logger.info(f"Parsed data saved to MongoDB 'parsed_data' collection")
        except Exception as e:
            logger.error(f"Failed to save parsed data to MongoDB: {str(e)}")
        
        parsing_time = time.time() - start_time
        logger.info(f"Parsing complete in {parsing_time:.2f}s")
        
        return ParsingResponse(
            success=True,
            graph=graph,
            parsing_time=parsing_time,
            files_parsed=graph.metadata.total_files
        )
        
    except Exception as e:
        logger.error(f"Error parsing repository: {e}", exc_info=True)
        parsing_time = time.time() - start_time
        return ParsingResponse(
            success=False,
            error=str(e),
            parsing_time=parsing_time,
            files_parsed=0
        )


@router.get("/")
async def list_parsed_graphs(session_id: str = Depends(get_session_id)):
    from app.core.db import get_all_graphs
    
    graphs_list = []
    
    # Add in-memory graphs
    for key, data in parsed_graphs.items():
        # Skip organization entries (they have graph=None) - they're handled by MongoDB
        if data.get("graph") is None:
            continue
        graphs_list.append({
            "key": key,
            "repository": data["graph"].metadata.repository_name,
            "parsed_at": data["parsed_at"]
        })
    
    # Add organization graphs from in-memory parsed_graphs
    for key, data in parsed_graphs.items():
        if key.startswith("org:") and data.get("organization_result"):
            org_name = key.replace("org:", "")
            graphs_list.append({
                "key": key,
                "repository": f"Organization: {org_name}",
                "parsed_at": data["parsed_at"].isoformat() if hasattr(data["parsed_at"], 'isoformat') else str(data["parsed_at"])
            })
    
    # Also add organization graphs from MongoDB
    try:
        mongo_graphs = get_all_graphs(session_id)
        for graph_doc in mongo_graphs:
            graph_name = graph_doc.get("graph_name", "")
            if graph_name.startswith("org:"):
                # Check if already added from in-memory
                if not any(g["key"] == graph_name for g in graphs_list):
                    # Organization graph
                    org_name = graph_name.replace("org:", "")
                    timestamp = graph_doc.get("timestamp", datetime.now())
                    
                    graphs_list.append({
                        "key": graph_name,
                        "repository": f"Organization: {org_name}",
                        "parsed_at": timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp)
                    })
                    logger.info(f"Added organization graph from MongoDB: {graph_name}")
    except Exception as e:
        logger.warning(f"Error fetching graphs from MongoDB: {str(e)}")
    
    return {"graphs": graphs_list}


@router.get("/{repo_key:path}")
async def get_parsed_graph(repo_key: str):
    from urllib.parse import unquote
    decoded_key = unquote(repo_key)
    actual_key = decoded_key if decoded_key in parsed_graphs else (repo_key if repo_key in parsed_graphs else None)
    
    if actual_key is None:
        for key in parsed_graphs.keys():
            if key == decoded_key or key == repo_key:
                actual_key = key
                break
    
    if actual_key is None or actual_key not in parsed_graphs:
        raise HTTPException(status_code=404, detail="Graph not found")
    
    return {
        "graph": parsed_graphs[actual_key]["graph"],
        "parsed_at": parsed_graphs[actual_key]["parsed_at"]
    }


@router.get("/{repo_key:path}/json")
async def get_parsed_graph_json(repo_key: str):
    from urllib.parse import unquote
    from fastapi.responses import JSONResponse
    decoded_key = unquote(repo_key)
    actual_key = decoded_key if decoded_key in parsed_graphs else (repo_key if repo_key in parsed_graphs else None)
    
    if actual_key is None:
        for key in parsed_graphs.keys():
            if key == decoded_key or key == repo_key:
                actual_key = key
                break
    
    if actual_key is None or actual_key not in parsed_graphs:
        logger.error(f"Graph not found. Requested: {decoded_key}. Available: {list(parsed_graphs.keys())}")
        raise HTTPException(status_code=404, detail=f"Graph not found. Available keys: {list(parsed_graphs.keys())}")
    
    graph = parsed_graphs[actual_key]["graph"]
    return JSONResponse(content=graph.model_dump(mode='json'))


@router.delete("/{repo_key}")
async def delete_parsed_graph(repo_key: str):
    """Delete a parsed graph."""
    if repo_key not in parsed_graphs:
        raise HTTPException(status_code=404, detail="Graph not found")
    
    del parsed_graphs[repo_key]
    return {"message": "Graph deleted successfully"}
