import time
import logging
from urllib.parse import unquote
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import Dict, Any, Optional
from app.schemas.graph_schema import ParsingRequest, ParsingResponse, CodebaseGraph
from app.knowledge_graph.repo_manager import RepositoryManager
from app.knowledge_graph.code_parser import CodeParser
from app.core.db import save_graph, save_parsed_data, get_parsed_data
from app.core.session import get_session_id
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/parse", tags=["parsing"])


def load_codebase_graph(repo_key: str, owner_id: str) -> Optional[CodebaseGraph]:
    """Load & reconstruct a single-repo CodebaseGraph for an owner from MongoDB.

    Replaces the old global in-memory `parsed_graphs` cache: graphs are persisted per-owner in
    the `parsed_data` collection, so lookups are isolated by owner AND survive Render restarts
    (also closes Phase 2.1). Returns None for org keys (different shape) or when not found.
    """
    candidates = []
    for k in (repo_key, unquote(repo_key)):
        if k and k not in candidates:
            candidates.append(k)
    for key in candidates:
        try:
            doc = get_parsed_data(key, owner_id)
        except Exception as e:
            logger.warning(f"load_codebase_graph: db error for '{key}': {e}")
            continue
        if not doc:
            continue
        raw = doc.get("parsed_data")
        if not isinstance(raw, dict) or "elements" not in raw or "metadata" not in raw:
            continue  # org data or an unexpected shape — not a CodebaseGraph
        try:
            graph = CodebaseGraph.model_validate(raw)
            graph.build_indexes()
            return graph
        except Exception as e:
            logger.warning(f"load_codebase_graph: reconstruct failed for '{key}': {e}")
    return None


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

                org_key = f"org:{org_name}"

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
                    graph_key=org_key,
                    parsing_time=parsing_time,
                    files_parsed=org_result.get("summary", {}).get("total_repos", 0)
                )
            except Exception as e:
                logger.error(f"Organization analysis failed: {str(e)}", exc_info=True)
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to analyze organization '{org_name}'"
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
        logger.info(f"Graph parsed with key: {graph_key}")

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
            graph_key=graph_key,
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
    try:
        for doc in get_all_graphs(session_id):
            key = doc.get("graph_name", "")
            if not key:
                continue
            ts = doc.get("timestamp", datetime.now())
            if key.startswith("org:"):
                repository = f"Organization: {key[len('org:'):]}"
            else:
                # Friendly repo name from the key (…/name.git:branch)
                base = key.rsplit(":", 1)[0]
                repository = base.rstrip("/").split("/")[-1].replace(".git", "") or key
            graphs_list.append({
                "key": key,
                "repository": repository,
                "parsed_at": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
            })
    except Exception as e:
        logger.warning(f"Error listing graphs from MongoDB: {str(e)}")

    return {"graphs": graphs_list}


@router.get("/{repo_key:path}")
async def get_parsed_graph(repo_key: str, session_id: str = Depends(get_session_id)):
    graph = load_codebase_graph(repo_key, session_id)
    if graph is None:
        raise HTTPException(status_code=404, detail="Graph not found")
    return {"graph": graph, "parsed_at": graph.metadata.parsed_at}


@router.get("/{repo_key:path}/json")
async def get_parsed_graph_json(repo_key: str, session_id: str = Depends(get_session_id)):
    from fastapi.responses import JSONResponse
    graph = load_codebase_graph(repo_key, session_id)
    if graph is None:
        raise HTTPException(status_code=404, detail="Graph not found")
    return JSONResponse(content=graph.model_dump(mode='json'))


@router.delete("/{repo_key:path}")
async def delete_parsed_graph(repo_key: str, session_id: str = Depends(get_session_id)):
    """Delete this owner's parsed graph (graph + parsed data)."""
    from app.core.db import delete_graph
    deleted = delete_graph(unquote(repo_key), session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Graph not found")
    return {"message": "Graph deleted successfully"}
