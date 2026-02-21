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
    ClassInfo, AgentInfo, WorkflowInfo, DatabaseSchema, DatabaseTable,
    DatabaseColumn, DatabaseLanguage
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
        
        # Database file extensions
        self.database_extensions = {
            DatabaseLanguage.SQL: {'.sql'},
            DatabaseLanguage.POSTGRESQL: {'.sql'},
            DatabaseLanguage.MYSQL: {'.sql'},
            DatabaseLanguage.SQLITE: {'.sql', '.db', '.sqlite', '.sqlite3'},
        }
        
        # Ignore patterns
        self.ignore_patterns = [
            '__pycache__', '.git', '.svn', '.hg',
            'node_modules', '.venv', 'venv', 'env',
            '.pytest_cache', '.mypy_cache', '.idea', '.vscode',
            'dist', 'build', '.next', '.nuxt'
        ]
        
        # Agent detection patterns
        self.agent_keywords = ['agent', 'llm', 'rag', 'assistant', 'chatbot', 'gpt', 'claude', 'groq']
        self.agent_base_classes = ['Agent', 'BaseAgent', 'LLMAgent', 'RAGAgent', 'ToolAgent']
        
        # Workflow detection patterns
        self.workflow_keywords = ['workflow', 'pipeline', 'orchestrate', 'taskflow', 'dag', 'celery']
        self.workflow_decorators = ['@workflow', '@task', '@pipeline', '@celery_task']
        
        # Database detection patterns
        self.orm_patterns = {
            'sqlalchemy': ['SQLAlchemy', 'Base', 'declarative_base', 'db.Model'],
            'django': ['models.Model', 'django.db'],
            'peewee': ['Model', 'peewee'],
            'tortoise': ['tortoise.models', 'Model'],
            'mongodb': ['mongoengine', 'Document', 'pymongo'],
            'redis': ['redis', 'Redis'],
        }
    
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
            
            # Parse classes - store agent/workflow info in module metadata temporarily
            agent_info_temp = {}
            workflow_info_temp = {}
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Check if it's an agent
                    if self._is_agent_class(node, content):
                        agent_elem, agent_deps, agent_info = self._parse_python_agent(
                            node, file_path, repo_path, content
                        )
                        elements.append(agent_elem)
                        dependencies.extend(agent_deps)
                        module.element_ids.append(agent_elem.id)
                        agent_info_temp[agent_elem.id] = agent_info
                    # Check if it's a workflow
                    elif self._is_workflow_class(node, content):
                        workflow_elem, workflow_deps, workflow_info = self._parse_python_workflow(
                            node, file_path, repo_path, content
                        )
                        elements.append(workflow_elem)
                        dependencies.extend(workflow_deps)
                        module.element_ids.append(workflow_elem.id)
                        workflow_info_temp[workflow_elem.id] = workflow_info
                    # Regular class
                    else:
                        class_elem, class_deps = self._parse_python_class(
                            node, file_path, repo_path, content
                        )
                        elements.append(class_elem)
                        dependencies.extend(class_deps)
                        module.element_ids.append(class_elem.id)
            
            # Store agent/workflow info in module metadata for later extraction
            if agent_info_temp:
                module.metadata['agent_info'] = agent_info_temp
            if workflow_info_temp:
                module.metadata['workflow_info'] = workflow_info_temp
            
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
            
            # Detect database models/schemas
            db_elements, db_deps = self._detect_database_models(tree, file_path, repo_path, content)
            elements.extend(db_elements)
            dependencies.extend(db_deps)
            
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
        agent_info_dict = {}
        workflow_info_dict = {}
        database_schemas_list = []
        total_lines = 0
        languages_found = set()
        database_languages_found = set()
        
        files = self.get_all_files(repo_path)
        logger.info(f"Found {len(files)} files to parse")
        
        # Track database schemas by name
        db_schema_map = {}
        
        for file_path in files:
            try:
                elements, dependencies, module = self.parse_file(file_path, repo_path)
                all_elements.extend(elements)
                all_dependencies.extend(dependencies)
                all_modules.append(module)
                
                # Extract agent and workflow info from module metadata
                if 'agent_info' in module.metadata:
                    agent_info_dict.update(module.metadata['agent_info'])
                if 'workflow_info' in module.metadata:
                    workflow_info_dict.update(module.metadata['workflow_info'])
                
                # Also check elements for any missed agents/workflows
                for elem in elements:
                    if elem.type == CodeElementType.AGENT and elem.id not in agent_info_dict:
                        agent_info_dict[elem.id] = AgentInfo(
                            agent_type=elem.metadata.get("agent_type", "LLM"),
                            tools=[],
                            capabilities=[]
                        )
                    elif elem.type == CodeElementType.WORKFLOW and elem.id not in workflow_info_dict:
                        workflow_info_dict[elem.id] = WorkflowInfo(
                            workflow_type=elem.metadata.get("workflow_type", "sequential"),
                            steps=[],
                            agents=[]
                        )
                    elif elem.type == CodeElementType.DATABASE_TABLE:
                        # Group tables by schema
                        db_lang = DatabaseLanguage(elem.metadata.get("database_language", "unknown"))
                        database_languages_found.add(db_lang)
                        schema_name = elem.metadata.get("schema_name", "default")
                        if schema_name not in db_schema_map:
                            db_schema_map[schema_name] = DatabaseSchema(
                                name=schema_name,
                                database_language=db_lang,
                                tables=[],
                                orm_framework=elem.metadata.get("orm_framework")
                            )
                        # Create table entry
                        table = DatabaseTable(
                            name=elem.name,
                            columns=[]  # Would need to parse columns from code
                        )
                        db_schema_map[schema_name].tables.append(table)
                
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
        
        database_schemas_list = list(db_schema_map.values())
        
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
            database_languages=list(database_languages_found) if database_languages_found else [],
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
            class_info=class_info,
            agent_info=agent_info_dict,
            workflow_info=workflow_info_dict,
            database_schemas=database_schemas_list
        )
        
        # Build indexes
        graph.build_indexes()
        
        logger.info(f"Parsing complete: {len(all_elements)} elements, {len(all_dependencies)} dependencies")
        return graph
    
    def _is_agent_class(self, node: ast.ClassDef, content: str) -> bool:
        """Check if a class is an agent."""
        name_lower = node.name.lower()
        content_lower = content.lower()
        
        # Check name
        if any(keyword in name_lower for keyword in self.agent_keywords):
            return True
        
        # Check base classes
        for base in node.bases:
            base_str = ast.unparse(base) if hasattr(ast, 'unparse') else str(base)
            if any(agent_base.lower() in base_str.lower() for agent_base in self.agent_base_classes):
                return True
        
        # Check docstring/content
        docstring = ast.get_docstring(node) or ""
        if any(keyword in docstring.lower() for keyword in self.agent_keywords):
            return True
        
        return False
    
    def _is_workflow_class(self, node: ast.ClassDef, content: str) -> bool:
        """Check if a class is a workflow."""
        name_lower = node.name.lower()
        content_lower = content.lower()
        
        # Check name
        if any(keyword in name_lower for keyword in self.workflow_keywords):
            return True
        
        # Check decorators
        for decorator in node.decorator_list:
            decorator_str = ast.unparse(decorator) if hasattr(ast, 'unparse') else str(decorator)
            if any(wf_decorator.lower() in decorator_str.lower() for wf_decorator in self.workflow_decorators):
                return True
        
        return False
    
    def _parse_python_agent(self, node: ast.ClassDef, file_path: Path, 
                           repo_path: Path, content: str) -> tuple[CodeElement, List[Dependency], AgentInfo]:
        """Parse a Python agent class."""
        rel_path = str(file_path.relative_to(repo_path))
        element_id = f"agent:{rel_path}:{node.name}"
        
        docstring = ast.get_docstring(node)
        lines = content.split('\n')
        code_snippet = '\n'.join(lines[node.lineno-1:min(node.lineno+20, len(lines))])
        
        # Detect agent type
        agent_type = "LLM"
        llm_provider = None
        model_name = None
        
        content_lower = content.lower()
        if 'rag' in content_lower or 'retrieval' in content_lower:
            agent_type = "RAG"
        elif 'tool' in content_lower or 'function' in content_lower:
            agent_type = "Tool-using"
        
        # Detect LLM provider
        for provider in ['openai', 'groq', 'anthropic', 'cohere', 'huggingface']:
            if provider in content_lower:
                llm_provider = provider
                break
        
        # Extract tools/capabilities
        tools = []
        capabilities = []
        for child in node.body:
            if isinstance(child, ast.FunctionDef):
                if 'tool' in child.name.lower() or 'function' in child.name.lower():
                    tools.append(f"{element_id}.{child.name}")
                if any(cap in child.name.lower() for cap in ['process', 'analyze', 'generate', 'query']):
                    capabilities.append(child.name)
        
        element = CodeElement(
            id=element_id,
            name=node.name,
            type=CodeElementType.AGENT,
            file_path=rel_path,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            language=Language.PYTHON,
            docstring=docstring,
            code_snippet=code_snippet[:500],
            metadata={"agent_type": agent_type}
        )
        
        dependencies = []
        agent_info = AgentInfo(
            agent_type=agent_type,
            tools=tools,
            capabilities=capabilities,
            llm_provider=llm_provider,
            model_name=model_name
        )
        
        return element, dependencies, agent_info
    
    def _parse_python_workflow(self, node: ast.ClassDef, file_path: Path,
                              repo_path: Path, content: str) -> tuple[CodeElement, List[Dependency], WorkflowInfo]:
        """Parse a Python workflow class."""
        rel_path = str(file_path.relative_to(repo_path))
        element_id = f"workflow:{rel_path}:{node.name}"
        
        docstring = ast.get_docstring(node)
        lines = content.split('\n')
        code_snippet = '\n'.join(lines[node.lineno-1:min(node.lineno+20, len(lines))])
        
        # Detect workflow type
        workflow_type = "sequential"
        content_lower = content.lower()
        if 'parallel' in content_lower or 'async' in content_lower:
            workflow_type = "parallel"
        elif 'conditional' in content_lower or 'if' in content_lower:
            workflow_type = "conditional"
        
        # Extract steps
        steps = []
        agents = []
        for child in node.body:
            if isinstance(child, ast.FunctionDef):
                steps.append(f"{element_id}.{child.name}")
                # Check if step uses agents
                child_content = ast.unparse(child) if hasattr(ast, 'unparse') else str(child)
                if 'agent' in child_content.lower():
                    agents.append(f"{element_id}.{child.name}")
        
        element = CodeElement(
            id=element_id,
            name=node.name,
            type=CodeElementType.WORKFLOW,
            file_path=rel_path,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            language=Language.PYTHON,
            docstring=docstring,
            code_snippet=code_snippet[:500],
            metadata={"workflow_type": workflow_type}
        )
        
        dependencies = []
        workflow_info = WorkflowInfo(
            workflow_type=workflow_type,
            steps=steps,
            agents=agents
        )
        
        return element, dependencies, workflow_info
    
    def _detect_database_models(self, tree: ast.AST, file_path: Path,
                                repo_path: Path, content: str) -> tuple[List[CodeElement], List[Dependency]]:
        """Detect database models/schemas in Python file."""
        elements = []
        dependencies = []
        rel_path = str(file_path.relative_to(repo_path))
        content_lower = content.lower()
        
        # Detect ORM framework
        orm_framework = None
        db_language = DatabaseLanguage.UNKNOWN
        
        for orm_name, patterns in self.orm_patterns.items():
            if any(pattern.lower() in content_lower for pattern in patterns):
                orm_framework = orm_name
                if orm_name == 'mongodb':
                    db_language = DatabaseLanguage.MONGODB
                elif orm_name == 'redis':
                    db_language = DatabaseLanguage.REDIS
                else:
                    db_language = DatabaseLanguage.SQL
                break
        
        if not orm_framework:
            return elements, dependencies
        
        # Find model classes
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if it's a database model
                is_model = False
                for base in node.bases:
                    base_str = ast.unparse(base) if hasattr(ast, 'unparse') else str(base)
                    if any(pattern.lower() in base_str.lower() for pattern in self.orm_patterns.get(orm_framework, [])):
                        is_model = True
                        break
                
                if is_model:
                    element_id = f"database_table:{rel_path}:{node.name}"
                    docstring = ast.get_docstring(node)
                    lines = content.split('\n')
                    code_snippet = '\n'.join(lines[node.lineno-1:min(node.lineno+20, len(lines))])
                    
                    element = CodeElement(
                        id=element_id,
                        name=node.name,
                        type=CodeElementType.DATABASE_TABLE,
                        file_path=rel_path,
                        line_start=node.lineno,
                        line_end=node.end_lineno or node.lineno,
                        language=Language.PYTHON,
                        docstring=docstring,
                        code_snippet=code_snippet[:500],
                        metadata={"orm_framework": orm_framework, "database_language": db_language.value}
                    )
                    elements.append(element)
        
        return elements, dependencies
    
    def _find_main_entry_points(self, modules: List[Module]) -> List[str]:
        """Find main entry point files."""
        entry_points = []
        for module in modules:
            if any(indicator in module.name.lower() for indicator in 
                   ['main', 'app', 'index', '__main__', 'server']):
                entry_points.append(module.file_path)
        return entry_points


