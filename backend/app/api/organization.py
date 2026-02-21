"""
API endpoints for GitHub organization-level analysis.
"""
import logging
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
from pathlib import Path

from app.knowledge_graph.github_org_discovery import GitHubOrgDiscovery
from app.knowledge_graph.enhanced_parser import EnhancedParser
from app.knowledge_graph.cross_repo_dependency_engine import CrossRepoDependencyEngine
from app.core.db import save_graph, save_parsed_data
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/organization", tags=["organization"])


@router.post("/analyze")
async def analyze_organization(org_name: str) -> Dict[str, Any]:
    """
    Analyze a GitHub organization and build cross-repo dependency graph.
    
    Args:
        org_name: GitHub organization name (e.g., "ShopSphere-Demo")
        
    Returns:
        Organization analysis with dependency graph
    """
    try:
        # Step 1: Discover and fetch repositories
        logger.info(f"Discovering repositories in organization: {org_name}")
        discovery = GitHubOrgDiscovery()
        repo_paths = await discovery.fetch_all_repos_parallel(org_name)
        
        if not repo_paths:
            raise HTTPException(
                status_code=404,
                detail=f"No repositories found in organization: {org_name}"
            )
        
        # Step 2: Parse each repository
        logger.info(f"Parsing {len(repo_paths)} repositories...")
        parser = EnhancedParser()
        repos_data = {}
        
        for repo_name, repo_path in repo_paths.items():
            try:
                parsed_data = parser.parse_repo(repo_path, repo_name)
                repos_data[repo_name] = parsed_data
                logger.info(f"Parsed {repo_name}: {len(parsed_data.get('api_endpoints', []))} endpoints")
            except Exception as e:
                logger.error(f"Error parsing {repo_name}: {str(e)}")
                continue
        
        if not repos_data:
            raise HTTPException(
                status_code=500,
                detail="Failed to parse any repositories"
            )
        
        # Step 3: Build cross-repo dependency graph
        logger.info("Building cross-repository dependency graph...")
        engine = CrossRepoDependencyEngine()
        dependency_graph = engine.analyze_organization(repos_data)
        
        # Step 4: Save to MongoDB
        org_key = f"org:{org_name}"
        try:
            # Save individual repo data
            save_parsed_data(org_key, repos_data)
            
            # Save dependency graph
            graph_data = {
                "nodes": dependency_graph["nodes"],
                "edges": dependency_graph["edges"],
                "violations": dependency_graph["violations"],
                "statistics": dependency_graph["statistics"]
            }
            save_graph(org_key, graph_data, timestamp=datetime.now())
            logger.info(f"Saved organization analysis to MongoDB: {org_key}")
        except Exception as e:
            logger.error(f"Failed to save to MongoDB: {str(e)}")
        
        # Step 5: Return results
        return {
            "organization": org_name,
            "repositories": list(repos_data.keys()),
            "repos_data": repos_data,
            "dependency_graph": dependency_graph,
            "summary": {
                "total_repos": len(repos_data),
                "total_endpoints": sum(len(r.get("api_endpoints", [])) for r in repos_data.values()),
                "total_services": sum(len(r.get("services", [])) for r in repos_data.values()),
                "total_dependencies": dependency_graph["statistics"]["total_dependencies"],
                "violations": len(dependency_graph["violations"])
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing organization: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing organization: {str(e)}"
        )


@router.get("/repos/{org_name}")
async def list_organization_repos(org_name: str) -> Dict[str, Any]:
    """
    List all repositories in a GitHub organization.
    
    Args:
        org_name: GitHub organization name
        
    Returns:
        List of repositories
    """
    try:
        discovery = GitHubOrgDiscovery()
        repos = await discovery.discover_repos(org_name)
        
        return {
            "organization": org_name,
            "repositories": repos,
            "count": len(repos)
        }
    except Exception as e:
        logger.error(f"Error listing repositories: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error listing repositories: {str(e)}"
        )


@router.get("/health")
async def organization_health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "organization"}

