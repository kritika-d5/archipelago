import os
import ast
import re
from pathlib import Path
from typing import List, Dict, Optional, Set, Any
import logging
from datetime import datetime

from app.schemas.graph_schema import (
    CodeElement, CodeElementType, Language, Parameter, ReturnType,
    Dependency, DependencyType, Module, CodebaseGraph, CodebaseMetadata,
    ClassInfo
)

logger = logging.getLogger(__name__)


class CodeParser:
    """Parses codebase and extracts structured information."""
    
    def __init__(self, include_tests: bool = True, include_vendor: bool = False,
                 languages: Optional[List[Language]] = None, max_file_size: int = 1000000):
        """
        Initialize code parser.
        
        Args:
            include_tests: Whether to include test files
            include_vendor: Whether to include vendor/node_modules
            languages: Specific languages to parse (None = all)
            max_file_size: Maximum file size in bytes
        """
        self.include_tests = include_tests
        self.include_vendor = include_vendor
        self.languages = languages
        self.max_file_size = max_file_size
        
        # Language detection patterns
        self.language_extensions = {
            Language.PYTHON: {'.py', '.pyw'},
            Language.JAVASCRIPT: {'.js', '.jsx'},
            Language.TYPESCRIPT: {'.ts', '.tsx'},
            Language.JAVA: {'.java'},
            Language.CPP: {'.cpp', '.cc', '.cxx', '.hpp', '.h'},
            Language.GO: {'.go'},
            Language.RUST: {'.rs'},
        }
        
        # Ignore patterns
        self.ignore_patterns = [
            '__pycache__', '.git', '.svn', '.hg',
            'node_modules', '.venv', 'venv', 'env',
            '.pytest_cache', '.mypy_cache', '.idea', '.vscode',
            'dist', 'build', '.next', '.nuxt'
        ]
    
    def detect_language(self, file_path: Path) -> Language:
        """Detect programming language from file extension."""
        ext = file_path.suffix.lower()
        for lang, extensions in self.language_extensions.items():
            if ext in extensions:
                return lang
        return Language.UNKNOWN
    
    def should_parse_file(self, file_path: Path) -> bool:
        """Determine if a file should be parsed."""
        # Check file size
        try:
            if file_path.stat().st_size > self.max_file_size:
                return False
        except Exception:
            return False
        
        # Check ignore patterns
        path_str = str(file_path)
        for pattern in self.ignore_patterns:
            if pattern in path_str:
                if not self.include_vendor:
                    return False
        
        # Check if test file
        if not self.include_tests:
            if any(test_indicator in path_str.lower() for test_indicator in 
                   ['test', 'spec', '__test__', '__tests__']):
                return False
        
        # Check language filter
        if self.languages:
            lang = self.detect_language(file_path)
            if lang not in self.languages:
                return False
        
        return True
    
    def get_all_files(self, repo_path: Path) -> List[Path]:
        """Get all parseable files in repository."""
        files = []
        for root, dirs, filenames in os.walk(repo_path):
            # Filter out ignored directories
            dirs[:] = [d for d in dirs if not any(
                pattern in os.path.join(root, d) for pattern in self.ignore_patterns
            )]
            
            for filename in filenames:
                file_path = Path(root) / filename
                if self.should_parse_file(file_path):
                    files.append(file_path)
        
        return files
    
    def parse_python_file(self, file_path: Path, repo_path: Path) -> tuple[List[CodeElement], List[Dependency], Module]:
        """Parse a Python file."""
        elements = []
        dependencies = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            tree = ast.parse(content, filename=str(file_path))
            
            # Get relative path
            rel_path = str(file_path.relative_to(repo_path))
            
            # Extract module-level docstring
            module_docstring = ast.get_docstring(tree)
            
            # Create module
            module_id = f"module:{rel_path}"
            module = Module(
                id=module_id,
                name=Path(file_path).stem,
                file_path=rel_path,
                package_path=self._get_package_path(file_path, repo_path),
                language=Language.PYTHON,
                docstring=module_docstring
            )
            
            # Track imports
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    import_str = self._extract_import(node)
                    if import_str:
                        imports.append(import_str)
                        module.imports.append(import_str)
            
            # Parse classes
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_elem, class_deps = self._parse_python_class(
                        node, file_path, repo_path, content
                    )
                    elements.append(class_elem)
                    dependencies.extend(class_deps)
                    module.element_ids.append(class_elem.id)
            
            # Parse functions (not methods)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Check if it's a method (inside a class)
                    is_method = any(
                        isinstance(parent, ast.ClassDef) for parent in ast.walk(tree)
                        if hasattr(parent, 'body') and node in parent.body
                    )
                    if not is_method:
                        func_elem, func_deps = self._parse_python_function(
                            node, file_path, repo_path, content, is_method=False
                        )
                        elements.append(func_elem)
                        dependencies.extend(func_deps)
                        module.element_ids.append(func_elem.id)
            
            return elements, dependencies, module
            
        except SyntaxError as e:
            logger.warning(f"Syntax error in {file_path}: {e}")
            return [], [], Module(
                id=f"module:{rel_path}",
                name=Path(file_path).stem,
                file_path=rel_path,
                language=Language.PYTHON
            )
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            return [], [], Module(
                id=f"module:{rel_path}",
                name=Path(file_path).stem,
                file_path=rel_path,
                language=Language.PYTHON
            )
    
    def _parse_python_class(self, node: ast.ClassDef, file_path: Path, 
                           repo_path: Path, content: str) -> tuple[CodeElement, List[Dependency]]:
        """Parse a Python class."""
        rel_path = str(file_path.relative_to(repo_path))
        element_id = f"class:{rel_path}:{node.name}"
        
        # Extract docstring
        docstring = ast.get_docstring(node)
        
        # Get code snippet
        lines = content.split('\n')
        code_snippet = '\n'.join(lines[node.lineno-1:min(node.lineno+20, len(lines))])
        
        # Get decorators
        decorators = [ast.unparse(d) if hasattr(ast, 'unparse') else d.__class__.__name__ 
                     for d in node.decorator_list]
        
        # Get base classes
        base_classes = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_classes.append(base.id)
            elif isinstance(base, ast.Attribute):
                base_classes.append(ast.unparse(base) if hasattr(ast, 'unparse') else str(base))
        
        element = CodeElement(
            id=element_id,
            name=node.name,
            type=CodeElementType.CLASS,
            file_path=rel_path,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            language=Language.PYTHON,
            docstring=docstring,
            code_snippet=code_snippet[:500],
            decorators=decorators,
            is_abstract=any('abstract' in d.lower() for d in decorators)
        )
        
        # Create dependencies for base classes
        dependencies = []
        for base in base_classes:
            dependencies.append(Dependency(
                source_id=element_id,
                target_id=f"class:{base}",
                dependency_type=DependencyType.INHERITANCE,
                strength=1.0
            ))
        
        return element, dependencies
    
    def _parse_python_function(self, node: ast.FunctionDef, file_path: Path,
                               repo_path: Path, content: str, is_method: bool) -> tuple[CodeElement, List[Dependency]]:
        """Parse a Python function or method."""
        rel_path = str(file_path.relative_to(repo_path))
        element_type = CodeElementType.METHOD if is_method else CodeElementType.FUNCTION
        element_id = f"{element_type.value}:{rel_path}:{node.name}"
        
        docstring = ast.get_docstring(node)
        
        # Extract parameters
        parameters = []
        for arg in node.args.args:
            param_type = None
            if arg.annotation:
                param_type = ast.unparse(arg.annotation) if hasattr(ast, 'unparse') else str(arg.annotation)
            
            parameters.append(Parameter(
                name=arg.arg,
                type=param_type,
                is_optional=False
            ))
        
        # Extract return type
        return_type = None
        if node.returns:
            return_type = ReturnType(
                type=ast.unparse(node.returns) if hasattr(ast, 'unparse') else str(node.returns)
            )
        
        # Get code snippet
        lines = content.split('\n')
        code_snippet = '\n'.join(lines[node.lineno-1:min(node.lineno+30, len(lines))])
        
        # Get decorators
        decorators = [ast.unparse(d) if hasattr(ast, 'unparse') else d.__class__.__name__
                     for d in node.decorator_list]
        
        element = CodeElement(
            id=element_id,
            name=node.name,
            type=element_type,
            file_path=rel_path,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            language=Language.PYTHON,
            docstring=docstring,
            code_snippet=code_snippet[:500],
            parameters=parameters,
            return_type=return_type,
            decorators=decorators,
            is_async=isinstance(node, ast.AsyncFunctionDef)
        )
        
        # Extract function calls (dependencies)
        dependencies = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    target_id = f"function:{rel_path}:{child.func.id}"
                    dependencies.append(Dependency(
                        source_id=element_id,
                        target_id=target_id,
                        dependency_type=DependencyType.CALL,
                        strength=0.8,
                        line_number=child.lineno
                    ))
        
        return element, dependencies
    
    def _extract_import(self, node: ast.Import | ast.ImportFrom) -> Optional[str]:
        """Extract import string from AST node."""
        if isinstance(node, ast.Import):
            return ', '.join(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            names = ', '.join(alias.name for alias in node.names)
            return f"from {module} import {names}" if module else names
        return None
    
    def _get_package_path(self, file_path: Path, repo_path: Path) -> Optional[str]:
        """Get package path for a file."""
        rel_path = file_path.relative_to(repo_path)
        parts = rel_path.parts[:-1]  # Exclude filename
        if parts:
            return '.'.join(parts)
        return None
    
    def parse_file(self, file_path: Path, repo_path: Path) -> tuple[List[CodeElement], List[Dependency], Module]:
        """Parse a file based on its language."""
        language = self.detect_language(file_path)
        
        if language == Language.PYTHON:
            return self.parse_python_file(file_path, repo_path)
        else:
            # For other languages, create a basic module entry
            rel_path = str(file_path.relative_to(repo_path))
            module = Module(
                id=f"module:{rel_path}",
                name=Path(file_path).stem,
                file_path=rel_path,
                language=language
            )
            return [], [], module
    
    def parse_repository(self, repo_path: Path, repo_url: Optional[str] = None,
                        branch: Optional[str] = None, commit_hash: Optional[str] = None) -> CodebaseGraph:
        """
        Parse entire repository and build codebase graph.
        
        Args:
            repo_path: Path to repository
            repo_url: Repository URL
            branch: Branch name
            commit_hash: Commit hash
            
        Returns:
            CodebaseGraph with all parsed information
        """
        logger.info(f"Starting to parse repository: {repo_path}")
        
        all_elements = []
        all_dependencies = []
        all_modules = []
        total_lines = 0
        languages_found = set()
        
        files = self.get_all_files(repo_path)
        logger.info(f"Found {len(files)} files to parse")
        
        for file_path in files:
            try:
                elements, dependencies, module = self.parse_file(file_path, repo_path)
                all_elements.extend(elements)
                all_dependencies.extend(dependencies)
                all_modules.append(module)
                
                # Count lines
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        total_lines += len(f.readlines())
                except Exception:
                    pass
                
                # Track languages
                languages_found.add(module.language)
                
            except Exception as e:
                logger.error(f"Error parsing {file_path}: {e}")
                continue
        
        # Build metadata
        repo_name = Path(repo_path).name
        metadata = CodebaseMetadata(
            repository_url=repo_url,
            repository_name=repo_name,
            branch=branch,
            commit_hash=commit_hash,
            parsed_at=datetime.now(),
            total_files=len(all_modules),
            total_lines=total_lines,
            languages=list(languages_found),
            main_entry_points=self._find_main_entry_points(all_modules),
            test_files=[m.file_path for m in all_modules if 'test' in m.file_path.lower()],
            config_files=[m.file_path for m in all_modules if any(
                cfg in m.file_path.lower() for cfg in ['config', 'settings', '.env', 'package.json', 'requirements.txt']
            )],
            docker_files=[m.file_path for m in all_modules if any(
                docker in m.file_path.lower() for docker in ['dockerfile', 'docker-compose']
            )],
            kubernetes_files=[m.file_path for m in all_modules if any(
                k8s in m.file_path.lower() for k8s in ['k8s', 'kubernetes', 'deployment.yaml', 'service.yaml']
            )]
        )
        
        # Build class info
        class_info = {}
        for elem in all_elements:
            if elem.type == CodeElementType.CLASS:
                # Find methods in this class
                methods = [e.id for e in all_elements 
                          if e.type == CodeElementType.METHOD and 
                          e.file_path == elem.file_path and
                          e.name.startswith(elem.name)]
                class_info[elem.id] = ClassInfo(methods=methods)
        
        # Create graph
        graph = CodebaseGraph(
            metadata=metadata,
            modules=all_modules,
            elements=all_elements,
            dependencies=all_dependencies,
            class_info=class_info
        )
        
        # Build indexes
        graph.build_indexes()
        
        logger.info(f"Parsing complete: {len(all_elements)} elements, {len(all_dependencies)} dependencies")
        return graph
    
    def _find_main_entry_points(self, modules: List[Module]) -> List[str]:
        """Find main entry point files."""
        entry_points = []
        for module in modules:
            if any(indicator in module.name.lower() for indicator in 
                   ['main', 'app', 'index', '__main__', 'server']):
                entry_points.append(module.file_path)
        return entry_points
