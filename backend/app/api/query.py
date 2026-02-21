"""
API endpoints for LLM queries and what-if analysis.
"""
import logging
from fastapi import APIRouter, HTTPException, Query
from urllib.parse import unquote

from app.schemas.graph_schema import QueryRequest, QueryResponse, WhatIfRequest, WhatIfResponse
from app.core.llm import LLMService
from app.core.db import get_graph, get_parsed_data
from app.api.parse import parsed_graphs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/query", tags=["query"])

# Initialize LLM service
try:
    llm_service = LLMService()
except Exception as e:
    logger.warning(f"LLM service initialization failed: {e}. Some endpoints may not work.")
    llm_service = None


def get_organization_data(org_key: str) -> dict:
    """
    Fetch organization data from MongoDB.
    
    Args:
        org_key: Organization key (format: org:org_name)
        
    Returns:
        Organization data with repos and dependency graph
    """
    try:
        # Get the parsed data (individual repo JSONs)
        parsed_doc = get_parsed_data(org_key)
        repos_data = parsed_doc.get("parsed_data", {}) if parsed_doc else {}
        
        # Get the main dependency graph
        graph_doc = get_graph(org_key)
        graph_data = graph_doc.get("graph_data", {}) if graph_doc else {}
        
        org_data = {
            "repos_data": repos_data,
            "dependency_graph": graph_data
        }
        
        logger.info(f"Loaded organization data: {len(repos_data)} repos, {len(graph_data.get('edges', []))} dependencies")
        return org_data
    except Exception as e:
        logger.error(f"Error fetching organization data: {e}")
        raise


@router.post("/ask", response_model=QueryResponse)
async def ask_question(request: QueryRequest, repo_key: str = Query(..., description="Repository key")):
    """
    Ask a question about the codebase using LLM.
    
    Supports both single repositories and organizations.
    
    Args:
        repo_key: Repository key (query parameter)
            - Single repo: {repo_url}:{branch}
            - Organization: org:{org_name}
        request: Query request (body)
            - query: The question to ask
            - include_code: Whether to include code snippets
            - max_context_elements: Max elements to include
    """
    logger.info(f"Query received for repo_key: {repo_key}")
    logger.info(f"Question: {request.query}")
    
    if not llm_service:
        logger.error("LLM service not available")
        raise HTTPException(status_code=503, detail="LLM service not available. Check GROQ_API_KEY in .env")
    
    try:
        # Check if it's an organization query
        if repo_key.startswith("org:") or repo_key.startswith("org%3A"):
            decoded_key = unquote(repo_key)
            logger.info(f"Processing organization query: {decoded_key}")
            
            # Fetch organization data from MongoDB
            org_data = get_organization_data(decoded_key)
            
            if not org_data.get("repos_data"):
                raise HTTPException(status_code=404, detail=f"Organization data not found: {decoded_key}")
            
            # Process with organization-level LLM method
            response = llm_service.answer_org_query(org_data, request)
            return response
        
        # Single repository query
        if repo_key not in parsed_graphs:
            logger.error(f"Graph not found for key: {repo_key}")
            raise HTTPException(status_code=404, detail=f"Graph not found for key: {repo_key}")
        
        graph_data = parsed_graphs[repo_key]["graph"]
        
        if graph_data is None:
            logger.error(f"Graph data is None for key: {repo_key}")
            raise HTTPException(status_code=400, detail=f"Graph data not available for key: {repo_key}")
        
        logger.info(f"Processing single repository query: {repo_key}")
        response = llm_service.answer_query(graph_data, request)
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error answering query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


@router.post("/what-if", response_model=WhatIfResponse)
async def what_if_analysis(request: WhatIfRequest, repo_key: str = Query(..., description="Repository key")):
    """
    Perform what-if analysis on the codebase.
    
    Supports both single repositories and organizations.
    
    Args:
        repo_key: Repository key (query parameter)
            - Single repo: {repo_url}:{branch}
            - Organization: org:{org_name}
        request: What-if request (body)
            - scenario: Description of the change
            - include_impact_chain: Whether to include impact chain
            - max_depth: Maximum depth for impact analysis
    """
    logger.info(f"What-if analysis received for repo_key: {repo_key}")
    logger.info(f"Scenario: {request.scenario}")
    
    if not llm_service:
        logger.error("LLM service not available")
        raise HTTPException(status_code=503, detail="LLM service not available. Check GROQ_API_KEY in .env")
    
    try:
        # Check if it's an organization query
        if repo_key.startswith("org:") or repo_key.startswith("org%3A"):
            decoded_key = unquote(repo_key)
            logger.info(f"Processing organization what-if analysis: {decoded_key}")
            
            # Fetch organization data from MongoDB
            org_data = get_organization_data(decoded_key)
            
            if not org_data.get("repos_data"):
                raise HTTPException(status_code=404, detail=f"Organization data not found: {decoded_key}")
            
            # Process with organization-level LLM method
            response = llm_service.analyze_org_what_if(org_data, request)
            return response
        
        # Single repository what-if
        if repo_key not in parsed_graphs:
            logger.error(f"Graph not found for key: {repo_key}")
            raise HTTPException(status_code=404, detail=f"Graph not found for key: {repo_key}")
        
        graph_data = parsed_graphs[repo_key]["graph"]
        
        if graph_data is None:
            logger.error(f"Graph data is None for key: {repo_key}")
            raise HTTPException(status_code=400, detail=f"Graph data not available for key: {repo_key}")
        
        logger.info(f"Processing single repository what-if analysis: {repo_key}")
        response = llm_service.analyze_what_if(graph_data, request)
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in what-if analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error performing analysis: {str(e)}")
