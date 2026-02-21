"""
Architecture Agent for generating architecture blueprints.
"""
import json
import logging
from typing import Dict, Any, Optional, List
from app.core.llm import LLMService
from app.schemas.architecture_schema import ArchitectureBlueprint, ArchitectureRequest

logger = logging.getLogger(__name__)


class ArchitectureAgent:
    """Agent for generating architecture blueprints."""
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        """Initialize architecture agent."""
        self.llm_service = llm_service or LLMService()
    
    def detect_mode(self, mode_input: str, repo_key: Optional[str] = None) -> str:
        """
        Detect mode from input.
        
        Args:
            mode_input: Mode string from request
            repo_key: Optional repo key for brownfield
            
        Returns:
            Detected mode: 'greenfield' or 'brownfield'
        """
        mode = mode_input.lower()
        if mode not in ['greenfield', 'brownfield']:
            # Auto-detect based on repo_key presence
            if repo_key:
                return 'brownfield'
            return 'greenfield'
        return mode
    
    def summarize_graph(self, graph_data: Dict[str, Any], parsed_data: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate summary of existing system from graph data.
        
        Args:
            graph_data: Graph data from MongoDB
            parsed_data: Parsed data from MongoDB
            
        Returns:
            Summary string
        """
        try:
            nodes = graph_data.get("graph_data", {}).get("nodes", [])
            edges = graph_data.get("graph_data", {}).get("edges", [])
            stats = graph_data.get("graph_data", {}).get("stats", {})
            
            # Count services
            services = [n for n in nodes if n.get("type") == "Service"]
            schemas = [n for n in nodes if n.get("type") == "Schema"]
            endpoints = [n for n in nodes if n.get("type") == "Endpoint"]
            
            total_services = len(services)
            total_databases = len([s for s in schemas if "database" in s.get("name", "").lower() or "db" in s.get("name", "").lower()])
            
            # Find most depended service
            service_dependencies = {}
            for edge in edges:
                target = edge.get("target", "")
                if any(s.get("id") == target for s in services):
                    service_dependencies[target] = service_dependencies.get(target, 0) + 1
            
            most_depended = max(service_dependencies.items(), key=lambda x: x[1])[0] if service_dependencies else "N/A"
            
            # Find high coupling services (services with many connections)
            high_coupling = []
            for service in services:
                service_id = service.get("id", "")
                connections = len([e for e in edges if e.get("source") == service_id or e.get("target") == service_id])
                if connections > 5:  # Threshold for high coupling
                    high_coupling.append(f"{service_id} ({connections} connections)")
            
            # Database usage pattern
            db_usage = []
            for edge in edges:
                relation = edge.get("relation", "")
                if "database" in relation.lower() or "db" in relation.lower():
                    db_usage.append(f"{edge.get('source')} -> {edge.get('target')}")
            
            # Detect architecture style based on unique top-level folders
            top_level_folders = set()
            common_root_folders = {'src', 'app', 'backend', 'frontend', 'lib', 'packages', 'services', 'modules'}
            
            for node in nodes:
                file_path = node.get("file_path", "")
                if file_path:
                    # Extract top-level folder from file path
                    # Handle both Unix and Windows paths
                    path_parts = file_path.replace("\\", "/").strip("/").split("/")
                    
                    if len(path_parts) > 0:
                        # Get the first meaningful folder
                        first_folder = path_parts[0].lower()
                        
                        # If first folder is a common root, look at second level
                        if first_folder in common_root_folders and len(path_parts) > 1:
                            # Use second level folder as top-level
                            top_level_folders.add(path_parts[1])
                        elif first_folder and first_folder not in common_root_folders:
                            # Use first folder if it's not a common root
                            top_level_folders.add(path_parts[0])
                        elif len(path_parts) > 1:
                            # Fallback to second level
                            top_level_folders.add(path_parts[1])
            
            number_of_unique_top_level_folders = len(top_level_folders)
            
            # Detect architecture style based on folder count
            if number_of_unique_top_level_folders > 3:
                architecture_style = "Microservices"
            else:
                architecture_style = "Monolithic"
            
            summary = f"""
SYSTEM SUMMARY:
- Total Services: {total_services}
- Total Databases/Schemas: {total_databases}
- Total Endpoints: {len(endpoints)}
- Most Depended Service: {most_depended}
- High Coupling Services: {', '.join(high_coupling) if high_coupling else 'None detected'}
- Database Usage Pattern: {len(db_usage)} database-related connections
- Unique Top-Level Folders: {number_of_unique_top_level_folders}
- Detected Architecture Style: {architecture_style}
- Total Nodes: {stats.get('total_nodes', 0)}
- Total Edges: {stats.get('total_edges', 0)}
"""
            return summary
        except Exception as e:
            logger.error(f"Error summarizing graph: {str(e)}")
            return "Unable to generate system summary."
    
    def build_greenfield_prompt(self, requirements: str, constraints: Optional[Dict[str, Any]] = None) -> str:
        """
        Build prompt for greenfield architecture generation.
        
        Args:
            requirements: User requirements
            constraints: System constraints
            
        Returns:
            Prompt string
        """
        constraints_text = ""
        if constraints:
            constraints_text = f"""
CONSTRAINTS:
- Scalability: {constraints.get('scalability', 'Not specified')}
- Performance: {constraints.get('performance', 'Not specified')}
- Budget: {constraints.get('budget', 'Not specified')}
"""
        
        prompt = f"""You are an expert software architect. Generate a comprehensive architecture blueprint for a GREENFIELD project.

REQUIREMENTS:
{requirements}

{constraints_text}

Generate a detailed architecture blueprint in STRICT JSON format matching this exact structure:

{{
  "mode": "greenfield",
  "architecture_style": "microservices|monolithic|serverless|event-driven|layered",
  "system_overview": "Detailed overview of the system architecture",
  "services": [
    {{
      "name": "ServiceName",
      "description": "Service description",
      "technology": "Technology stack",
      "responsibilities": ["responsibility1", "responsibility2"],
      "endpoints": ["/endpoint1", "/endpoint2"]
    }}
  ],
  "infrastructure": {{
    "cloud_provider": "AWS|Azure|GCP|On-premise",
    "compute": {{"type": "containers|VMs|serverless", "details": "..."}},
    "storage": {{"type": "object storage|block storage", "details": "..."}},
    "networking": {{"type": "VPC|CDN", "details": "..."}},
    "monitoring": {{"tools": ["tool1", "tool2"], "details": "..."}}
  }},
  "data_architecture": {{
    "databases": [
      {{"type": "PostgreSQL|MongoDB|Redis", "purpose": "...", "schema": "..."}}
    ],
    "data_flow": "Description of data flow",
    "storage_strategy": "Strategy description"
  }},
  "detected_issues": [],
  "recommendations": ["recommendation1", "recommendation2"],
  "tradeoffs": ["tradeoff1", "tradeoff2"],
  "migration_plan": [],
  "mermaid_diagram": "mermaid diagram code here",
  "confidence_score": 0.85
}}

IMPORTANT:
- Return ONLY valid JSON, no markdown, no explanations
- Ensure all fields are present
- mermaid_diagram should be valid Mermaid syntax
- confidence_score should be between 0.0 and 1.0
"""
        return prompt
    
    def build_brownfield_prompt(self, system_summary: str, user_intent: Optional[str] = None) -> str:
        """
        Build prompt for brownfield architecture optimization.
        
        Args:
            system_summary: Summary of existing system
            user_intent: User's optimization intent
            
        Returns:
            Prompt string
        """
        intent_text = f"\nUSER INTENT:\n{user_intent}\n" if user_intent else ""
        
        prompt = f"""You are an expert software architect. Analyze the EXISTING system and generate an optimized architecture blueprint.

EXISTING SYSTEM SUMMARY:
{system_summary}
{intent_text}

Generate a detailed architecture blueprint in STRICT JSON format matching this exact structure:

{{
  "mode": "brownfield",
  "architecture_style": "current architecture style",
  "system_overview": "Overview of current system and proposed optimizations",
  "services": [
    {{
      "name": "ServiceName",
      "description": "Service description",
      "technology": "Technology stack",
      "responsibilities": ["responsibility1", "responsibility2"],
      "endpoints": ["/endpoint1", "/endpoint2"]
    }}
  ],
  "infrastructure": {{
    "cloud_provider": "AWS|Azure|GCP|On-premise",
    "compute": {{"type": "containers|VMs|serverless", "details": "..."}},
    "storage": {{"type": "object storage|block storage", "details": "..."}},
    "networking": {{"type": "VPC|CDN", "details": "..."}},
    "monitoring": {{"tools": ["tool1", "tool2"], "details": "..."}}
  }},
  "data_architecture": {{
    "databases": [
      {{"type": "PostgreSQL|MongoDB|Redis", "purpose": "...", "schema": "..."}}
    ],
    "data_flow": "Description of data flow",
    "storage_strategy": "Strategy description"
  }},
  "detected_issues": ["issue1", "issue2"],
  "recommendations": ["recommendation1", "recommendation2"],
  "tradeoffs": ["tradeoff1", "tradeoff2"],
  "migration_plan": ["step1", "step2", "step3"],
  "mermaid_diagram": "mermaid diagram code here",
  "confidence_score": 0.85
}}

IMPORTANT:
- Return ONLY valid JSON, no markdown, no explanations
- Ensure all fields are present
- detected_issues should list current system issues
- migration_plan should provide step-by-step migration strategy
- mermaid_diagram should be valid Mermaid syntax
- confidence_score should be between 0.0 and 1.0
"""
        return prompt
    
    def call_llm(self, prompt: str) -> str:
        """
        Call LLM with prompt and extract JSON response.
        
        Args:
            prompt: Prompt string
            
        Returns:
            JSON response string
        """
        try:
            response = self.llm_service.client.chat.completions.create(
                model=self.llm_service.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert software architect. Always respond with valid JSON only, no markdown formatting, no code blocks, no explanations before or after the JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=4000
            )
            
            content = response.choices[0].message.content.strip()
            
            # Remove markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]
            elif content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            
            content = content.strip()
            
            # Extract JSON object by finding first { and matching closing }
            # This handles cases where there's extra text before or after
            first_brace = content.find('{')
            if first_brace == -1:
                raise ValueError("No JSON object found in response")
            
            # Find the matching closing brace
            brace_count = 0
            last_brace = -1
            for i in range(first_brace, len(content)):
                if content[i] == '{':
                    brace_count += 1
                elif content[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        last_brace = i
                        break
            
            if last_brace == -1:
                raise ValueError("Unclosed JSON object in response")
            
            # Extract just the JSON part
            json_content = content[first_brace:last_brace + 1]
            
            # Validate it's valid JSON before returning
            try:
                json.loads(json_content)
            except json.JSONDecodeError as e:
                logger.error(f"Extracted JSON is still invalid: {str(e)}")
                logger.error(f"Extracted content: {json_content[:500]}...")
                raise ValueError(f"Failed to extract valid JSON: {str(e)}")
            
            return json_content
        except Exception as e:
            logger.error(f"Error calling LLM: {str(e)}")
            raise
    
    def validate_blueprint_schema(self, json_str: str) -> ArchitectureBlueprint:
        """
        Validate and parse JSON response into ArchitectureBlueprint.
        
        Args:
            json_str: JSON string from LLM
            
        Returns:
            Validated ArchitectureBlueprint
        """
        try:
            data = json.loads(json_str)
            
            # Ensure mermaid_diagram is not empty, provide default if missing
            if not data.get("mermaid_diagram"):
                data["mermaid_diagram"] = "graph TD\n    A[Architecture]\n    B[To be generated]\n    A --> B"
            
            # Ensure confidence_score is present and valid
            if "confidence_score" not in data:
                data["confidence_score"] = 0.8
            else:
                try:
                    score = float(data["confidence_score"])
                    if not (0.0 <= score <= 1.0):
                        data["confidence_score"] = 0.8
                except (ValueError, TypeError):
                    data["confidence_score"] = 0.8
            
            blueprint = ArchitectureBlueprint(**data)
            return blueprint
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from LLM: {str(e)}")
            logger.error(f"JSON string (first 500 chars): {json_str[:500]}")
            raise ValueError(f"Invalid JSON response at position {e.pos}: {str(e)}")
        except Exception as e:
            logger.error(f"Schema validation error: {str(e)}")
            logger.error(f"JSON data keys: {list(data.keys()) if 'data' in locals() else 'N/A'}")
            raise ValueError(f"Schema validation failed: {str(e)}")

