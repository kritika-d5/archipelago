"""
API endpoints for LLM queries and what-if analysis.
"""
import logging
from fastapi import APIRouter, HTTPException, Query
from urllib.parse import unquote

from pydantic import BaseModel
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


class DocDiffRequest(BaseModel):
    documentation: str


@router.post("/doc-diff")
async def doc_vs_codebase_diff(request: DocDiffRequest, repo_key: str = Query(..., description="Repository key")):
    """Compare documentation with codebase and suggest documentation edits."""
    if not llm_service:
        raise HTTPException(status_code=503, detail="LLM service not available")
    decoded_key = unquote(repo_key)
    codebase_summary = ""
    try:
        parsed_doc = get_parsed_data(decoded_key)
        if parsed_doc:
            pd = parsed_doc.get("parsed_data", {})
            if decoded_key.startswith("org:"):
                parts = []
                for repo_name, repo_pd in (pd.items() if isinstance(pd, dict) else []):
                    rp = repo_pd if isinstance(repo_pd, dict) else {}
                    parts.append(f"Repo {repo_name}: services {rp.get('services',[])}, endpoints {rp.get('api_endpoints',[])}")
                codebase_summary = "Organization. " + "; ".join(parts[:10])
            else:
                metas = pd.get("metadata", {})
                codebase_summary = f"Repo: {metas.get('repository_name','')}. Services: {pd.get('services',[])}. Endpoints: {pd.get('api_endpoints',[])}. Schemas: {pd.get('database_schemas',[])}."
        graph_doc = get_graph(decoded_key)
        if graph_doc:
            gd = graph_doc.get("graph_data", {})
            if not gd and graph_doc.get("nodes"):
                gd = graph_doc
            nodes = (gd or {}).get("nodes", [])[:30]
            edges = (gd or {}).get("edges", [])[:50]
            codebase_summary += f" Graph nodes: {[n.get('id') for n in nodes]}. Edges sample: {[(e.get('source'),e.get('target')) for e in edges[:20]]}."
    except Exception as e:
        logger.warning(f"Could not get codebase: {e}")
    if not codebase_summary:
        codebase_summary = "Codebase structure unavailable."
    prompt = f"""You are a technical documentation specialist. Compare the following documentation with the actual codebase and suggest specific edits to make the documentation accurate.

DOCUMENTATION:
{request.documentation[:4000]}

CODEBASE SUMMARY:
{codebase_summary[:4000]}

Provide:
1. List of differences (what in docs is wrong or missing compared to code)
2. Specific suggested edits for the documentation (quote old text, propose new text)
3. Any sections to add that are missing

Format as markdown. Be concise and actionable."""
    try:
        response = llm_service.client.chat.completions.create(
            model=llm_service.model,
            messages=[
                {"role": "system", "content": "You compare documentation with codebases and suggest precise edits."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000
        )
        analysis = response.choices[0].message.content
        structured_prompt = f"""Based on the doc vs code comparison, return a JSON array of suggestions. Each: {{"id": "unique_id", "type": "add"|"update"|"fix", "description": "brief description", "current": "current text if update", "suggested": "new text to add/use"}}.
Return ONLY a JSON array, no other text. Example: [{{"id":"1","type":"add","description":"Missing API X","current":"","suggested":"Add section: API X handles..."}}]"""
        try:
            struct_resp = llm_service.client.chat.completions.create(
                model=llm_service.model,
                messages=[
                    {"role": "system", "content": "You return only valid JSON arrays. No markdown, no explanation."},
                    {"role": "user", "content": f"Doc: {request.documentation[:2000]}\nCodebase: {codebase_summary[:2000]}\n\n{structured_prompt}\n\nAnalysis so far:\n{analysis}\n\nExtract 1-5 specific actionable suggestions as JSON array:"}
                ],
                temperature=0.2,
                max_tokens=1000
            )
            import json
            struct_text = struct_resp.choices[0].message.content.strip()
            if struct_text.startswith("```"): struct_text = struct_text.split("```")[1].replace("json","").strip()
            items = json.loads(struct_text)
            if not isinstance(items, list): items = []
            for i, it in enumerate(items):
                if not isinstance(it, dict): items[i] = {"id": str(i), "type": "fix", "description": str(it), "current": "", "suggested": str(it)}
                elif "id" not in it: it["id"] = str(i)
        except Exception:
            items = []
        return {
            "suggestions": analysis,
            "structured": items[:10],
            "has_differences": "suggest" in analysis.lower() or "edit" in analysis.lower() or "missing" in analysis.lower() or len(items) > 0
        }
    except Exception as e:
        logger.error(f"Doc diff failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
