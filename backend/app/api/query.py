"""
API endpoints for LLM queries and what-if analysis.
"""
import logging
from fastapi import APIRouter, HTTPException, Query

from app.schemas.graph_schema import QueryRequest, QueryResponse, WhatIfRequest, WhatIfResponse
from app.core.llm import LLMService
from app.api.parse import parsed_graphs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/query", tags=["query"])

# Initialize LLM service
try:
    llm_service = LLMService()
except Exception as e:
    logger.warning(f"LLM service initialization failed: {e}. Some endpoints may not work.")
    llm_service = None


@router.post("/ask", response_model=QueryResponse)
async def ask_question(request: QueryRequest, repo_key: str = Query(..., description="Repository key")):
    """
    Ask a question about the codebase using LLM.
    
    Args:
        repo_key: Repository key (query parameter)
        request: Query request (body)
    """
    if repo_key not in parsed_graphs:
        raise HTTPException(status_code=404, detail="Graph not found")
    
    if not llm_service:
        raise HTTPException(status_code=503, detail="LLM service not available")
    
    graph_data = parsed_graphs[repo_key]["graph"]
    
    try:
        response = llm_service.answer_query(graph_data, request)
        return response
    except Exception as e:
        logger.error(f"Error answering query: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


@router.post("/what-if", response_model=WhatIfResponse)
async def what_if_analysis(request: WhatIfRequest, repo_key: str = Query(..., description="Repository key")):
    """
    Perform what-if analysis on the codebase.
    
    Args:
        repo_key: Repository key (query parameter)
        request: What-if request (body)
    """
    if repo_key not in parsed_graphs:
        raise HTTPException(status_code=404, detail="Graph not found")
    
    if not llm_service:
        raise HTTPException(status_code=503, detail="LLM service not available")
    
    graph_data = parsed_graphs[repo_key]["graph"]
    
    try:
        response = llm_service.analyze_what_if(graph_data, request)
        return response
    except Exception as e:
        logger.error(f"Error in what-if analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Error performing analysis: {str(e)}")
