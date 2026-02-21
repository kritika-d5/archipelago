from fastapi import FastAPI
from app.api import architecture, graph, health

app = FastAPI(title="Living Knowledge Graph System")

app.include_router(architecture.router)
app.include_router(graph.router)
app.include_router(health.router)

@app.get("/")
def root():
    return {"message": "Knowledge Graph System Running 🚀"}