# ============================================================================
# Simple standalone functions for basic parsing (returns dict format)
# ============================================================================

def parse_repository(repo_path: str) -> Dict[str, Any]:
    """
    Simple function to parse repository and return dictionary format.
    This is a wrapper that extracts basic info from Python files.
    
    Args:
        repo_path: Path to the repository root
        
    Returns:
        Dictionary containing services, schemas, endpoints, fields, and imports
    """
    import ast
    from pathlib import Path
    
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
        if "__pycache__" in str(py_file) or "venv" in str(py_file) or ".venv" in str(py_file):
            continue
            
        try:
            file_data = parse_file_simple(str(py_file))
            
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


def parse_file_simple(file_path: str) -> Dict[str, Any]:
    """
    Parse a single Python file and extract metadata (simple version).
    
    Args:
        file_path: Path to the Python file
        
    Returns:
        Dictionary with services, schemas, endpoints, fields, and imports
    """
    import ast
    
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
        imports = _extract_imports_simple(tree)
        result["imports"][file_path] = imports
        
        # Walk through AST nodes
        for node in ast.walk(tree):
            # Extract classes (services, schemas)
            if isinstance(node, ast.ClassDef):
                class_info = _extract_class_info_simple(node, file_path)
                
                # Determine if it's a service or schema
                if _is_service_class_simple(node):
                    result["services"][class_info["name"]] = class_info
                elif _is_schema_class_simple(node):
                    result["schemas"][class_info["name"]] = class_info
                    # Extract fields from schema
                    fields = _extract_class_fields_simple(node)
                    result["fields"][class_info["name"]] = fields
            
            # Extract functions (endpoints, main functions)
            elif isinstance(node, ast.FunctionDef):
                func_info = _extract_function_info_simple(node, file_path)
                
                # Check if it's an endpoint (decorated with @router, @app, etc.)
                if _is_endpoint_simple(node):
                    result["endpoints"].append(func_info)
    
    except Exception as e:
        # Return empty result if parsing fails
        pass
    
    return result


