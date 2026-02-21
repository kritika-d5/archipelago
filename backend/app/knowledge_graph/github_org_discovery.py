"""
GitHub Organization Discovery and Repository Fetcher.
Discovers all repositories in a GitHub organization and fetches them in parallel.
"""
import os
import aiohttp
import logging
import subprocess
import time
import stat
from typing import List, Dict, Optional
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from git import Repo, GitCommandError
import shutil

from app.knowledge_graph.repo_manager import RepositoryManager

logger = logging.getLogger(__name__)


class GitHubOrgDiscovery:
    """Discovers and fetches repositories from a GitHub organization."""
    
    def __init__(self, github_token: Optional[str] = None):
        """
        Initialize GitHub organization discovery.
        
        Args:
            github_token: GitHub personal access token (optional, for private repos)
        """
        self.github_token = github_token or os.getenv("GITHUB_TOKEN")
        self.base_url = "https://api.github.com"
        self.repo_manager = RepositoryManager()
    
    async def discover_repos(self, org_name: str) -> List[Dict[str, str]]:
        """
        Discover all repositories in a GitHub organization.
        
        Args:
            org_name: GitHub organization name
            
        Returns:
            List of repository information dictionaries
        """
        repos = []
        page = 1
        per_page = 100
        
        headers = {}
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
        
        async with aiohttp.ClientSession() as session:
            while True:
                url = f"{self.base_url}/orgs/{org_name}/repos"
                params = {"page": page, "per_page": per_page, "type": "all"}
                
                try:
                    async with session.get(url, headers=headers, params=params) as response:
                        if response.status == 404:
                            # Try as user instead of organization
                            user_url = f"{self.base_url}/users/{org_name}/repos"
                            async with session.get(user_url, headers=headers, params=params) as user_response:
                                if user_response.status == 404:
                                    raise ValueError(f"Organization or user '{org_name}' not found on GitHub")
                                elif user_response.status == 200:
                                    # It's a user, use user endpoint
                                    url = user_url
                                    response = user_response
                                else:
                                    raise ValueError(f"GitHub API error: {user_response.status}")
                        elif response.status == 403:
                            raise ValueError("GitHub API rate limit exceeded or insufficient permissions. Consider setting GITHUB_TOKEN environment variable.")
                        response.raise_for_status()
                        
                        data = await response.json()
                        
                        if not data:
                            break
                        
                        for repo in data:
                            repos.append({
                                "name": repo["name"],
                                "full_name": repo["full_name"],
                                "clone_url": repo["clone_url"],
                                "ssh_url": repo["ssh_url"],
                                "default_branch": repo.get("default_branch", "main"),
                                "language": repo.get("language", "unknown"),
                                "description": repo.get("description", "")
                            })
                        
                        # Check if there are more pages
                        if len(data) < per_page:
                            break
                        
                        page += 1
                        
                except aiohttp.ClientError as e:
                    logger.error(f"Error fetching repositories: {str(e)}")
                    raise
        
        logger.info(f"Discovered {len(repos)} repositories in organization '{org_name}'")
        return repos
    
    def fetch_repo_shallow(self, repo_info: Dict[str, str], base_dir: Path) -> Optional[Path]:
        """
        Shallow clone a single repository.
        
        Args:
            repo_info: Repository information dictionary
            base_dir: Base directory for storing repos
            
        Returns:
            Path to cloned repository or None if failed
        """
        import time
        repo_name = repo_info["name"]
        clone_url = repo_info["clone_url"]
        branch = repo_info.get("default_branch", "main")
        repo_path = base_dir / repo_name
        
        try:
            # Remove existing directory if it exists (with retry for Windows)
            if repo_path.exists():
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        # Try to remove .git directory first if it exists
                        git_dir = repo_path / ".git"
                        if git_dir.exists():
                            # On Windows, .git files might be locked
                            import stat
                            def remove_readonly(func, path, exc):
                                os.chmod(path, stat.S_IWRITE)
                                func(path)
                            shutil.rmtree(git_dir, onerror=remove_readonly)
                        shutil.rmtree(repo_path, onerror=remove_readonly)
                        break
                    except PermissionError:
                        if attempt < max_retries - 1:
                            time.sleep(0.5)  # Wait before retry
                        else:
                            logger.warning(f"Could not remove existing {repo_name}, will try to clone anyway")
            
            # Ensure parent directory exists
            base_dir.mkdir(parents=True, exist_ok=True)
            
            # Shallow clone with depth=1 using git command
            logger.info(f"Cloning {repo_name} (shallow, branch: {branch})...")
            result = subprocess.run(
                [
                    "git", "clone",
                    "--depth", "1",
                    "--branch", branch,
                    "--single-branch",
                    clone_url,
                    str(repo_path)
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to clone {repo_name}: {result.stderr}")
                # Clean up partial clone
                if repo_path.exists():
                    try:
                        shutil.rmtree(repo_path, ignore_errors=True)
                    except:
                        pass
                return None
            
            logger.info(f"Successfully cloned {repo_name}")
            return repo_path
            
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout cloning {repo_name}")
            if repo_path.exists():
                try:
                    shutil.rmtree(repo_path, ignore_errors=True)
                except:
                    pass
            return None
        except Exception as e:
            logger.error(f"Error cloning {repo_name}: {str(e)}")
            # Clean up on error
            if repo_path.exists():
                try:
                    shutil.rmtree(repo_path, ignore_errors=True)
                except:
                    pass
            return None
    
    async def fetch_all_repos_parallel(
        self, 
        org_name: str, 
        base_dir: Optional[Path] = None
    ) -> Dict[str, Path]:
        """
        Discover and fetch all repositories in parallel.
        
        Args:
            org_name: GitHub organization name
            base_dir: Base directory for storing repos (defaults to temp)
            
        Returns:
            Dictionary mapping repo names to their paths
        """
        if base_dir is None:
            base_dir = Path(self.repo_manager.base_dir) / org_name
        
        # Clean up existing directory to avoid Windows file locking issues
        if base_dir.exists():
            logger.info(f"Cleaning up existing directory: {base_dir}")
            try:
                def remove_readonly(func, path, exc):
                    os.chmod(path, stat.S_IWRITE)
                    func(path)
                shutil.rmtree(base_dir, onerror=remove_readonly)
                time.sleep(1.0)  # Give Windows time to release file handles
            except Exception as e:
                logger.warning(f"Could not fully clean up {base_dir}: {str(e)}. Continuing anyway...")
        
        # Ensure base directory exists
        base_dir.mkdir(parents=True, exist_ok=True)
        
        # Discover all repositories
        repos_info = await self.discover_repos(org_name)
        
        if not repos_info:
            logger.warning(f"No repositories found in organization '{org_name}'")
            return {}
        
        # Fetch repositories with limited parallelism to avoid Windows file locking
        # Use fewer workers and add small delays to prevent file system conflicts
        repo_paths = {}
        max_workers = 2  # Further reduced to avoid Windows file locking issues
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for idx, repo_info in enumerate(repos_info):
                # Add delay between submissions to stagger operations and avoid file conflicts
                if idx > 0:
                    time.sleep(0.5)  # Increased delay to avoid Windows file locking
                future = executor.submit(self.fetch_repo_shallow, repo_info, base_dir)
                futures[future] = repo_info["name"]
            
            for future in futures:
                repo_name = futures[future]
                try:
                    repo_path = future.result()
                    if repo_path:
                        repo_paths[repo_name] = repo_path
                except Exception as e:
                    logger.error(f"Error fetching {repo_name}: {str(e)}")
        
        logger.info(f"Successfully fetched {len(repo_paths)}/{len(repos_info)} repositories")
        return repo_paths

