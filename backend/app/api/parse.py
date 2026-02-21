import time
import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any
from app.schemas.graph_schema import ParsingRequest, ParsingResponse
from app.knowledge_graph.repo_manager import RepositoryManager
from app.knowledge_graph.code_parser import CodeParser

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/parse", tags=["parsing"])
parsed_graphs: Dict[str, Any] = {}


@router.post("/", response_model=ParsingResponse)
async def parse_repository(request: ParsingRequest, background_tasks: BackgroundTasks):
    start_time = time.time()
    
    try:
        repo_manager = RepositoryManager()
        parser = CodeParser(
            include_tests=request.include_tests,
            include_vendor=request.include_vendor,
            languages=request.languages,
            max_file_size=request.max_file_size
        )
        
        logger.info(f"Cloning/updating repository: {request.repository_url}")
        repo_path = repo_manager.clone_or_update(request.repository_url, request.branch)
        
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
async def list_parsed_graphs():
    return {
        "graphs": [
            {
                "key": key,
                "repository": data["graph"].metadata.repository_name,
                "parsed_at": data["parsed_at"]
            }
            for key, data in parsed_graphs.items()
        ]
    }


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
