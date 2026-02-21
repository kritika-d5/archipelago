import os
from typing import List, Dict, Any, Optional
import logging
from groq import Groq
from pydantic import ValidationError

from app.schemas.graph_schema import (
    CodebaseGraph, CodeElement, QueryRequest, QueryResponse,
    WhatIfRequest, WhatIfResponse
)

logger = logging.getLogger(__name__)


class LLMService:
    """Service for LLM interactions using Groq API."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize LLM service.
        
        Args:
            api_key: Groq API key (defaults to GROQ_API_KEY env var)
        """
        from app.config import GROQ_API_KEY
        api_key = api_key or GROQ_API_KEY or os.getenv("GROQ_API_KEY")
        if not api_key:
            logger.warning("GROQ_API_KEY not found. LLM features will not work.")
            raise ValueError("GROQ_API_KEY environment variable is required. Create .env file with GROQ_API_KEY=your_key")
        
        self.client = Groq(api_key=api_key)
        self.model = "openai/gpt-oss-20b"  # or "mixtral-8x7b-32768"
    
    def _build_context(self, codebase_graph: CodebaseGraph, 
                      element_ids: Optional[List[str]] = None,
                      include_code: bool = True,
                      max_elements: int = 10) -> str:
        """
        Build context string from codebase graph.
        
        Args:
            codebase_graph: Codebase graph
            element_ids: Specific element IDs to include
            include_code: Whether to include code snippets
            max_elements: Maximum number of elements to include
            
        Returns:
            Context string
        """
        context_parts = []
        
        # Add metadata
        metadata = codebase_graph.metadata
        context_parts.append(f"Repository: {metadata.repository_name}")
        context_parts.append(f"Languages: {', '.join([l.value for l in metadata.languages])}")
        context_parts.append(f"Total files: {metadata.total_files}")
        context_parts.append(f"Total lines: {metadata.total_lines}")
        context_parts.append("")
        
        # Add relevant elements
        if element_ids:
            elements_to_include = [codebase_graph.get_element_by_id(eid) 
                                  for eid in element_ids if codebase_graph.get_element_by_id(eid)]
        else:
            # Include top-level modules and important classes
            elements_to_include = []
            for module in codebase_graph.modules[:max_elements]:
                elements_to_include.append(module)
            for elem in codebase_graph.elements[:max_elements]:
                if elem.type.value in ['class', 'function']:
                    elements_to_include.append(elem)
        
        context_parts.append("=== Codebase Structure ===")
        for item in elements_to_include[:max_elements]:
            if isinstance(item, CodeElement):
                context_parts.append(f"\n{item.type.value.upper()}: {item.name}")
                context_parts.append(f"File: {item.file_path}")
                context_parts.append(f"Lines: {item.line_start}-{item.line_end}")
                if item.docstring:
                    context_parts.append(f"Description: {item.docstring}")
                if include_code and item.code_snippet:
                    context_parts.append(f"Code:\n{item.code_snippet}")
                if item.parameters:
                    params_str = ", ".join([f"{p.name}: {p.type or 'Any'}" for p in item.parameters])
                    context_parts.append(f"Parameters: {params_str}")
                if item.return_type:
                    context_parts.append(f"Returns: {item.return_type.type or 'None'}")
            else:  # Module
                context_parts.append(f"\nMODULE: {item.name}")
                context_parts.append(f"File: {item.file_path}")
                if item.docstring:
                    context_parts.append(f"Description: {item.docstring}")
                if item.imports:
                    context_parts.append(f"Imports: {', '.join(item.imports[:10])}")
        
        # Add dependency information
        context_parts.append("\n=== Key Dependencies ===")
        dep_count = 0
        for dep in codebase_graph.dependencies[:20]:
            source = codebase_graph.get_element_by_id(dep.source_id)
            target = codebase_graph.get_element_by_id(dep.target_id)
            if source and target:
                context_parts.append(
                    f"{source.name} -> {target.name} ({dep.dependency_type.value})"
                )
                dep_count += 1
                if dep_count >= 20:
                    break
        
        return "\n".join(context_parts)
    
    def answer_query(self, codebase_graph: CodebaseGraph, 
                    request: QueryRequest) -> QueryResponse:
        """
        Answer a query about the codebase using LLM.
        
        Args:
            codebase_graph: Codebase graph
            request: Query request
            
        Returns:
            Query response with answer
        """
        try:
            # Build context
            context = self._build_context(
                codebase_graph,
                element_ids=request.context_element_ids,
                include_code=request.include_code,
                max_elements=request.max_context_elements
            )
            
            # Build prompt
            prompt = f"""You are an expert code analyst. Analyze the following codebase and answer the user's question.

{context}

User Question: {request.query}

Provide a detailed, accurate answer based on the codebase structure. Include:
1. Direct answer to the question
2. Relevant code elements mentioned
3. How different parts relate to each other
4. Any important patterns or architectural decisions

Answer:"""
            
            # Call Groq API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert code analyst specializing in understanding codebase architecture and relationships."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            answer = response.choices[0].message.content
            
            # Extract relevant elements (simple keyword matching)
            relevant_elements = []
            if request.context_element_ids:
                relevant_elements = request.context_element_ids
            else:
                # Find elements mentioned in answer
                for elem in codebase_graph.elements:
                    if elem.name.lower() in answer.lower() or elem.file_path in answer:
                        relevant_elements.append(elem.id)
                        if len(relevant_elements) >= 10:
                            break
            
            return QueryResponse(
                answer=answer,
                relevant_elements=relevant_elements[:10],
                confidence=0.8,
                sources=[{"type": "codebase", "element_id": eid} for eid in relevant_elements[:5]]
            )
            
        except Exception as e:
            logger.error(f"Error answering query: {e}")
            return QueryResponse(
                answer=f"Error processing query: {str(e)}",
                relevant_elements=[],
                confidence=0.0,
                sources=[]
            )
    
    def explain_project(self, codebase_graph: CodebaseGraph) -> str:
        """
        Generate a comprehensive explanation of the project including database schema.
        
        Args:
            codebase_graph: Codebase graph
            
        Returns:
            Project explanation string
        """
        try:
            # Build context about the project
            context_parts = []
            
            # Database information only
            if codebase_graph.metadata.database_languages:
                context_parts.append(f"\nDatabase Technologies: {', '.join([lang.value for lang in codebase_graph.metadata.database_languages])}")
            
            if codebase_graph.database_schemas:
                context_parts.append(f"\nDatabase Schemas ({len(codebase_graph.database_schemas)}):")
                for schema in codebase_graph.database_schemas:
                    context_parts.append(f"  - {schema.name} ({schema.database_language.value})")
                    if schema.orm_framework:
                        context_parts.append(f"    ORM: {schema.orm_framework}")
                    if schema.tables:
                        context_parts.append(f"    Tables ({len(schema.tables)}):")
                        for table in schema.tables[:10]:  # Limit to first 10
                            context_parts.append(f"      • {table.name} ({len(table.columns)} columns)")
                            if table.primary_keys:
                                context_parts.append(f"        Primary Keys: {', '.join(table.primary_keys)}")
            
            # Only include database-related information
            
            context = "\n".join(context_parts)
            
            # Build prompt - focus only on database schema
            prompt = f"""You are an expert database architect. Analyze the following database structure and provide a clear explanation.

{context}

Provide a focused explanation of the database schema only. Include:
1. **Database Technologies**: What database systems are used
2. **Database Schema Structure**: Overview of schemas and their purpose
3. **Tables and Relationships**: Detailed explanation of each table, its columns, primary keys, foreign keys, and relationships to other tables
4. **Data Model**: What kind of data is stored and how tables relate to each other

Keep it concise and focused only on the database schema. Do not include general project information, architecture, or other components.

Database Schema Explanation:"""
            
            # Call Groq API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert database architect who explains database schemas clearly and concisely, focusing only on database structure, tables, and relationships."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error explaining project: {e}")
            return f"Error generating project explanation: {str(e)}"
    
    def analyze_what_if(self, codebase_graph: CodebaseGraph,
                       request: WhatIfRequest) -> WhatIfResponse:
        """
        Perform what-if analysis using LLM.
        
        Args:
            codebase_graph: Codebase graph
            request: What-if request
            
        Returns:
            What-if response with analysis
        """
        try:
            # Find affected elements
            affected_elements = request.affected_elements or []
            
            # Build impact chain if requested
            impact_chain = []
            if request.include_impact_chain and affected_elements:
                from app.agents.graph_agent import GraphBuilder
                builder = GraphBuilder()
                for elem_id in affected_elements[:5]:  # Limit to first 5
                    chain = builder.find_impact_chain(codebase_graph, elem_id, request.max_depth)
                    impact_chain.extend(chain)
            
            # Build context with affected elements
            context = self._build_context(
                codebase_graph,
                element_ids=affected_elements,
                include_code=True,
                max_elements=20
            )
            
            # Add impact chain to context
            if impact_chain:
                context += "\n\n=== Impact Chain ==="
                for entry in impact_chain[:30]:
                    source = codebase_graph.get_element_by_id(entry['source'])
                    target = codebase_graph.get_element_by_id(entry['target'])
                    if source and target:
                        context += f"\n{source.name} -> {target.name} (depth: {entry['depth']})"
            
            # Build prompt
            prompt = f"""You are an expert code impact analyst. Analyze the following scenario and predict its impact on the codebase.

Codebase Context:
{context}

Scenario: {request.scenario}

Provide a comprehensive impact analysis including:
1. Direct impact on affected elements
2. Cascading effects through dependencies
3. Risk assessment (low/medium/high/critical)
4. Specific recommendations for safe implementation
5. Potential breaking changes
6. Testing requirements

Analysis:"""
            
            # Call Groq API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert code impact analyst specializing in predicting code changes and their effects."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=2500
            )
            
            analysis = response.choices[0].message.content
            
            # Extract risk level from analysis
            risk_level = "medium"
            analysis_lower = analysis.lower()
            if "critical" in analysis_lower or "severe" in analysis_lower:
                risk_level = "critical"
            elif "high" in analysis_lower:
                risk_level = "high"
            elif "low" in analysis_lower or "minimal" in analysis_lower:
                risk_level = "low"
            
            # Extract recommendations (simple pattern matching)
            recommendations = []
            lines = analysis.split('\n')
            for line in lines:
                if any(keyword in line.lower() for keyword in ['recommend', 'suggest', 'should', 'must']):
                    if line.strip() and not line.strip().startswith('#'):
                        recommendations.append(line.strip())
            
            if not recommendations:
                recommendations = [
                    "Review all dependent components",
                    "Update tests for affected areas",
                    "Consider backward compatibility"
                ]
            
            return WhatIfResponse(
                analysis=analysis,
                affected_elements=affected_elements,
                impact_chain=[{"source": e['source'], "target": e['target'], "depth": e['depth']} 
                            for e in impact_chain[:20]],
                risk_level=risk_level,
                recommendations=recommendations[:10]
            )
            
        except Exception as e:
            logger.error(f"Error in what-if analysis: {e}")
            return WhatIfResponse(
                analysis=f"Error performing analysis: {str(e)}",
                affected_elements=[],
                impact_chain=[],
                risk_level="unknown",
                recommendations=[]
            )

    def _build_org_context(self, org_data: Dict[str, Any], max_repos: int = 5) -> str:
        """
        Build context string from organization data (multiple repos + dependencies).
        
        Args:
            org_data: Organization data containing:
                - repos_data: Dict of repo_name -> parsed repo data
                - dependency_graph: Organization-level dependency graph
            max_repos: Maximum number of repos to include in detail
            
        Returns:
            Context string for LLM
        """
        context_parts = []
        
        repos_data = org_data.get("repos_data", {})
        dependency_graph = org_data.get("dependency_graph", {})
        
        # Organization header
        context_parts.append("=== ORGANIZATION OVERVIEW ===")
        context_parts.append(f"Total Repositories: {len(repos_data)}")
        context_parts.append(f"Repository Names: {', '.join(list(repos_data.keys())[:10])}")
        context_parts.append("")
        
        # Add key repositories
        context_parts.append("=== KEY REPOSITORIES ===")
        for i, (repo_name, repo_info) in enumerate(list(repos_data.items())[:max_repos]):
            context_parts.append(f"\nRepository: {repo_name}")
            
            # Services in this repo
            services = repo_info.get("services", [])
            if services:
                context_parts.append(f"Services: {', '.join([s.get('name', 'Unknown') for s in services[:5]])}")
            
            # API endpoints
            endpoints = repo_info.get("api_endpoints", [])
            if endpoints:
                context_parts.append(f"Endpoints: {', '.join([e.get('path', '') for e in endpoints[:5]])}")
            
            # Database access
            db_access = repo_info.get("database_access", [])
            if db_access:
                context_parts.append(f"Database Tables: {', '.join(set([d.get('table') for d in db_access if d.get('table')][:5]))}")
        
        # Cross-repository dependencies
        context_parts.append("\n=== CROSS-REPOSITORY DEPENDENCIES ===")
        edges = dependency_graph.get("edges", [])
        
        # Group by type
        import_deps = [e for e in edges if e.get("dependency_type") == "import"]
        rest_deps = [e for e in edges if e.get("type") == "REST"]
        event_deps = [e for e in edges if e.get("type") == "EVENT"]
        circular_deps = [e for e in edges if e.get("circular")]
        
        if import_deps:
            context_parts.append(f"\nImport Dependencies: {len(import_deps)}")
            for dep in import_deps[:3]:
                context_parts.append(f"  {dep.get('from')} -> {dep.get('to')}")
        
        if rest_deps:
            context_parts.append(f"\nREST API Dependencies: {len(rest_deps)}")
            for dep in rest_deps[:3]:
                endpoint = dep.get('endpoint', 'unknown')
                context_parts.append(f"  {dep.get('from')} -[{endpoint}]-> {dep.get('to')}")
        
        if event_deps:
            context_parts.append(f"\nEvent-driven Dependencies: {len(event_deps)}")
            for dep in event_deps[:3]:
                context_parts.append(f"  {dep.get('from')} -[event: {dep.get('event_name', 'unknown')}]-> {dep.get('to')}")
        
        if circular_deps:
            context_parts.append(f"\nCircular Dependencies (⚠️ Violations): {len(circular_deps)}")
            for dep in circular_deps[:3]:
                context_parts.append(f"  ⚠️ CIRCULAR: {dep.get('from')} <-> {dep.get('to')}")
        
        # Statistics
        context_parts.append("\n=== STATISTICS ===")
        stats = dependency_graph.get("statistics", {})
        context_parts.append(f"Total Dependencies: {stats.get('total_dependencies', 0)}")
        context_parts.append(f"Total Services: {stats.get('total_services', 0)}")
        context_parts.append(f"Total Endpoints: {stats.get('total_endpoints', 0)}")
        
        violations = dependency_graph.get("violations", [])
        if violations:
            context_parts.append(f"⚠️ Architecture Violations: {len(violations)}")
        
        return "\n".join(context_parts)
    
    def answer_org_query(self, org_data: Dict[str, Any], request: QueryRequest) -> QueryResponse:
        """
        Answer a query about an organization's codebase using LLM.
        
        Args:
            org_data: Organization data with all repos and dependency graph
            request: Query request
            
        Returns:
            Query response with answer
        """
        try:
            # Build context from organization data
            context = self._build_org_context(org_data, max_repos=10)
            
            # Build prompt
            prompt = f"""You are an expert in microservices architecture and cross-repository analysis. 
Analyze the following multi-repository organization and answer the user's question.

{context}

User Question: {request.query}

Provide a detailed answer that considers:
1. The overall architecture of the organization
2. How services interact across repositories
3. Potential bottlenecks or dependencies
4. Any architectural issues or violations
5. Best practices and recommendations

Answer:"""
            
            # Call Groq API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert in analyzing microservices architectures and multi-repository organizations. Provide comprehensive, technical answers about system design and dependencies."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            answer = response.choices[0].message.content
            
            # Extract relevant repositories mentioned in answer
            repos_data = org_data.get("repos_data", {})
            relevant_repos = []
            for repo_name in repos_data.keys():
                if repo_name.lower() in answer.lower():
                    relevant_repos.append(repo_name)
            
            return QueryResponse(
                answer=answer,
                relevant_elements=relevant_repos[:10],
                confidence=0.85,
                sources=[{"type": "organization", "element_id": repo} for repo in relevant_repos[:5]]
            )
            
        except Exception as e:
            logger.error(f"Error answering organization query: {e}", exc_info=True)
            return QueryResponse(
                answer=f"Error processing query: {str(e)}",
                relevant_elements=[],
                confidence=0.0,
                sources=[]
            )
    
    def analyze_org_what_if(self, org_data: Dict[str, Any], request: WhatIfRequest) -> WhatIfResponse:
        """
        Perform what-if analysis on organization architecture.
        
        Args:
            org_data: Organization data with all repos and dependency graph
            request: What-if request
            
        Returns:
            What-if response with impact analysis
        """
        try:
            # Build context
            context = self._build_org_context(org_data, max_repos=10)
            
            # Build prompt for what-if analysis
            prompt = f"""You are an expert in system architecture and impact analysis.
Analyze the following organization and perform a what-if analysis for the proposed scenario.

{context}

Scenario: {request.scenario}

Provide a comprehensive impact analysis including:
1. Which repositories/services would be affected
2. What changes would be required in each service
3. Potential breaking changes or compatibility issues
4. Performance implications
5. Testing considerations
6. Deployment strategy
7. Risk assessment (Low/Medium/High)
8. Specific recommendations

Impact Analysis:"""
            
            # Call Groq API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert in analyzing the impact of architectural changes on microservices systems. Provide thorough, risk-aware analysis."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                max_tokens=2500
            )
            
            analysis = response.choices[0].message.content
            
            # Extract affected repositories
            repos_data = org_data.get("repos_data", {})
            affected_repos = []
            for repo_name in repos_data.keys():
                if repo_name.lower() in analysis.lower():
                    affected_repos.append(repo_name)
            
            # Determine risk level from analysis
            analysis_lower = analysis.lower()
            if "high risk" in analysis_lower or "critical" in analysis_lower:
                risk_level = "high"
            elif "medium risk" in analysis_lower or "significant" in analysis_lower:
                risk_level = "medium"
            else:
                risk_level = "low"
            
            # Extract recommendations
            recommendations = [
                "Review affected repositories' dependencies",
                "Update integration tests across services",
                "Plan phased rollout of changes",
                "Monitor cross-service communication",
                "Document architectural changes"
            ]
            
            return WhatIfResponse(
                analysis=analysis,
                affected_elements=affected_repos[:15],
                impact_chain=[],  # Organization-level doesn't have element chains
                risk_level=risk_level,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Error in organization what-if analysis: {e}", exc_info=True)
            return WhatIfResponse(
                analysis=f"Error performing analysis: {str(e)}",
                affected_elements=[],
                impact_chain=[],
                risk_level="unknown",
                recommendations=[]
            )
