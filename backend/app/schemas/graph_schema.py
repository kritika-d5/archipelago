"""
Comprehensive Pydantic schemas for codebase parsing and knowledge graph.
All schemas include strict validation for Groq API integration.
"""
from typing import List, Optional, Dict, Any, Set
from enum import Enum
from pydantic import BaseModel, Field, validator
from datetime import datetime


class DependencyType(str, Enum):
    """Types of dependencies between code elements."""
    IMPORT = "import"
    INHERITANCE = "inheritance"
    COMPOSITION = "composition"
    CALL = "call"
    REFERENCE = "reference"
    DATA_FLOW = "data_flow"
    CONTROL_FLOW = "control_flow"
    USES_AGENT = "uses_agent"
    TRIGGERS_WORKFLOW = "triggers_workflow"
    QUERIES_DATABASE = "queries_database"
    WRITES_TO_DATABASE = "writes_to_database"
    READS_FROM_DATABASE = "reads_from_database"


class CodeElementType(str, Enum):
    """Types of code elements."""
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    VARIABLE = "variable"
    CONSTANT = "constant"
    INTERFACE = "interface"
    ENUM = "enum"
    TYPE = "type"
    AGENT = "agent"
    WORKFLOW = "workflow"
    DATABASE_SCHEMA = "database_schema"
    DATABASE_TABLE = "database_table"
    DATABASE_COLUMN = "database_column"
    API_ENDPOINT = "api_endpoint"


class Language(str, Enum):
    """Supported programming languages."""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    CPP = "cpp"
    GO = "go"
    RUST = "rust"
    UNKNOWN = "unknown"


class DatabaseLanguage(str, Enum):
    """Supported database languages and technologies."""
    SQL = "sql"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLITE = "sqlite"
    MONGODB = "mongodb"
    REDIS = "redis"
    CASSANDRA = "cassandra"
    ELASTICSEARCH = "elasticsearch"
    NEO4J = "neo4j"
    UNKNOWN = "unknown"


class Parameter(BaseModel):
    """Function/method parameter."""
    name: str = Field(..., description="Parameter name")
    type: Optional[str] = Field(None, description="Parameter type annotation")
    default_value: Optional[str] = Field(None, description="Default value if any")
    is_optional: bool = Field(False, description="Whether parameter is optional")
    description: Optional[str] = Field(None, description="Parameter description")


class ReturnType(BaseModel):
    """Function/method return type."""
    type: Optional[str] = Field(None, description="Return type annotation")
    description: Optional[str] = Field(None, description="Return value description")
    is_async: bool = Field(False, description="Whether function is async")


class CodeElement(BaseModel):
    """Base code element with common properties."""
    id: str = Field(..., description="Unique identifier for the element")
    name: str = Field(..., description="Element name")
    type: CodeElementType = Field(..., description="Type of code element")
    file_path: str = Field(..., description="File path relative to repo root")
    line_start: int = Field(..., description="Starting line number")
    line_end: int = Field(..., description="Ending line number")
    language: Language = Field(..., description="Programming language")
    docstring: Optional[str] = Field(None, description="Documentation string")
    code_snippet: Optional[str] = Field(None, description="Code snippet (first 500 chars)")
    full_code: Optional[str] = Field(None, description="Full code content")
    complexity: Optional[int] = Field(None, description="Cyclomatic complexity")
    parameters: List[Parameter] = Field(default_factory=list, description="Function/method parameters")
    return_type: Optional[ReturnType] = Field(None, description="Return type information")
    decorators: List[str] = Field(default_factory=list, description="Decorators applied")
    access_modifier: Optional[str] = Field(None, description="Access modifier (public, private, protected)")
    is_abstract: bool = Field(False, description="Whether element is abstract")
    is_static: bool = Field(False, description="Whether element is static")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @validator('line_end')
    def line_end_after_start(cls, v, values):
        if 'line_start' in values and v < values['line_start']:
            raise ValueError('line_end must be >= line_start')
        return v


class Dependency(BaseModel):
    """Dependency relationship between code elements."""
    source_id: str = Field(..., description="Source element ID")
    target_id: str = Field(..., description="Target element ID")
    dependency_type: DependencyType = Field(..., description="Type of dependency")
    strength: float = Field(1.0, ge=0.0, le=1.0, description="Dependency strength (0-1)")
    context: Optional[str] = Field(None, description="Context of the dependency")
    line_number: Optional[int] = Field(None, description="Line number where dependency occurs")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional dependency metadata")


