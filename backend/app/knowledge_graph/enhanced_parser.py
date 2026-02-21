"""
Enhanced Parser for Node.js and Python codebases.
Extracts microservices-specific patterns: REST calls, events, routes, dependencies.
"""
import os
import re
import ast
import json
from pathlib import Path
from typing import List, Dict, Optional, Set, Any
import logging

logger = logging.getLogger(__name__)


class EnhancedParser:
    """Enhanced parser for extracting microservices patterns."""
    
    def __init__(self):
        """Initialize enhanced parser."""
        # Service name patterns
        self.service_patterns = [
            r'(\w+)-service',
            r'(\w+)_service',
            r'service[_-]?(\w+)',
        ]
        
        # HTTP client patterns
        self.http_patterns = {
            'axios': [r'axios\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']'],
            'fetch': [r'fetch\(["\']([^"\']+)["\']'],
            'request': [r'request\(["\']([^"\']+)["\']'],
            'http': [r'http\.(get|post)\(["\']([^"\']+)["\']'],
        }
        
        # Python HTTP patterns
        self.python_http_patterns = {
            'requests': [r'requests\.(get|post|put|delete)\(["\']([^"\']+)["\']'],
            'httpx': [r'httpx\.(get|post|put|delete)\(["\']([^"\']+)["\']'],
            'aiohttp': [r'aiohttp\.(get|post|put|delete)\(["\']([^"\']+)["\']'],
        }
    
    def parse_repo(self, repo_path: Path, repo_name: str) -> Dict[str, Any]:
        """
        Parse a repository and extract normalized JSON.
        
        Args:
            repo_path: Path to repository
            repo_name: Name of the repository
            
        Returns:
            Normalized JSON structure per repo
        """
        result = {
            "repo": repo_name,
            "language": self._detect_language(repo_path),
            "services": [],
            "api_endpoints": [],
            "external_calls": [],
            "events_produced": [],
            "events_consumed": [],
            "db_models": [],
            "direct_model_access": [],
            "undocumented_routes": [],
            "shared_imports": [],
            "imports": []
        }
        
        # Parse based on language
        if result["language"] == "node":
            self._parse_nodejs_repo(repo_path, result)
        elif result["language"] == "python":
            self._parse_python_repo(repo_path, result)
        
        return result
    
    def _detect_language(self, repo_path: Path) -> str:
        """Detect primary language of repository."""
        package_json = repo_path / "package.json"
        requirements_txt = repo_path / "requirements.txt"
        
        if package_json.exists():
            return "node"
        elif requirements_txt.exists():
            return "python"
        else:
            # Check for file extensions
            js_files = list(repo_path.rglob("*.js"))
            py_files = list(repo_path.rglob("*.py"))
            
            if len(js_files) > len(py_files):
                return "node"
            elif len(py_files) > 0:
                return "python"
            return "unknown"
    
    def _parse_nodejs_repo(self, repo_path: Path, result: Dict[str, Any]):
        """Parse Node.js/Express repository."""
        js_files = list(repo_path.rglob("*.js"))
        ts_files = list(repo_path.rglob("*.ts"))
        all_files = js_files + ts_files
        
        for file_path in all_files:
            if self._should_skip_file(file_path):
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Extract imports
                imports = self._extract_nodejs_imports(content)
                result["imports"].extend(imports)
                
                # Extract routes
                routes = self._extract_nodejs_routes(content, file_path)
                result["api_endpoints"].extend(routes)
                
                # Extract external HTTP calls
                external_calls = self._extract_external_calls(content, file_path)
                result["external_calls"].extend(external_calls)
                
                # Extract events
                events_produced = self._extract_events_emitted(content)
                result["events_produced"].extend(events_produced)
                
                events_consumed = self._extract_events_consumed(content)
                result["events_consumed"].extend(events_consumed)
                
                # Extract DB models
                db_models = self._extract_db_models(content)
                result["db_models"].extend(db_models)
                
                # Extract shared imports
                shared_imports = self._extract_shared_imports(imports)
                result["shared_imports"].extend(shared_imports)
                
                # Extract services
                services = self._extract_services(content, file_path)
                result["services"].extend(services)
                
            except Exception as e:
                logger.debug(f"Error parsing {file_path}: {str(e)}")
                continue
        
        # Deduplicate
        result["api_endpoints"] = self._deduplicate_list(result["api_endpoints"], "path")
        result["external_calls"] = self._deduplicate_list(result["external_calls"], "target")
        result["events_produced"] = list(set(result["events_produced"]))
        result["events_consumed"] = list(set(result["events_consumed"]))
        result["db_models"] = list(set(result["db_models"]))
        result["shared_imports"] = list(set(result["shared_imports"]))
        result["services"] = list(set(result["services"]))
    
    def _parse_python_repo(self, repo_path: Path, result: Dict[str, Any]):
        """Parse Python/FastAPI repository."""
        py_files = list(repo_path.rglob("*.py"))
        
        for file_path in py_files:
            if self._should_skip_file(file_path):
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                tree = ast.parse(content, filename=str(file_path))
                
                # Extract imports
                imports = self._extract_python_imports(tree)
                result["imports"].extend(imports)
                
                # Extract routes
                routes = self._extract_python_routes(tree, file_path)
                result["api_endpoints"].extend(routes)
                
                # Extract external HTTP calls
                external_calls = self._extract_python_external_calls(content, file_path)
                result["external_calls"].extend(external_calls)
                
                # Extract events (Python event emitters)
                events_produced = self._extract_python_events_emitted(content)
                result["events_produced"].extend(events_produced)
                
                events_consumed = self._extract_python_events_consumed(content)
                result["events_consumed"].extend(events_consumed)
                
                # Extract DB models
                db_models = self._extract_python_db_models(tree)
                result["db_models"].extend(db_models)
                
                # Extract shared imports
                shared_imports = self._extract_shared_imports(imports)
                result["shared_imports"].extend(shared_imports)
                
                # Extract services
                services = self._extract_python_services(tree, file_path)
                result["services"].extend(services)
                
            except Exception as e:
                logger.debug(f"Error parsing {file_path}: {str(e)}")
                continue
        
        # Deduplicate
        result["api_endpoints"] = self._deduplicate_list(result["api_endpoints"], "path")
        result["external_calls"] = self._deduplicate_list(result["external_calls"], "target")
        result["events_produced"] = list(set(result["events_produced"]))
        result["events_consumed"] = list(set(result["events_consumed"]))
        result["db_models"] = list(set(result["db_models"]))
        result["shared_imports"] = list(set(result["shared_imports"]))
        result["services"] = list(set(result["services"]))
    
    def _should_skip_file(self, file_path: Path) -> bool:
        """Check if file should be skipped."""
        skip_patterns = [
            'node_modules', '__pycache__', '.git', 'venv', '.venv',
            'dist', 'build', '.next', 'test', 'spec', '__tests__'
        ]
        path_str = str(file_path)
        return any(pattern in path_str for pattern in skip_patterns)
    
    def _extract_nodejs_imports(self, content: str) -> List[str]:
        """Extract require() and import statements."""
        imports = []
        
        # require() statements
        require_pattern = r'require\(["\']([^"\']+)["\']\)'
        imports.extend(re.findall(require_pattern, content))
        
        # ES6 import statements
        import_pattern = r'import\s+.*?\s+from\s+["\']([^"\']+)["\']'
        imports.extend(re.findall(import_pattern, content))
        
        # import 'module'
        import_direct_pattern = r'import\s+["\']([^"\']+)["\']'
        imports.extend(re.findall(import_direct_pattern, content))
        
        return imports
    
    def _extract_python_imports(self, tree: ast.AST) -> List[str]:
        """Extract Python import statements."""
        imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        
        return imports
    
    def _extract_nodejs_routes(self, content: str, file_path: Path) -> List[Dict[str, str]]:
        """Extract Express/Fastify route definitions."""
        routes = []
        
        # Express patterns: app.get, router.post, etc.
        route_patterns = [
            r'(?:app|router|express)\.(get|post|put|delete|patch|put)\s*\(["\']([^"\']+)["\']',
            r'\.(get|post|put|delete|patch)\s*\(["\']([^"\']+)["\']',
        ]
        
        for pattern in route_patterns:
            matches = re.finditer(pattern, content, re.MULTILINE)
            for match in matches:
                method = match.group(1).upper()
                path = match.group(2)
                routes.append({
                    "method": method,
                    "path": path,
                    "file": str(file_path)
                })
        
        return routes
    
    def _extract_python_routes(self, tree: ast.AST, file_path: Path) -> List[Dict[str, str]]:
        """Extract FastAPI/Flask route definitions."""
        routes = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check for FastAPI decorators
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call):
                        if isinstance(decorator.func, ast.Attribute):
                            # @router.get, @app.post, etc.
                            method = decorator.func.attr.upper()
                            if method in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
                                # Extract path from decorator arguments
                                path = "/"
                                if decorator.args:
                                    if isinstance(decorator.args[0], ast.Constant):
                                        path = decorator.args[0].value
                                
                                routes.append({
                                    "method": method,
                                    "path": path,
                                    "file": str(file_path),
                                    "function": node.name
                                })
        
        return routes
    
    def _extract_external_calls(self, content: str, file_path: Path) -> List[Dict[str, str]]:
        """Extract external HTTP calls to other services."""
        external_calls = []
        
        # Match service names in URLs
        service_pattern = r'https?://([\w-]+-service)[^/\s"\']*'
        service_matches = re.finditer(service_pattern, content, re.IGNORECASE)
        
        for match in service_matches:
            target = match.group(1)
            # Extract HTTP method if available
            method = "REST"
            external_calls.append({
                "target": target,
                "type": method,
                "file": str(file_path)
            })
        
        # Also check for axios/fetch patterns with service names
        for http_lib, patterns in self.http_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    url = match.group(-1)  # Last group is the URL
                    # Check if URL contains service name
                    for service_match in re.finditer(r'([\w-]+-service)', url, re.IGNORECASE):
                        target = service_match.group(1)
                        external_calls.append({
                            "target": target,
                            "type": "REST",
                            "file": str(file_path)
                        })
        
        return external_calls
    
    def _extract_python_external_calls(self, content: str, file_path: Path) -> List[Dict[str, str]]:
        """Extract external HTTP calls in Python code."""
        external_calls = []
        
        # Match service names in URLs
        service_pattern = r'https?://([\w-]+-service)[^/\s"\']*'
        service_matches = re.finditer(service_pattern, content, re.IGNORECASE)
        
        for match in service_matches:
            target = match.group(1)
            external_calls.append({
                "target": target,
                "type": "REST",
                "file": str(file_path)
            })
        
        # Check Python HTTP libraries
        for http_lib, patterns in self.python_http_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    url = match.group(-1)
                    for service_match in re.finditer(r'([\w-]+-service)', url, re.IGNORECASE):
                        target = service_match.group(1)
                        external_calls.append({
                            "target": target,
                            "type": "REST",
                            "file": str(file_path)
                        })
        
        return external_calls
    
    def _extract_events_emitted(self, content: str) -> List[str]:
        """Extract event names from emit() calls."""
        events = []
        
        # Node.js EventEmitter patterns
        emit_patterns = [
            r'\.emit\s*\(["\']([^"\']+)["\']',
            r'emit\s*\(["\']([^"\']+)["\']',
            r'eventEmitter\.emit\s*\(["\']([^"\']+)["\']',
        ]
        
        for pattern in emit_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                events.append(match.group(1))
        
        return events
    
    def _extract_events_consumed(self, content: str) -> List[str]:
        """Extract event names from on()/listen() calls."""
        events = []
        
        # Node.js EventEmitter patterns
        listen_patterns = [
            r'\.on\s*\(["\']([^"\']+)["\']',
            r'\.listen\s*\(["\']([^"\']+)["\']',
            r'on\s*\(["\']([^"\']+)["\']',
        ]
        
        for pattern in listen_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                events.append(match.group(1))
        
        return events
    
    def _extract_python_events_emitted(self, content: str) -> List[str]:
        """Extract event names from Python emit calls."""
        events = []
        
        # Python event emitter patterns
        emit_patterns = [
            r'\.emit\s*\(["\']([^"\']+)["\']',
            r'emit\s*\(["\']([^"\']+)["\']',
        ]
        
        for pattern in emit_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                events.append(match.group(1))
        
        return events
    
    def _extract_python_events_consumed(self, content: str) -> List[str]:
        """Extract event names from Python listen/on calls."""
        events = []
        
        listen_patterns = [
            r'\.on\s*\(["\']([^"\']+)["\']',
            r'\.listen\s*\(["\']([^"\']+)["\']',
        ]
        
        for pattern in listen_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                events.append(match.group(1))
        
        return events
    
    def _extract_db_models(self, content: str) -> List[str]:
        """Extract in-memory DB model names."""
        models = []
        
        # Common patterns for in-memory DBs
        db_patterns = [
            r'const\s+(\w+)\s*=\s*\[\]',  # const orders = []
            r'let\s+(\w+)\s*=\s*\[\]',
            r'var\s+(\w+)\s*=\s*\[\]',
            r'(\w+)\s*:\s*\[\]',  # orders: []
        ]
        
        for pattern in db_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                model_name = match.group(1)
                # Filter out common non-model names
                if model_name not in ['data', 'items', 'list', 'array', 'result', 'results']:
                    models.append(model_name)
        
        return models
    
    def _extract_python_db_models(self, tree: ast.AST) -> List[str]:
        """Extract Python DB model names."""
        models = []
        
        for node in ast.walk(tree):
            # Look for list/dict assignments that might be in-memory DBs
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if isinstance(node.value, (ast.List, ast.Dict)):
                            models.append(target.id)
        
        return models
    
    def _extract_shared_imports(self, imports: List[str]) -> List[str]:
        """Extract imports that reference shared-contracts or other repos."""
        shared = []
        
        for imp in imports:
            if 'shared' in imp.lower() or 'contract' in imp.lower():
                shared.append(imp)
            # Check for cross-repo imports (../other-service)
            if '../' in imp or '/other-' in imp:
                shared.append(imp)
        
        return shared
    
    def _extract_services(self, content: str, file_path: Path) -> List[str]:
        """Extract service class/object names."""
        services = []
        
        # Look for class definitions with "Service" in name
        service_class_pattern = r'class\s+(\w*Service\w*)'
        matches = re.finditer(service_class_pattern, content, re.IGNORECASE)
        for match in matches:
            services.append(match.group(1))
        
        return services
    
    def _extract_python_services(self, tree: ast.AST, file_path: Path) -> List[str]:
        """Extract Python service class names."""
        services = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if 'service' in node.name.lower():
                    services.append(node.name)
        
        return services
    
    def _deduplicate_list(self, items: List[Dict], key: str) -> List[Dict]:
        """Deduplicate list of dictionaries by key."""
        seen = set()
        result = []
        for item in items:
            item_key = item.get(key)
            if item_key and item_key not in seen:
                seen.add(item_key)
                result.append(item)
        return result

