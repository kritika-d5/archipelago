"""
Core utility functions.
"""
import os
from pathlib import Path
from typing import Optional
from git import Repo


def clone_or_pull_repo(repo_url: str, local_path: str) -> bool:
    """
    Clone a repository if it doesn't exist, or pull latest changes if it does.
    
    Args:
        repo_url: Git repository URL
        local_path: Local path where repository should be cloned
        
    Returns:
        True if successful, False otherwise
    """
    try:
        local_path_obj = Path(local_path)
        
        if not local_path_obj.exists():
            # Clone the repository
            os.makedirs(local_path_obj.parent, exist_ok=True)
            Repo.clone_from(repo_url, str(local_path))
        else:
            # Pull latest changes
            repo = Repo(str(local_path))
            repo.remotes.origin.pull()
        
        return True
    except Exception as e:
        print(f"Error in clone_or_pull_repo: {str(e)}")
        return False

