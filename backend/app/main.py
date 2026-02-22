import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import parse, graph, query, health, architecture, organization, integrations, learning_path
from app.config import LOG_LEVEL

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = FastAPI(title="Living Knowledge Graph System")

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(parse.router)
app.include_router(graph.router)
app.include_router(query.router)
app.include_router(health.router)
app.include_router(architecture.router)
app.include_router(organization.router)
app.include_router(integrations.router)
app.include_router(learning_path.router)

@app.get("/")
def root():
    return {"message": "Knowledge Graph System Running 🚀"}