import os
from pathlib import Path
from dotenv import load_dotenv

# Get backend directory path
BACKEND_DIR = Path(__file__).parent.parent
ENV_FILE = BACKEND_DIR / ".env"

# Load environment variables from .env file in backend directory
if ENV_FILE.exists():
    load_dotenv(dotenv_path=ENV_FILE)
else:
    load_dotenv()

# Groq API Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Repository storage
REPO_STORAGE_DIR = os.getenv("REPO_STORAGE_DIR", None)  # None = use temp directory

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# API Configuration
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# MongoDB Configuration
MONGO_URI = os.getenv("MONGO_URI")

# CORS: comma-separated origins (e.g. https://app.vercel.app,https://yourdomain.com)
# Local dev defaults are merged in main.py if unset.
_raw_cors = os.getenv("CORS_ORIGINS", "")
CORS_ORIGINS = [o.strip() for o in _raw_cors.split(",") if o.strip()]

# Where the browser loads the React app (used for Composio OAuth redirect to /connect-callback).
# Production: https://your-app.vercel.app  (no trailing slash)
FRONTEND_PUBLIC_URL = (os.getenv("FRONTEND_PUBLIC_URL") or "http://localhost:3000").rstrip("/")

# Composio (optional - for GitHub/Notion/Slack OAuth)
COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY") or os.getenv("COMPOSIO_EKEY")

# Auth config IDs per toolkit, from app.composio.dev -> Auth Configs (look like "ac_...").
# Required for the OAuth connect flow (connected_accounts.link). One per integration.
COMPOSIO_AUTH_CONFIGS = {
    "github": os.getenv("COMPOSIO_AUTH_CONFIG_GITHUB"),
    "notion": os.getenv("COMPOSIO_AUTH_CONFIG_NOTION"),
    "slack": os.getenv("COMPOSIO_AUTH_CONFIG_SLACK"),
}