class Module(BaseModel):
    """Module/package information."""
    id: str = Field(..., description="Unique module identifier")
    name: str = Field(..., description="Module name")
    file_path: str = Field(..., description="File path")
    package_path: Optional[str] = Field(None, description="Package path (e.g., app.core.utils)")
    language: Language = Field(..., description="Programming language")
    imports: List[str] = Field(default_factory=list, description="List of imported modules/packages")
    exports: List[str] = Field(default_factory=list, description="List of exported elements")
    dependencies: List[str] = Field(default_factory=list, description="External dependencies")
    element_ids: List[str] = Field(default_factory=list, description="IDs of elements in this module")
    docstring: Optional[str] = Field(None, description="Module-level documentation")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional module metadata")


class ClassInfo(BaseModel):
    """Class-specific information."""
    base_classes: List[str] = Field(default_factory=list, description="Parent class names")
    interfaces: List[str] = Field(default_factory=list, description="Implemented interfaces")
    methods: List[str] = Field(default_factory=list, description="Method IDs in this class")
    properties: List[str] = Field(default_factory=list, description="Property IDs in this class")
    class_variables: List[str] = Field(default_factory=list, description="Class variable IDs")
    instance_variables: List[str] = Field(default_factory=list, description="Instance variable IDs")


class AgentInfo(BaseModel):
    """Agent-specific information."""
    agent_type: str = Field(..., description="Type of agent (LLM, RAG, Tool-using, etc.)")
    tools: List[str] = Field(default_factory=list, description="Tool IDs available to agent")
    workflows: List[str] = Field(default_factory=list, description="Workflow IDs this agent participates in")
    capabilities: List[str] = Field(default_factory=list, description="Agent capabilities")
    llm_provider: Optional[str] = Field(None, description="LLM provider (OpenAI, Groq, etc.)")
    model_name: Optional[str] = Field(None, description="Model name used by agent")


class WorkflowInfo(BaseModel):
    """Workflow-specific information."""
    workflow_type: str = Field(..., description="Type of workflow (sequential, parallel, conditional, etc.)")
    steps: List[str] = Field(default_factory=list, description="Step IDs in workflow")
    agents: List[str] = Field(default_factory=list, description="Agent IDs participating in workflow")
    triggers: List[str] = Field(default_factory=list, description="Trigger conditions")
    outputs: List[str] = Field(default_factory=list, description="Output element IDs")


class DatabaseColumn(BaseModel):
    """Database column information."""
    name: str = Field(..., description="Column name")
    data_type: str = Field(..., description="Column data type")
    is_nullable: bool = Field(True, description="Whether column allows NULL")
    is_primary_key: bool = Field(False, description="Whether column is primary key")
    is_foreign_key: bool = Field(False, description="Whether column is foreign key")
    foreign_key_table: Optional[str] = Field(None, description="Referenced table if foreign key")
    foreign_key_column: Optional[str] = Field(None, description="Referenced column if foreign key")
    default_value: Optional[str] = Field(None, description="Default value")
    constraints: List[str] = Field(default_factory=list, description="Additional constraints")


class DatabaseTable(BaseModel):
    """Database table information."""
    name: str = Field(..., description="Table name")
    schema_name: Optional[str] = Field(None, description="Schema name")
    columns: List[DatabaseColumn] = Field(default_factory=list, description="Table columns")
    indexes: List[str] = Field(default_factory=list, description="Index names")
    primary_keys: List[str] = Field(default_factory=list, description="Primary key column names")
    foreign_keys: Dict[str, str] = Field(default_factory=dict, description="Foreign key mappings")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional table metadata")


class DatabaseSchema(BaseModel):
    """Database schema information."""
    name: str = Field(..., description="Schema/database name")
    database_language: DatabaseLanguage = Field(..., description="Database language/technology")
    tables: List[DatabaseTable] = Field(default_factory=list, description="Tables in schema")
    connection_string: Optional[str] = Field(None, description="Connection string pattern")
    orm_framework: Optional[str] = Field(None, description="ORM framework used (SQLAlchemy, Django ORM, etc.)")
    migration_files: List[str] = Field(default_factory=list, description="Migration file paths")


