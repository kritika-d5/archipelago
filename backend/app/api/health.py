"""
Health check endpoint.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("/")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "Knowledge Graph System"}
