import os
import stat
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from git import Repo, GitCommandError, InvalidGitRepositoryError
import logging

logger = logging.getLogger(__name__)

# Only allow cloning from these hosts. The app analyses GitHub repos via Composio, so this
# is intentionally strict — it blocks SSRF (file://, git://, ssh, localhost/internal IPs)
# and cloning from arbitrary hosts.
ALLOWED_CLONE_HOSTS = {"github.com", "www.github.com"}


def validate_repo_url(repo_url: str) -> str:
    """Validate a clone URL before handing it to git. Returns the normalized URL or raises.

    Rejects non-https schemes and any host not in ALLOWED_CLONE_HOSTS, which prevents
    server-side request forgery (e.g. file://, git://, ssh://, http://localhost, internal IPs).
    """
    if not repo_url or not isinstance(repo_url, str):
        raise ValueError("Repository URL is required")
    url = repo_url.strip()
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"Only https:// repository URLs are allowed (got '{parsed.scheme or 'no scheme'}')")
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_CLONE_HOSTS:
        raise ValueError(f"Repository host '{host}' is not allowed. Only GitHub repositories are supported.")
    return url


class RepositoryManager:
    """Manages repository cloning and updating."""
    
    def __init__(self, base_dir: Optional[str] = None):
        """
        Initialize repository manager.
        
        Args:
            base_dir: Base directory for storing repositories. Defaults to temp directory.
        """
        if base_dir is None:
            base_dir = os.path.join(tempfile.gettempdir(), "codebase_repos")
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def get_repo_path(self, repo_url: str) -> Path:
        """Get local path for a repository."""
        # Create a safe directory name from URL
        repo_name = repo_url.split("/")[-1].replace(".git", "")
        return self.base_dir / repo_name

    @staticmethod
    def _safe_rmtree(path: Path) -> None:
        """Remove a directory tree, tolerating Windows read-only git objects (which make a plain
        shutil.rmtree raise PermissionError). Missing paths are a no-op."""
        path = Path(path)
        if not path.exists():
            return

        def _on_error(func, p, _exc):
            try:
                os.chmod(p, stat.S_IWRITE)
                func(p)
            except Exception:
                pass

        shutil.rmtree(path, onerror=_on_error)

    def _fresh_clone(self, repo_url: str, repo_path: Path, branch: Optional[str]) -> Path:
        """Clone into repo_path from scratch, cleaning up any partial dir on failure so a retry
        starts clean instead of getting wedged on a half-written .git."""
        logger.info(f"Cloning repository: {repo_url}")
        self._safe_rmtree(repo_path)
        # Shallow clone: we only need the working tree to parse, not full history. Caps
        # download size/time (DoS mitigation) on large repos.
        clone_kwargs = {"url": repo_url, "to_path": str(repo_path), "depth": 1}
        if branch:
            clone_kwargs["branch"] = branch
        try:
            Repo.clone_from(**clone_kwargs)
        except Exception:
            # A cancelled/failed clone can leave a partial directory; remove it so the next
            # attempt re-clones cleanly rather than treating the stub as an existing repo.
            self._safe_rmtree(repo_path)
            raise
        logger.info(f"Repository cloned to: {repo_path}")
        return repo_path

    def clone_or_update(self, repo_url: str, branch: Optional[str] = None) -> Path:
        """
        Clone a repository, or update an existing clone. Self-healing: if an existing checkout is
        missing or corrupted (e.g. a clone interrupted mid-way left a partial .git without HEAD),
        it is wiped and re-cloned rather than failing permanently.

        Args:
            repo_url: Repository URL
            branch: Branch to checkout (defaults to default branch)

        Returns:
            Path to the cloned repository

        Raises:
            Exception: If a fresh clone ultimately fails
        """
        repo_url = validate_repo_url(repo_url)
        repo_path = self.get_repo_path(repo_url)

        # Try to update an existing, valid clone.
        if repo_path.exists() and (repo_path / ".git").exists():
            try:
                logger.info(f"Updating repository: {repo_url}")
                repo = Repo(repo_path)  # raises InvalidGitRepositoryError on a broken .git
                repo.remotes.origin.fetch()

                refs = repo.remotes.origin.refs
                if branch and branch in [ref.name.split("/")[-1] for ref in refs]:
                    repo.git.checkout(f"origin/{branch}")
                elif branch:
                    logger.warning(f"Branch {branch} not found, using default branch")
                    repo.git.checkout(f"origin/{refs[0].name.split('/')[-1]}")
                else:
                    repo.git.checkout(f"origin/{refs[0].name.split('/')[-1]}")
                repo.head.reset(index=True, working_tree=True)
                return repo_path
            except (InvalidGitRepositoryError, GitCommandError, IndexError, ValueError) as e:
                # Corrupted/partial clone or a broken remote state — recover by re-cloning.
                logger.warning(f"Existing clone at {repo_path} is unusable ({e}); re-cloning fresh.")
                self._safe_rmtree(repo_path)

        # No usable clone — do a fresh one.
        try:
            return self._fresh_clone(repo_url, repo_path, branch)
        except GitCommandError as e:
            logger.error(f"Git error cloning {repo_url}: {e}")
            raise Exception(f"Failed to clone repository: {e}")
        except Exception as e:
            logger.error(f"Error cloning repository {repo_url}: {e}")
            raise
    
    def get_commit_hash(self, repo_path: Path) -> Optional[str]:
        """Get current commit hash of repository."""
        try:
            repo = Repo(repo_path)
            return repo.head.commit.hexsha
        except Exception as e:
            logger.error(f"Error getting commit hash: {e}")
            return None
    
    def get_branch(self, repo_path: Path) -> Optional[str]:
        """Get current branch name."""
        try:
            repo = Repo(repo_path)
            return repo.active_branch.name
        except Exception as e:
            logger.error(f"Error getting branch: {e}")
            return None
    
    def cleanup(self, repo_url: str):
        """Remove cloned repository."""
        repo_path = self.get_repo_path(repo_url)
        if repo_path.exists():
            shutil.rmtree(repo_path)
            logger.info(f"Cleaned up repository: {repo_path}")
