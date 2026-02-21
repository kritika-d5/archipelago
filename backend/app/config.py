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

# Composio (optional - for GitHub/Notion/Slack OAuth)
COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY") or os.getenv("COMPOSIO_EKEY")