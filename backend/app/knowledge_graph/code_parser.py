"""
Code Parser for Knowledge Graph
Extracts structured metadata from Python repositories.
"""
import os
import ast
from typing import Dict, List, Any
from pathlib import Path


def parse_repository(repo_path: str) -> Dict[str, Any]:
    """
    Walk through repository and parse all Python files.
    
    Args:
        repo_path: Path to the repository root
        
    Returns:
        Dictionary containing services, schemas, endpoints, fields, and imports
    """
    parsed_data = {
        "services": {},
        "schemas": {},
        "endpoints": [],
        "fields": {},
        "imports": {}
    }
    
    repo_path_obj = Path(repo_path)
    
    if not repo_path_obj.exists():
        return parsed_data
    
    # Walk through all .py files
    for py_file in repo_path_obj.rglob("*.py"):
        # Skip __pycache__ and venv directories
        if "__pycache__" in str(py_file) or "venv" in str(py_file):
            continue
            
        try:
            file_data = parse_file(str(py_file))
            
            # Merge file data into parsed_data
            parsed_data["services"].update(file_data.get("services", {}))
            parsed_data["schemas"].update(file_data.get("schemas", {}))
            parsed_data["endpoints"].extend(file_data.get("endpoints", []))
            parsed_data["fields"].update(file_data.get("fields", {}))
            parsed_data["imports"].update(file_data.get("imports", {}))
            
        except Exception as e:
            # Skip files that can't be parsed
            continue
    
    return parsed_data


def parse_file(file_path: str) -> Dict[str, Any]:
    """
    Parse a single Python file and extract metadata.
    
    Args:
        file_path: Path to the Python file
        
    Returns:
        Dictionary with services, schemas, endpoints, fields, and imports
    """
    result = {
        "services": {},
        "schemas": {},
        "endpoints": [],
        "fields": {},
        "imports": {}
    }
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        # Extract file-level imports
        imports = _extract_imports(tree)
        result["imports"][file_path] = imports
        
        # Walk through AST nodes
        for node in ast.walk(tree):
            # Extract classes (services, schemas)
            if isinstance(node, ast.ClassDef):
                class_info = _extract_class_info(node, file_path)
                
                # Determine if it's a service or schema
                if _is_service_class(node):
                    result["services"][class_info["name"]] = class_info
                elif _is_schema_class(node):
                    result["schemas"][class_info["name"]] = class_info
                    # Extract fields from schema
                    fields = _extract_class_fields(node)
                    result["fields"][class_info["name"]] = fields
            
            # Extract functions (endpoints, main functions)
            elif isinstance(node, ast.FunctionDef):
                func_info = _extract_function_info(node, file_path)
                
                # Check if it's an endpoint (decorated with @router, @app, etc.)
                if _is_endpoint(node):
                    result["endpoints"].append(func_info)
    
    except Exception as e:
        # Return empty result if parsing fails
        pass
    
    return result


def _extract_imports(tree: ast.AST) -> List[str]:
    """Extract all import statements from AST."""
    imports = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append(f"{module}.{alias.name}" if module else alias.name)
    
    return imports


def _extract_class_info(node: ast.ClassDef, file_path: str) -> Dict[str, Any]:
    """Extract information about a class."""
    return {
        "name": node.name,
        "file_path": file_path,
        "bases": [ast.unparse(base) if hasattr(ast, "unparse") else _node_to_string(base) for base in node.bases],
        "methods": [n.name for n in node.body if isinstance(n, ast.FunctionDef)],
        "line_number": node.lineno
    }


def _extract_class_fields(node: ast.ClassDef) -> Dict[str, Any]:
    """Extract fields from a class (for schemas)."""
    fields = {}
    
    for item in node.body:
        # Check for class variables or annotations
        if isinstance(item, ast.AnnAssign):
            if isinstance(item.target, ast.Name):
                field_name = item.target.id
                field_type = ast.unparse(item.annotation) if hasattr(ast, "unparse") else _node_to_string(item.annotation)
                fields[field_name] = {"type": field_type}
        
        # Check for assignments (like in Pydantic models)
        elif isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name):
                    fields[target.id] = {"type": "Any"}
    
    return fields


def _extract_function_info(node: ast.FunctionDef, file_path: str) -> Dict[str, Any]:
    """Extract information about a function."""
    # Extract decorators
    decorators = []
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Attribute):
                decorators.append(decorator.func.attr)
            elif isinstance(decorator.func, ast.Name):
                decorators.append(decorator.func.id)
        elif isinstance(decorator, ast.Attribute):
            decorators.append(decorator.attr)
        elif isinstance(decorator, ast.Name):
            decorators.append(decorator.id)
    
    # Extract parameters
    params = []
    for arg in node.args.args:
        param_info = {"name": arg.arg}
        if arg.annotation:
            param_info["type"] = ast.unparse(arg.annotation) if hasattr(ast, "unparse") else _node_to_string(arg.annotation)
        params.append(param_info)
    
    return {
        "name": node.name,
        "file_path": file_path,
        "decorators": decorators,
        "parameters": params,
        "line_number": node.lineno
    }


def _is_service_class(node: ast.ClassDef) -> bool:
    """Check if a class is a service (has Service in name or methods like get, create, etc.)."""
    service_keywords = ["service", "manager", "handler", "controller"]
    name_lower = node.name.lower()
    
    if any(keyword in name_lower for keyword in service_keywords):
        return True
    
    # Check for common service methods
    method_names = [n.name.lower() for n in node.body if isinstance(n, ast.FunctionDef)]
    service_methods = ["get", "create", "update", "delete", "fetch", "save"]
    if any(method in " ".join(method_names) for method in service_methods):
        return True
    
    return False


def _is_schema_class(node: ast.ClassDef) -> bool:
    """Check if a class is a schema/model (inherits from BaseModel, Schema, etc.)."""
    schema_keywords = ["schema", "model", "dto", "entity"]
    name_lower = node.name.lower()
    
    if any(keyword in name_lower for keyword in schema_keywords):
        return True
    
    # Check base classes
    for base in node.bases:
        base_str = ast.unparse(base) if hasattr(ast, "unparse") else _node_to_string(base)
        if "BaseModel" in base_str or "Schema" in base_str or "Model" in base_str:
            return True
    
    return False


def _is_endpoint(node: ast.FunctionDef) -> bool:
    """Check if a function is an API endpoint (has router/app decorators)."""
    endpoint_decorators = ["get", "post", "put", "delete", "patch", "router", "app"]
    
    for decorator in node.decorator_list:
        decorator_str = ""
        if isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Attribute):
                decorator_str = decorator.func.attr.lower()
            elif isinstance(decorator.func, ast.Name):
                decorator_str = decorator.func.id.lower()
        elif isinstance(decorator, ast.Attribute):
            decorator_str = decorator.attr.lower()
        elif isinstance(decorator, ast.Name):
            decorator_str = decorator.id.lower()
        
        if any(endpoint in decorator_str for endpoint in endpoint_decorators):
            return True
    
    return False


def _node_to_string(node: ast.AST) -> str:
    """Convert AST node to string representation (fallback for older Python versions)."""
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        return f"{_node_to_string(node.value)}.{node.attr}"
    elif isinstance(node, ast.Constant):
        return str(node.value)
    else:
        return str(type(node).__name__)