class CodebaseMetadata(BaseModel):
    """Overall codebase metadata."""
    repository_url: Optional[str] = Field(None, description="Repository URL")
    repository_name: str = Field(..., description="Repository name")
    branch: Optional[str] = Field(None, description="Git branch")
    commit_hash: Optional[str] = Field(None, description="Current commit hash")
    parsed_at: datetime = Field(default_factory=datetime.now, description="Parsing timestamp")
    total_files: int = Field(..., description="Total number of files parsed")
    total_lines: int = Field(..., description="Total lines of code")
    languages: List[Language] = Field(default_factory=list, description="Languages found in codebase")
    database_languages: List[DatabaseLanguage] = Field(default_factory=list, description="Database languages/technologies used")
    main_entry_points: List[str] = Field(default_factory=list, description="Main entry point file paths")
    test_files: List[str] = Field(default_factory=list, description="Test file paths")
    config_files: List[str] = Field(default_factory=list, description="Configuration file paths")
    docker_files: List[str] = Field(default_factory=list, description="Docker-related file paths")
    kubernetes_files: List[str] = Field(default_factory=list, description="Kubernetes-related file paths")
    dependencies: Dict[str, str] = Field(default_factory=dict, description="External dependencies with versions")


class CodebaseGraph(BaseModel):
    """Complete codebase knowledge graph structure."""
    metadata: CodebaseMetadata = Field(..., description="Codebase metadata")
    modules: List[Module] = Field(default_factory=list, description="All modules in the codebase")
    elements: List[CodeElement] = Field(default_factory=list, description="All code elements")
    dependencies: List[Dependency] = Field(default_factory=list, description="All dependencies")
    class_info: Dict[str, ClassInfo] = Field(default_factory=dict, description="Class-specific information by element ID")
    agent_info: Dict[str, AgentInfo] = Field(default_factory=dict, description="Agent-specific information by element ID")
    workflow_info: Dict[str, WorkflowInfo] = Field(default_factory=dict, description="Workflow-specific information by element ID")
    database_schemas: List[DatabaseSchema] = Field(default_factory=list, description="Database schemas in codebase")
    
    # Indexes for fast lookup
    element_index: Dict[str, CodeElement] = Field(default_factory=dict, description="Element ID to element mapping")
    module_index: Dict[str, Module] = Field(default_factory=dict, description="Module ID to module mapping")
    file_index: Dict[str, List[str]] = Field(default_factory=dict, description="File path to element IDs mapping")
    agent_index: Dict[str, str] = Field(default_factory=dict, description="Agent name to element ID mapping")
    workflow_index: Dict[str, str] = Field(default_factory=dict, description="Workflow name to element ID mapping")
    database_index: Dict[str, DatabaseSchema] = Field(default_factory=dict, description="Database name to schema mapping")
    
    def build_indexes(self):
        """Build indexes for fast lookups."""
        self.element_index = {elem.id: elem for elem in self.elements}
        self.module_index = {mod.id: mod for mod in self.modules}
        
        # Build file index
        self.file_index = {}
        for elem in self.elements:
            if elem.file_path not in self.file_index:
                self.file_index[elem.file_path] = []
            self.file_index[elem.file_path].append(elem.id)
        
        # Build module file index
        for mod in self.modules:
            if mod.file_path not in self.file_index:
                self.file_index[mod.file_path] = []
    
    def get_element_by_id(self, element_id: str) -> Optional[CodeElement]:
        """Get element by ID."""
        return self.element_index.get(element_id)
    
    def get_elements_by_file(self, file_path: str) -> List[CodeElement]:
        """Get all elements in a file."""
        element_ids = self.file_index.get(file_path, [])
        return [self.element_index[eid] for eid in element_ids if eid in self.element_index]
    
    def get_dependencies_for_element(self, element_id: str) -> List[Dependency]:
        """Get all dependencies for an element."""
        return [dep for dep in self.dependencies if dep.source_id == element_id]
    
    def get_dependents_of_element(self, element_id: str) -> List[Dependency]:
        """Get all elements that depend on this element."""
        return [dep for dep in self.dependencies if dep.target_id == element_id]
    
    def get_agents(self) -> List[CodeElement]:
        """Get all agent elements."""
        return [elem for elem in self.elements if elem.type == CodeElementType.AGENT]
    
    def get_workflows(self) -> List[CodeElement]:
        """Get all workflow elements."""
        return [elem for elem in self.elements if elem.type == CodeElementType.WORKFLOW]
    
    def get_database_schemas(self) -> List[DatabaseSchema]:
        """Get all database schemas."""
        return self.database_schemas
    
    def get_database_tables(self) -> List[DatabaseTable]:
        """Get all database tables across all schemas."""
        tables = []
        for schema in self.database_schemas:
            tables.extend(schema.tables)
        return tables