def _extract_imports_simple(tree: ast.AST) -> List[str]:
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


def _extract_class_info_simple(node: ast.ClassDef, file_path: str) -> Dict[str, Any]:
    """Extract information about a class."""
    return {
        "name": node.name,
        "file_path": file_path,
        "bases": [_node_to_string_simple(base) for base in node.bases],
        "methods": [n.name for n in node.body if isinstance(n, ast.FunctionDef)],
        "line_number": node.lineno
    }


def _extract_class_fields_simple(node: ast.ClassDef) -> Dict[str, Any]:
    """Extract fields from a class (for schemas)."""
    fields = {}
    
    for item in node.body:
        # Check for class variables or annotations
        if isinstance(item, ast.AnnAssign):
            if isinstance(item.target, ast.Name):
                field_name = item.target.id
                field_type = _node_to_string_simple(item.annotation)
                fields[field_name] = {"type": field_type}
        
        # Check for assignments (like in Pydantic models)
        elif isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name):
                    fields[target.id] = {"type": "Any"}
    
    return fields


def _extract_function_info_simple(node: ast.FunctionDef, file_path: str) -> Dict[str, Any]:
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
            param_info["type"] = _node_to_string_simple(arg.annotation)
        params.append(param_info)
    
    return {
        "name": node.name,
        "file_path": file_path,
        "decorators": decorators,
        "parameters": params,
        "line_number": node.lineno
    }


def _is_service_class_simple(node: ast.ClassDef) -> bool:
    """Check if a class is a service."""
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


def _is_schema_class_simple(node: ast.ClassDef) -> bool:
    """Check if a class is a schema/model."""
    schema_keywords = ["schema", "model", "dto", "entity"]
    name_lower = node.name.lower()
    
    if any(keyword in name_lower for keyword in schema_keywords):
        return True
    
    # Check base classes
    for base in node.bases:
        base_str = _node_to_string_simple(base)
        if "BaseModel" in base_str or "Schema" in base_str or "Model" in base_str:
            return True
    
    return False


def _is_endpoint_simple(node: ast.FunctionDef) -> bool:
    """Check if a function is an API endpoint."""
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


def _node_to_string_simple(node: ast.AST) -> str:
    """Convert AST node to string representation."""
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        return f"{_node_to_string_simple(node.value)}.{node.attr}"
    elif isinstance(node, ast.Constant):
        return str(node.value)
    elif hasattr(ast, "unparse"):
        return ast.unparse(node)
    else:
        return str(type(node).__name__)

