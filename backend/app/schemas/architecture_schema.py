"""
Pydantic schemas for Architecture Studio feature.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, validator


class ArchitectureConstraints(BaseModel):
    """Constraints for architecture generation."""
    scalability: Optional[str] = Field(None, description="Scalability requirements")
    performance: Optional[str] = Field(None, description="Performance requirements")
    budget: Optional[str] = Field(None, description="Budget constraints")


class ArchitectureRequest(BaseModel):
    """Request model for architecture generation."""
    mode: str = Field(..., description="Mode: 'greenfield' or 'brownfield'")
    requirements: Optional[str] = Field(None, description="User requirements (for greenfield)")
    repo_key: Optional[str] = Field(None, description="Repository key (for brownfield)")
    constraints: Optional[ArchitectureConstraints] = Field(None, description="System constraints")
    
    @validator('mode')
    def validate_mode(cls, v):
        if v.lower() not in ['greenfield', 'brownfield']:
            raise ValueError("Mode must be 'greenfield' or 'brownfield'")
        return v.lower()


class Service(BaseModel):
    """Service definition in architecture."""
    name: str = Field(..., description="Service name")
    description: str = Field(..., description="Service description")
    technology: str = Field(..., description="Technology stack")
    responsibilities: List[str] = Field(default_factory=list, description="Service responsibilities")
    endpoints: List[str] = Field(default_factory=list, description="API endpoints")


class Infrastructure(BaseModel):
    """Infrastructure configuration."""
    cloud_provider: Optional[str] = Field(None, description="Cloud provider")
    compute: Optional[Dict[str, Any]] = Field(None, description="Compute resources")
    storage: Optional[Dict[str, Any]] = Field(None, description="Storage configuration")
    networking: Optional[Dict[str, Any]] = Field(None, description="Networking setup")
    monitoring: Optional[Dict[str, Any]] = Field(None, description="Monitoring tools")


class DataArchitecture(BaseModel):
    """Data architecture configuration."""
    databases: List[Dict[str, Any]] = Field(default_factory=list, description="Database configurations")
    data_flow: Optional[str] = Field(None, description="Data flow description")
    storage_strategy: Optional[str] = Field(None, description="Storage strategy")


class ArchitectureModifyRequest(BaseModel):
    """Request model for modifying an existing blueprint."""
    current_blueprint: Dict[str, Any] = Field(..., description="Current blueprint to modify")
    modification_request: str = Field(..., description="User's modification request")


class ArchitectureBlueprint(BaseModel):
    """Architecture blueprint response model."""
    mode: str = Field(..., description="Mode: greenfield or brownfield")
    architecture_style: str = Field(..., description="Detected or recommended architecture style")
    system_overview: str = Field(..., description="System overview description")
    services: List[Service] = Field(default_factory=list, description="List of services")
    infrastructure: Infrastructure = Field(..., description="Infrastructure configuration")
    data_architecture: DataArchitecture = Field(..., description="Data architecture")
    detected_issues: List[str] = Field(default_factory=list, description="Detected issues (brownfield)")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations")
    tradeoffs: List[str] = Field(default_factory=list, description="Tradeoffs and considerations")
    migration_plan: List[str] = Field(default_factory=list, description="Migration plan (brownfield)")
    mermaid_diagram: str = Field(default="", description="Mermaid diagram code")
    confidence_score: float = Field(default=0.8, ge=0.0, le=1.0, description="Confidence score")