class ParsingRequest(BaseModel):
    """Request model for parsing a repository."""
    repository_url: str = Field(..., description="Repository URL to parse")
    branch: Optional[str] = Field(None, description="Git branch to parse")
    include_tests: bool = Field(True, description="Whether to include test files")
    include_vendor: bool = Field(False, description="Whether to include vendor/node_modules")
    languages: Optional[List[Language]] = Field(None, description="Specific languages to parse")
    max_file_size: int = Field(1000000, description="Maximum file size in bytes to parse")


class ParsingResponse(BaseModel):
    """Response model for parsing operation."""
    success: bool = Field(..., description="Whether parsing was successful")
    graph: Optional[CodebaseGraph] = Field(None, description="Parsed codebase graph")
    error: Optional[str] = Field(None, description="Error message if parsing failed")
    parsing_time: float = Field(..., description="Time taken to parse in seconds")
    files_parsed: int = Field(..., description="Number of files parsed")


class QueryRequest(BaseModel):
    """Request model for LLM queries."""
    query: str = Field(..., min_length=1, description="User query about the codebase")
    context_element_ids: Optional[List[str]] = Field(None, description="Specific element IDs to focus on")
    include_code: bool = Field(True, description="Whether to include code snippets in context")
    max_context_elements: int = Field(10, ge=1, le=50, description="Maximum context elements to include")


class QueryResponse(BaseModel):
    """Response model for LLM queries."""
    answer: str = Field(..., description="LLM-generated answer")
    relevant_elements: List[str] = Field(default_factory=list, description="Relevant element IDs")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Confidence score")
    sources: List[Dict[str, Any]] = Field(default_factory=list, description="Source references")


class WhatIfRequest(BaseModel):
    """Request model for what-if analysis."""
    scenario: str = Field(..., min_length=1, description="What-if scenario description")
    affected_elements: Optional[List[str]] = Field(None, description="Element IDs that would be affected")
    include_impact_chain: bool = Field(True, description="Whether to include impact chain analysis")
    max_depth: int = Field(5, ge=1, le=10, description="Maximum depth for impact analysis")


class WhatIfResponse(BaseModel):
    """Response model for what-if analysis."""
    analysis: str = Field(..., description="Impact analysis")
    affected_elements: List[str] = Field(default_factory=list, description="Affected element IDs")
    impact_chain: List[Dict[str, Any]] = Field(default_factory=list, description="Impact propagation chain")
    risk_level: str = Field(..., description="Risk level (low, medium, high, critical)")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations")


class SubgraphContext(BaseModel):
    """Structured context object for subgraph extraction."""
    target_service: Optional[str] = Field(None, description="Target service/element name")
    target_element_id: Optional[str] = Field(None, description="Target element ID")
    direct_dependents: List[str] = Field(default_factory=list, description="Direct dependent element IDs")
    transitive_dependents: List[str] = Field(default_factory=list, description="Transitive dependent element IDs")
    incoming_dependencies: List[str] = Field(default_factory=list, description="Incoming dependency element IDs")
    outgoing_dependencies: List[str] = Field(default_factory=list, description="Outgoing dependency element IDs")
    affected_apis: List[str] = Field(default_factory=list, description="Affected API endpoint paths")
    database_tables: List[str] = Field(default_factory=list, description="Database tables touched")
    database_operations: List[str] = Field(default_factory=list, description="Database operations (read/write)")
    agents_involved: List[str] = Field(default_factory=list, description="Agent IDs involved")
    workflows_involved: List[str] = Field(default_factory=list, description="Workflow IDs involved")
    related_files: List[str] = Field(default_factory=list, description="Related file paths")
    impact_summary: str = Field("", description="Human-readable impact summary")
