"""
API endpoints for Architecture Studio feature.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any

from app.schemas.architecture_schema import ArchitectureRequest, ArchitectureBlueprint, ArchitectureModifyRequest
from app.agents.architecture_agent import ArchitectureAgent
from app.core.db import get_graph, get_parsed_data
from app.core.session import get_session_id
from app.core.llm import LLMService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/architecture", tags=["architecture"])

# Initialize LLM service
try:
    llm_service = LLMService()
except Exception as e:
    logger.warning(f"LLM service initialization failed: {e}. Architecture features will not work.")
    llm_service = None


@router.post("/generate", response_model=ArchitectureBlueprint)
async def generate_architecture(request: ArchitectureRequest, session_id: str = Depends(get_session_id)) -> ArchitectureBlueprint:
    """
    Generate architecture blueprint.
    
    Args:
        request: Architecture generation request
        
    Returns:
        ArchitectureBlueprint with generated architecture
    """
    if not llm_service:
        raise HTTPException(status_code=503, detail="LLM service not available")
    
    try:
        agent = ArchitectureAgent(llm_service)
        mode = agent.detect_mode(request.mode, request.repo_key)
        
        if mode == "greenfield":
            # Greenfield mode
            if not request.requirements:
                raise HTTPException(
                    status_code=400,
                    detail="Requirements are required for greenfield mode"
                )
            
            constraints_dict = request.constraints.dict() if request.constraints else {}
            prompt = agent.build_greenfield_prompt(request.requirements, constraints_dict)
            
        else:
            # Brownfield mode
            if not request.repo_key:
                raise HTTPException(
                    status_code=400,
                    detail="repo_key is required for brownfield mode"
                )
            
            # Fetch graph and parsed data from MongoDB
            graph_data = get_graph(request.repo_key, session_id)
            if not graph_data:
                raise HTTPException(
                    status_code=404,
                    detail=f"Graph not found for repo_key: {request.repo_key}"
                )

            parsed_data = get_parsed_data(request.repo_key, session_id)
            system_summary = agent.summarize_graph(graph_data, parsed_data)
            
            user_intent = request.requirements or "Optimize the existing architecture"
            prompt = agent.build_brownfield_prompt(system_summary, user_intent)
        
        # Call LLM
        logger.info(f"Generating architecture blueprint in {mode} mode")
        json_response = agent.call_llm(prompt)
        
        # Validate and parse response
        blueprint = agent.validate_blueprint_schema(json_response)
        
        logger.info(f"Architecture blueprint generated successfully with confidence: {blueprint.confidence_score}")
        return blueprint
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid response format: {str(e)}")
    except Exception as e:
        logger.error(f"Error generating architecture: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error generating architecture blueprint: {str(e)}"
        )


@router.post("/modify", response_model=ArchitectureBlueprint)
async def modify_architecture(request: ArchitectureModifyRequest) -> ArchitectureBlueprint:
    """Modify an existing blueprint based on user feedback."""
    if not llm_service:
        raise HTTPException(status_code=503, detail="LLM service not available")
    try:
        agent = ArchitectureAgent(llm_service)
        prompt = agent.build_modify_prompt(
            request.current_blueprint,
            request.modification_request
        )
        json_response = agent.call_llm(prompt)
        blueprint = agent.validate_blueprint_schema(json_response)
        return blueprint
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error modifying architecture: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def architecture_health():
    """Health check endpoint for architecture service."""
    return {
        "status": "healthy",
        "service": "architecture",
        "llm_available": llm_service is not None
    }

