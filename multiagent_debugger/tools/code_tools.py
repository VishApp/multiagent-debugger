import os
import ast
import re
import json
from typing import Dict, Any, List, Optional, Set, Tuple
from pathlib import Path
from dataclasses import dataclass
from collections import defaultdict

from crewai.tools import tool

# Global cache to prevent repeated tool calls
_code_analysis_cache = {}

@dataclass
class CodeElement:
    name: str
    type: str  # function, class, method, variable
    file_path: str
    line_number: int
    source: str
    dependencies: List[str] = None
    decorators: List[str] = None
    parameters: List[str] = None
    return_type: str = None
    docstring: str = None

@dataclass
class ErrorHandler:
    type: str  # try_except, if_error, decorator
    file_path: str
    line_number: int
    source: str
    exception_types: List[str] = None
    error_messages: List[str] = None
    context_function: str = None

def clear_code_analysis_cache():
    """Clear the code analysis cache."""
    global _code_analysis_cache
    _code_analysis_cache.clear()
    print("[DEBUG] Code analysis cache cleared")

def get_code_cache_stats():
    """Get statistics about the code analysis cache."""
    return {
        "cache_size": len(_code_analysis_cache),
        "cached_keys": list(_code_analysis_cache.keys())
    }

class CodeAnalyzer:
    """Enhanced code analyzer with comprehensive AST analysis."""
    
    def __init__(self, code_path: str):
        self.code_path = code_path
        self.source_files = self._find_source_files()
        self.parsed_files = {}
        self.imports_map = defaultdict(set)
        self.functions_map = defaultdict(list)
        self.classes_map = defaultdict(list)
        
    def _find_source_files(self) -> List[Path]:
        """Find all source code files in the given path."""
        if not os.path.exists(self.code_path):
            return []
            
        # Supported source file extensions
        source_extensions = {
            '.py', '.js', '.ts', '.jsx', '.tsx',  # Python, JavaScript, TypeScript
            '.java', '.kt', '.scala',             # JVM languages
            '.c', '.cpp', '.cc', '.cxx', '.h', '.hpp',  # C/C++
            '.go',                                # Go
            '.rs',                                # Rust
            '.php',                               # PHP
            '.rb',                                # Ruby
            '.cs',                                # C#
            '.swift',                             # Swift
            '.clj', '.cljs',                      # Clojure
            '.hs',                                # Haskell
            '.ml', '.mli',                        # OCaml
            '.fs', '.fsi',                        # F#
            '.vb',                                # Visual Basic
            '.pl', '.pm',                         # Perl
            '.sh', '.bash',                       # Shell
            '.sql'                                # SQL
        }
            
        path_obj = Path(self.code_path)
        if path_obj.is_file() and path_obj.suffix in source_extensions:
            return [path_obj]
        
        source_files = []
        for root, _, files in os.walk(self.code_path):
            for file in files:
                file_path = Path(root) / file
                if file_path.suffix in source_extensions:
                    source_files.append(file_path)
        
        return source_files
    
    def _parse_file(self, file_path: Path) -> Optional[ast.AST]:
        """Parse a source file and return its content (AST for Python, raw content for others)."""
        if str(file_path) in self.parsed_files:
            return self.parsed_files[str(file_path)].get('tree')
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # For Python files, try to parse AST
                if file_path.suffix == '.py':
                    try:
                        tree = ast.parse(content)
                        self.parsed_files[str(file_path)] = {
                            'tree': tree,
                            'content': content,
                            'lines': content.splitlines(),
                            'language': 'python'
                        }
                        return tree
                    except SyntaxError as e:
                        print(f"[DEBUG] Could not parse Python AST for {file_path}: {e}")
                        # Fall through to store content without AST
                
                # For all files (including non-Python), store content
                self.parsed_files[str(file_path)] = {
                    'tree': None,
                    'content': content,
                    'lines': content.splitlines(),
                    'language': self._detect_language(file_path)
                }
                return None
                
        except UnicodeDecodeError as e:
            print(f"[DEBUG] Could not read {file_path}: {e}")
            return None
    
    def _detect_language(self, file_path: Path) -> str:
        """Detect the programming language based on file extension."""
        extension_map = {
            '.py': 'python',
            '.js': 'javascript', '.jsx': 'javascript',
            '.ts': 'typescript', '.tsx': 'typescript',
            '.java': 'java',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.c': 'c', '.h': 'c',
            '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp', '.hpp': 'cpp',
            '.go': 'go',
            '.rs': 'rust',
            '.php': 'php',
            '.rb': 'ruby',
            '.cs': 'csharp',
            '.swift': 'swift',
            '.clj': 'clojure', '.cljs': 'clojure',
            '.hs': 'haskell',
            '.ml': 'ocaml', '.mli': 'ocaml',
            '.fs': 'fsharp', '.fsi': 'fsharp',
            '.vb': 'vb',
            '.pl': 'perl', '.pm': 'perl',
            '.sh': 'shell', '.bash': 'shell',
            '.sql': 'sql'
        }
        return extension_map.get(file_path.suffix, 'unknown')
    
    def _extract_source_lines(self, file_path: str, start_line: int, end_line: int = None) -> str:
        """Extract source code lines from a file."""
        if file_path not in self.parsed_files:
            return ""
            
        lines = self.parsed_files[file_path]['lines']
        if end_line is None:
            end_line = start_line
            
        # Adjust for 0-based indexing
        start_idx = max(0, start_line - 1)
        end_idx = min(len(lines), end_line)
        
        return '\n'.join(lines[start_idx:end_idx])
    
    def find_api_handlers(self, api_route: str) -> List[CodeElement]:
        """Find API handler functions for a specific route."""
        handlers = []
        clean_route = api_route.strip('/')
        
        for file_path in self.source_files:
            tree = self._parse_file(file_path)
            if not tree:
                continue
                
            content = self.parsed_files[str(file_path)]['content']
            
            # Check if file contains the API route
            route_patterns = [
                rf'[\'"]/?{re.escape(clean_route)}[\'"]',
                rf'[\'"]/?{re.escape(api_route)}[\'"]',
                rf'{re.escape(clean_route)}',
                rf'{re.escape(api_route)}'
            ]
            
            if not any(re.search(pattern, content, re.IGNORECASE) for pattern in route_patterns):
                continue
            
            # Analyze AST for API handlers
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    handler = self._analyze_function_as_handler(node, file_path, clean_route, api_route)
                    if handler:
                        handlers.append(handler)
                        
                elif isinstance(node, ast.Call):
                    handler = self._analyze_call_as_handler(node, file_path, clean_route, api_route)
                    if handler:
                        handlers.append(handler)
        
        return handlers
    
    def _analyze_function_as_handler(self, node: ast.FunctionDef, file_path: Path, clean_route: str, api_route: str) -> Optional[CodeElement]:
        """Analyze a function to see if it's an API handler."""
        # Check decorators for route information
        route_decorators = ['route', 'get', 'post', 'put', 'delete', 'patch', 'head', 'options']
        
        for decorator in node.decorator_list:
            decorator_name = ""
            
            if isinstance(decorator, ast.Name):
                decorator_name = decorator.id
            elif isinstance(decorator, ast.Attribute):
                decorator_name = decorator.attr
            elif isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Name):
                    decorator_name = decorator.func.id
                elif isinstance(decorator.func, ast.Attribute):
                    decorator_name = decorator.func.attr
            
            if decorator_name.lower() in route_decorators:
                # Check if decorator contains the route
                if self._decorator_contains_route(decorator, clean_route, api_route):
                    return self._create_code_element_from_function(node, file_path)
        
        # Check if function name suggests it handles the route
        function_name_lower = node.name.lower()
        route_parts = clean_route.lower().replace('/', '_').replace('-', '_').split('_')
        
        if any(part in function_name_lower for part in route_parts if len(part) > 2):
            return self._create_code_element_from_function(node, file_path)
        
        return None
    
    def _decorator_contains_route(self, decorator: ast.AST, clean_route: str, api_route: str) -> bool:
        """Check if a decorator contains the specified route."""
        def extract_strings(node):
            strings = []
            if isinstance(node, ast.Str):
                strings.append(node.s)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                strings.append(node.value)
            elif hasattr(node, 'args'):
                for arg in node.args:
                    strings.extend(extract_strings(arg))
            elif hasattr(node, 'keywords'):
                for kw in node.keywords:
                    strings.extend(extract_strings(kw.value))
            return strings
        
        strings = extract_strings(decorator)
        return any(clean_route in s or api_route in s for s in strings)
    
    def _analyze_call_as_handler(self, node: ast.Call, file_path: Path, clean_route: str, api_route: str) -> Optional[CodeElement]:
        """Analyze a function call to see if it registers an API handler."""
        # Check for route registration patterns
        if isinstance(node.func, ast.Attribute):
            method_name = node.func.attr
            if method_name in ['add_url_rule', 'register', 'route']:
                # Check arguments for the route
                for arg in node.args:
                    if isinstance(arg, (ast.Str, ast.Constant)):
                        value = arg.s if isinstance(arg, ast.Str) else arg.value
                        if isinstance(value, str) and (clean_route in value or api_route in value):
                            source = self._extract_source_lines(str(file_path), node.lineno, getattr(node, 'end_lineno', node.lineno))
                            return CodeElement(
                                name=f"route_registration_{method_name}",
                                type="route_registration",
                                file_path=str(file_path),
                                line_number=node.lineno,
                                source=source
                            )
        
        return None
    
    def _create_code_element_from_function(self, node: ast.FunctionDef, file_path: Path) -> CodeElement:
        """Create a CodeElement from a function AST node."""
        # Extract function source
        start_line = node.lineno
        end_line = getattr(node, 'end_lineno', start_line + 10)  # Fallback estimation
        source = self._extract_source_lines(str(file_path), start_line, end_line)
        
        # Extract decorators
        decorators = []
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                decorators.append(decorator.id)
            elif isinstance(decorator, ast.Attribute):
                decorators.append(decorator.attr)
            elif isinstance(decorator, ast.Call):
                decorators.append(ast.unparse(decorator) if hasattr(ast, 'unparse') else str(decorator))
        
        # Extract parameters
        parameters = [arg.arg for arg in node.args.args]
        
        # Extract docstring
        docstring = ast.get_docstring(node)
        
        # Extract return type annotation
        return_type = None
        if node.returns:
            return_type = ast.unparse(node.returns) if hasattr(ast, 'unparse') else str(node.returns)
        
        return CodeElement(
            name=node.name,
            type="function",
            file_path=str(file_path),
            line_number=start_line,
            source=source,
            decorators=decorators,
            parameters=parameters,
            return_type=return_type,
            docstring=docstring
        )
    
    def find_dependencies(self, function_name: str = None, file_path: str = None) -> Dict[str, List[str]]:
        """Find dependencies for a function or file."""
        dependencies = {
            'imports': [],
            'function_calls': [],
            'class_usage': [],
            'external_modules': [],
            'database_calls': [],
            'api_calls': [],
            'file_operations': []
        }
        
        target_files = []
        if file_path:
            if os.path.exists(file_path):
                target_files = [Path(file_path)]
        else:
            target_files = self.source_files
        
        for file in target_files:
            tree = self._parse_file(file)
            if not tree:
                continue
            
            # Analyze imports
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    imports = self._extract_imports(node)
                    dependencies['imports'].extend(imports)
                
                elif isinstance(node, ast.Call):
                    call_info = self._analyze_function_call(node)
                    if call_info:
                        dependencies['function_calls'].append(call_info)
                        
                        # Categorize special types of calls
                        if self._is_database_call(call_info):
                            dependencies['database_calls'].append(call_info)
                        elif self._is_api_call(call_info):
                            dependencies['api_calls'].append(call_info)
                        elif self._is_file_operation(call_info):
                            dependencies['file_operations'].append(call_info)
                
                elif isinstance(node, ast.Name):
                    # Track variable/class usage
                    if function_name and self._is_in_function(node, function_name, tree):
                        dependencies['class_usage'].append(node.id)
        
        # Remove duplicates
        for key in dependencies:
            if isinstance(dependencies[key], list):
                dependencies[key] = list(set(dependencies[key]))
        
        return dependencies
    
    def find_error_handlers(self, file_path: str = None, function_name: str = None) -> List[ErrorHandler]:
        """Find error handling code in the codebase."""
        error_handlers = []
        
        target_files = []
        if file_path and os.path.exists(file_path):
            target_files = [Path(file_path)]
        else:
            target_files = self.source_files
        
        for file in target_files:
            # Parse the file (AST for Python, content for others)
            tree = self._parse_file(file)
            
            # Get file content and language
            file_info = self.parsed_files.get(str(file))
            if not file_info:
                continue
                
            language = file_info.get('language', 'unknown')
            content = file_info.get('content', '')
            
            # For Python files, use AST analysis
            if language == 'python' and tree:
                for node in ast.walk(tree):
                    # Find try-except blocks
                    if isinstance(node, ast.Try):
                        error_handler = self._analyze_try_except(node, file, function_name)
                        if error_handler:
                            error_handlers.append(error_handler)
                    
                    # Find error-checking if statements
                    elif isinstance(node, ast.If):
                        error_handler = self._analyze_error_if(node, file, function_name)
                        if error_handler:
                            error_handlers.append(error_handler)
                    
                    # Find error handling decorators
                    elif isinstance(node, ast.FunctionDef):
                        for decorator in node.decorator_list:
                            error_handler = self._analyze_error_decorator(decorator, node, file)
                            if error_handler:
                                error_handlers.append(error_handler)
            
            # For all files, use text-based analysis
            text_handlers = self._analyze_text_error_patterns(file, content, language, function_name)
            error_handlers.extend(text_handlers)
        
        return error_handlers
    
    def _analyze_text_error_patterns(self, file_path: Path, content: str, language: str, function_name: str = None) -> List[ErrorHandler]:
        """Analyze error patterns using text-based analysis for any language."""
        error_handlers = []
        lines = content.splitlines()
        
        # Language-specific error patterns
        error_patterns = {
            'python': [
                r'try\s*:', r'except\s+\w+', r'raise\s+\w+', r'assert\s+',
                r'if\s+.*error', r'if\s+.*exception', r'if\s+.*fail',
                r'logging\.error', r'logger\.error', r'print.*error'
            ],
            'go': [
                r'if\s+err\s*!=\s*nil', r'panic\(', r'recover\(\)',
                r'return\s+.*err', r'fmt\.Errorf', r'log\.Error',
                r'errors\.New', r'errors\.Wrap', r'fmt\.Println.*err',
                r'defer\s+.*\(\)', r'goroutine', r'channel', r'interface\s*\{\}',
                r'var\s+\w+\s*\*', r'&.*\{', r'\.\*', r'\.\(',
                r'panic:\s+runtime\s+error', r'panic:\s+interface\s+conversion'
            ],
            'javascript': [
                r'try\s*{', r'catch\s*\(', r'throw\s+', r'if\s*\(.*error',
                r'\.catch\(', r'Promise\.reject', r'console\.error'
            ],
            'typescript': [
                r'try\s*{', r'catch\s*\(', r'throw\s+', r'if\s*\(.*error',
                r'\.catch\(', r'Promise\.reject', r'console\.error'
            ],
            'java': [
                r'try\s*{', r'catch\s*\(', r'throw\s+', r'throws\s+\w+',
                r'if\s*\(.*error', r'Exception', r'RuntimeException'
            ],
            'rust': [
                r'Result<', r'Option<', r'match\s+', r'\.unwrap\(',
                r'\.expect\(', r'panic!', r'if\s+.*\.is_err\('
            ],
            'c': [
                r'if\s*\(.*error', r'if\s*\(.*fail', r'return\s+-?\d+',
                r'exit\(', r'assert\(', r'perror\('
            ],
            'cpp': [
                r'try\s*{', r'catch\s*\(', r'throw\s+', r'if\s*\(.*error',
                r'std::exception', r'std::runtime_error'
            ]
        }
        
        patterns = error_patterns.get(language, error_patterns.get('javascript', []))
        
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            for pattern in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    # Extract context around the error pattern
                    start_line = max(0, i - 1)
                    end_line = min(len(lines), i + 3)
                    context_lines = lines[start_line:end_line]
                    
                    error_handlers.append(ErrorHandler(
                        type=f"{language}_error_pattern",
                        file_path=str(file_path),
                        line_number=i + 1,
                        source='\n'.join(context_lines),
                        context_function=function_name
                    ))
                    break  # One match per line
        
        return error_handlers
    
    def _extract_imports(self, node: ast.AST) -> List[str]:
        """Extract import statements."""
        imports = []
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append(f"{module}.{alias.name}" if module else alias.name)
        return imports
    
    def _analyze_function_call(self, node: ast.Call) -> Optional[str]:
        """Analyze a function call and return call information."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            # Try to reconstruct the full call
            parts = []
            current = node.func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return '.'.join(reversed(parts))
        return None
    
    def _is_database_call(self, call_info: str) -> bool:
        """Check if a function call is database-related."""
        db_patterns = ['execute', 'query', 'select', 'insert', 'update', 'delete', 'commit', 'rollback', 'connect']
        return any(pattern in call_info.lower() for pattern in db_patterns)
    
    def _is_api_call(self, call_info: str) -> bool:
        """Check if a function call is API-related."""
        api_patterns = ['requests.', 'get', 'post', 'put', 'delete', 'patch', 'fetch', 'http']
        return any(pattern in call_info.lower() for pattern in api_patterns)
    
    def _is_file_operation(self, call_info: str) -> bool:
        """Check if a function call is file operation-related."""
        file_patterns = ['open', 'read', 'write', 'close', 'os.path', 'pathlib']
        return any(pattern in call_info.lower() for pattern in file_patterns)
    
    def _is_in_function(self, node: ast.AST, function_name: str, tree: ast.AST) -> bool:
        """Check if a node is inside a specific function."""
        for func_node in ast.walk(tree):
            if isinstance(func_node, ast.FunctionDef) and func_node.name == function_name:
                return (node.lineno >= func_node.lineno and 
                       node.lineno <= getattr(func_node, 'end_lineno', func_node.lineno + 100))
        return False
    
    def _analyze_try_except(self, node: ast.Try, file_path: Path, function_name: str = None) -> Optional[ErrorHandler]:
        """Analyze a try-except block."""
        exception_types = []
        error_messages = []
        
        for handler in node.handlers:
            if handler.type:
                if isinstance(handler.type, ast.Name):
                    exception_types.append(handler.type.id)
                elif isinstance(handler.type, ast.Tuple):
                    for elt in handler.type.elts:
                        if isinstance(elt, ast.Name):
                            exception_types.append(elt.id)
        
        # Extract error messages from the handler
        for handler in node.handlers:
            for stmt in handler.body:
                if isinstance(stmt, ast.Raise) and stmt.exc:
                    if isinstance(stmt.exc, ast.Call) and len(stmt.exc.args) > 0:
                        if isinstance(stmt.exc.args[0], (ast.Str, ast.Constant)):
                            msg = stmt.exc.args[0].s if isinstance(stmt.exc.args[0], ast.Str) else stmt.exc.args[0].value
                            if isinstance(msg, str):
                                error_messages.append(msg)
        
        source = self._extract_source_lines(str(file_path), node.lineno, getattr(node, 'end_lineno', node.lineno + 5))
        
        return ErrorHandler(
            type="try_except",
            file_path=str(file_path),
            line_number=node.lineno,
            source=source,
            exception_types=exception_types,
            error_messages=error_messages,
            context_function=function_name
        )
    
    def _analyze_error_if(self, node: ast.If, file_path: Path, function_name: str = None) -> Optional[ErrorHandler]:
        """Analyze if statements that might be error checks."""
        # Look for common error checking patterns
        error_patterns = ['error', 'exception', 'fail', 'invalid', 'none', 'null']
        
        # Convert test to string for pattern matching
        test_str = ast.unparse(node.test) if hasattr(ast, 'unparse') else str(node.test)
        
        if any(pattern in test_str.lower() for pattern in error_patterns):
            source = self._extract_source_lines(str(file_path), node.lineno, getattr(node, 'end_lineno', node.lineno + 3))
            
            return ErrorHandler(
                type="if_error",
                file_path=str(file_path),
                line_number=node.lineno,
                source=source,
                context_function=function_name
            )
        
        return None
    
    def _analyze_error_decorator(self, decorator: ast.AST, func_node: ast.FunctionDef, file_path: Path) -> Optional[ErrorHandler]:
        """Analyze decorators that might handle errors."""
        error_decorator_patterns = ['error_handler', 'exception_handler', 'catch', 'retry']
        
        decorator_name = ""
        if isinstance(decorator, ast.Name):
            decorator_name = decorator.id
        elif isinstance(decorator, ast.Attribute):
            decorator_name = decorator.attr
        elif isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Name):
                decorator_name = decorator.func.id
            elif isinstance(decorator.func, ast.Attribute):
                decorator_name = decorator.func.attr
        
        if any(pattern in decorator_name.lower() for pattern in error_decorator_patterns):
            source = self._extract_source_lines(str(file_path), func_node.lineno, func_node.lineno)
            
            return ErrorHandler(
                type="decorator",
                file_path=str(file_path),
                line_number=func_node.lineno,
                source=source,
                context_function=func_node.name
            )
        
        return None

def create_find_api_handlers_tool(code_path: str = None):
    """Create an enhanced find API handlers tool."""
    @tool("find_api_handlers")
    def find_api_handlers_tool(api_route: str, code_path: str = None) -> str:
        """Find API handler functions in the codebase for a specific API route.
        
        Args:
            api_route: The API route to find handlers for
            code_path: Optional code path (if not provided, will use default or extracted path)
            
        Returns:
            String containing detailed information about found API handlers
        """
        # Use provided code_path or fall back to default
        effective_code_path = code_path or ""
        
        # Check cache
        cache_key = f"api_handlers_{api_route}_{effective_code_path}"
        if cache_key in _code_analysis_cache:
            return f"[CACHED RESULT] {_code_analysis_cache[cache_key]}"
        
        if not effective_code_path:
            result = "❌ ERROR: No code path provided. Cannot perform code analysis."
            _code_analysis_cache[cache_key] = result
            return result
        
        if not os.path.exists(effective_code_path):
            result = f"❌ ERROR: Code path does not exist: {effective_code_path}"
            _code_analysis_cache[cache_key] = result
            return result
        
        try:
            analyzer = CodeAnalyzer(effective_code_path)
            handlers = analyzer.find_api_handlers(api_route)
            
            if not handlers:
                result = f"No API handlers found for route '{api_route}'."
                _code_analysis_cache[cache_key] = result
                return result
            
            # Format results
            results = [f"🔍 API HANDLERS FOUND FOR ROUTE '{api_route}'\n"]
            
            for i, handler in enumerate(handlers, 1):
                results.append(f"📍 HANDLER #{i}:")
                results.append(f"  Name: {handler.name}")
                results.append(f"  Type: {handler.type}")
                results.append(f"  File: {handler.file_path}:{handler.line_number}")
                
                if handler.decorators:
                    results.append(f"  Decorators: {', '.join(handler.decorators)}")
                
                if handler.parameters:
                    results.append(f"  Parameters: {', '.join(handler.parameters)}")
                
                if handler.return_type:
                    results.append(f"  Return Type: {handler.return_type}")
                
                if handler.docstring:
                    results.append(f"  Description: {handler.docstring[:100]}...")
                
                results.append(f"  Source Code:")
                # Determine language from file extension
                file_ext = handler.file_path.split('.')[-1] if '.' in handler.file_path else 'text'
                results.append(f"```{file_ext}")
                results.append(handler.source)
                results.append(f"```\n")
            
            result = "\n".join(results)
            _code_analysis_cache[cache_key] = result
            return result
            
        except Exception as e:
            result = f"Error analyzing API handlers: {str(e)}"
            _code_analysis_cache[cache_key] = result
            return result
    
    return find_api_handlers_tool

def create_find_dependencies_tool(code_path: str = None):
    """Create an enhanced find dependencies tool."""
    @tool("find_dependencies")
    def find_dependencies_tool(function_name: str = "", file_path: str = "", code_path: str = "") -> str:
        """Find dependencies of a specific function or module.
        
        Args:
            function_name: Name of the function to analyze (can be empty string)
            file_path: Path to the file to analyze (can be empty string)
            code_path: Code path (if not provided, will use default or extracted path)
            
        Returns:
            String containing detailed dependency information
        """
        # Use provided code_path or fall back to default
        effective_code_path = code_path or ""
        
        # Check cache
        cache_key = f"dependencies_{function_name}_{file_path}_{effective_code_path}"
        if cache_key in _code_analysis_cache:
            return f"[CACHED RESULT] {_code_analysis_cache[cache_key]}"
        
        if not effective_code_path or not os.path.exists(effective_code_path):
            result = "No valid code path provided."
            _code_analysis_cache[cache_key] = result
            return result
        
        # Convert empty strings to None for the analyzer
        function_name = function_name if function_name else None
        file_path = file_path if file_path else None
        
        if not function_name and not file_path:
            result = "Please provide either a function name or a file path."
            _code_analysis_cache[cache_key] = result
            return result
        
        try:
            analyzer = CodeAnalyzer(effective_code_path)
            dependencies = analyzer.find_dependencies(function_name, file_path)
            
            # Format results
            results = [f"🔗 DEPENDENCY ANALYSIS"]
            if function_name:
                results.append(f"Function: {function_name}")
            if file_path:
                results.append(f"File: {file_path}")
            results.append("")
            
            for dep_type, dep_list in dependencies.items():
                if dep_list:
                    results.append(f"📦 {dep_type.upper().replace('_', ' ')}:")
                    for dep in dep_list[:10]:  # Limit to first 10
                        results.append(f"  • {dep}")
                    if len(dep_list) > 10:
                        results.append(f"  ... and {len(dep_list) - 10} more")
                    results.append("")
            
            # Add summary
            total_deps = sum(len(deps) for deps in dependencies.values())
            results.append(f"📊 SUMMARY: {total_deps} total dependencies found")
            
            result = "\n".join(results)
            _code_analysis_cache[cache_key] = result
            return result
            
        except Exception as e:
            result = f"Error analyzing dependencies: {str(e)}"
            _code_analysis_cache[cache_key] = result
            return result
    
    return find_dependencies_tool

def create_find_error_handlers_tool(code_path: str = None):
    """Create an enhanced find error handlers tool."""
    @tool("find_error_handlers")
    def find_error_handlers_tool(file_path: str = "", function_name: str = "", code_path: str = "") -> str:
        """Find error handling code in the codebase.
        
        Args:
            file_path: Path to the file to search in (can be empty string)
            function_name: Name of the function to search in (can be empty string)
            code_path: Code path (if not provided, will use default or extracted path)
            
        Returns:
            String containing detailed error handler information
        """
        # Use provided code_path or fall back to default
        effective_code_path = code_path or ""
        
        # Check cache
        cache_key = f"error_handlers_{file_path}_{function_name}_{effective_code_path}"
        if cache_key in _code_analysis_cache:
            return f"[CACHED RESULT] {_code_analysis_cache[cache_key]}"
        
        if not effective_code_path or not os.path.exists(effective_code_path):
            result = "No valid code path provided."
            _code_analysis_cache[cache_key] = result
            return result
        
        # Convert empty strings to None for the analyzer
        file_path = file_path if file_path else None
        function_name = function_name if function_name else None
        
        if not file_path:
            result = "Please provide a file path to search for error handlers."
            _code_analysis_cache[cache_key] = result
            return result
        
        try:
            analyzer = CodeAnalyzer(effective_code_path)
            error_handlers = analyzer.find_error_handlers(file_path, function_name)
            
            if not error_handlers:
                result = "No error handlers found."
                _code_analysis_cache[cache_key] = result
                return result
            
            # Format results
            results = [f"⚠️ ERROR HANDLERS FOUND\n"]
            
            for i, handler in enumerate(error_handlers, 1):
                results.append(f"🛡️ ERROR HANDLER #{i}:")
                results.append(f"  Type: {handler.type}")
                results.append(f"  File: {handler.file_path}:{handler.line_number}")
                
                if handler.context_function:
                    results.append(f"  Function: {handler.context_function}")
                
                if handler.exception_types:
                    results.append(f"  Exception Types: {', '.join(handler.exception_types)}")
                
                if handler.error_messages:
                    results.append(f"  Error Messages: {', '.join(handler.error_messages[:3])}")
                
                results.append(f"  Source Code:")
                # Determine language from file extension
                file_ext = handler.file_path.split('.')[-1] if '.' in handler.file_path else 'text'
                results.append(f"```{file_ext}")
                results.append(handler.source)
                results.append(f"```\n")
            
            result = "\n".join(results)
            _code_analysis_cache[cache_key] = result
            return result
            
        except Exception as e:
            result = f"Error analyzing error handlers: {str(e)}"
            _code_analysis_cache[cache_key] = result
            return result
    
    return find_error_handlers_tool

# SMART MULTI-LANGUAGE TOOLS IMPLEMENTATION

import os
import re
import glob
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Optional
from crewai.tools import tool

# 1. SMART MULTI-LANGUAGE SEARCH TOOL
def create_smart_multilang_search_tool(code_path: str = None):
    """Create a smart multi-language search tool."""
    @tool("smart_multilang_search")
    def smart_multilang_search_tool(language: str, error_pattern: str, component: str = "", code_path: str = None) -> str:
        """Search for error patterns across multiple programming languages.
        
        Args:
            language: Programming language to search in (python, javascript, java, etc.)
            error_pattern: Error pattern to search for
            component: Optional component name to narrow search
            code_path: Optional code path (if not provided, will use default or extracted path)
            
        Returns:
            String containing search results
        """
        # Use provided code_path or fall back to default
        effective_code_path = code_path or ""
        
        # Check cache
        cache_key = f"smart_search_{language}_{error_pattern}_{component}_{effective_code_path}"
        if cache_key in _code_analysis_cache:
            return f"[CACHED RESULT] {_code_analysis_cache[cache_key]}"
        
        if not effective_code_path or not os.path.exists(effective_code_path):
            result = "No valid code path provided."
            _code_analysis_cache[cache_key] = result
            return result
        
        try:
            # Determine file extensions for the language
            extensions = {
                'python': ['.py'],
                'javascript': ['.js', '.jsx', '.ts', '.tsx'],
                'java': ['.java'],
                'go': ['.go'],
                'rust': ['.rs'],
                'php': ['.php'],
                'ruby': ['.rb'],
                'csharp': ['.cs'],
                'cpp': ['.cpp', '.cc', '.cxx', '.hpp', '.h'],
                'c': ['.c', '.h'],
                'swift': ['.swift'],
                'kotlin': ['.kt'],
                'scala': ['.scala'],
                'clojure': ['.clj', '.cljs'],
                'haskell': ['.hs'],
                'ocaml': ['.ml', '.mli'],
                'fsharp': ['.fs', '.fsi'],
                'vb': ['.vb'],
                'perl': ['.pl', '.pm'],
                'shell': ['.sh', '.bash'],
                'sql': ['.sql']
            }
            
            search_extensions = extensions.get(language.lower(), [])
            if not search_extensions:
                result = f"Unsupported language: {language}"
                _code_analysis_cache[cache_key] = result
                return result
            
            # Build search terms
            search_terms = [error_pattern]
            if component:
                search_terms.append(component)
            
            # Search for files with matching extensions
            found_files = []
            for root, dirs, files in os.walk(effective_code_path):
                for file in files:
                    if any(file.endswith(ext) for ext in search_extensions):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                # Check if any search term is in the content
                                if any(term.lower() in content.lower() for term in search_terms):
                                    found_files.append(file_path)
                        except Exception:
                            continue
            
            if not found_files:
                result = f"No files found containing '{error_pattern}' in {language} code."
                _code_analysis_cache[cache_key] = result
                return result
            
            # Format results
            results = [f"🔍 SMART SEARCH RESULTS"]
            results.append(f"Language: {language}")
            results.append(f"Error Pattern: {error_pattern}")
            if component:
                results.append(f"Component: {component}")
            results.append(f"Files Found: {len(found_files)}")
            results.append("")
            
            for i, file_path in enumerate(found_files[:10], 1):  # Limit to first 10
                results.append(f"📄 FILE #{i}: {file_path}")
                
                # Extract relevant lines
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                    
                    relevant_lines = []
                    for line_num, line in enumerate(lines, 1):
                        if any(term.lower() in line.lower() for term in search_terms):
                            relevant_lines.append(f"  Line {line_num}: {line.strip()}")
                            if len(relevant_lines) >= 5:  # Limit to 5 relevant lines per file
                                break
                    
                    if relevant_lines:
                        results.extend(relevant_lines)
                    results.append("")
                    
                except Exception:
                    results.append("  [Error reading file]")
                    results.append("")
            
            if len(found_files) > 10:
                results.append(f"... and {len(found_files) - 10} more files")
            
            result = "\n".join(results)
            _code_analysis_cache[cache_key] = result
            return result
            
        except Exception as e:
            result = f"Error in smart search: {str(e)}"
            _code_analysis_cache[cache_key] = result
            return result
    
    return smart_multilang_search_tool

# 2. DIRECTORY LANGUAGE ANALYZER TOOL
def create_directory_language_analyzer_tool(code_path: str = None):
    """Create a directory language analyzer tool."""
    @tool("directory_language_analyzer")
    def directory_language_analyzer_tool(error_category: str, component_hint: str = "", code_path: str = None) -> str:
        """Analyze codebase structure and find relevant files for error categories.
        
        Args:
            error_category: Category of error (database, api, file, auth, etc.)
            component_hint: Optional hint about the component involved
            code_path: Optional code path (if not provided, will use default or extracted path)
            
        Returns:
            String containing directory analysis results
        """
        # Use provided code_path or fall back to default
        effective_code_path = code_path or ""
        
        # Check cache
        cache_key = f"dir_analyzer_{error_category}_{component_hint}_{effective_code_path}"
        if cache_key in _code_analysis_cache:
            return f"[CACHED RESULT] {_code_analysis_cache[cache_key]}"
        
        if not effective_code_path or not os.path.exists(effective_code_path):
            result = "No valid code path provided."
            _code_analysis_cache[cache_key] = result
            return result
        
        try:
            # Define error category patterns
            category_patterns = {
                'database': ['db', 'database', 'sql', 'connection', 'query', 'migration'],
                'api': ['api', 'endpoint', 'route', 'controller', 'handler', 'request'],
                'file': ['file', 'upload', 'download', 'io', 'path', 'directory'],
                'auth': ['auth', 'authentication', 'authorization', 'login', 'token', 'jwt'],
                'network': ['network', 'http', 'https', 'socket', 'connection', 'timeout'],
                'memory': ['memory', 'leak', 'allocation', 'gc', 'garbage'],
                'config': ['config', 'configuration', 'settings', 'env', 'environment'],
                'validation': ['validation', 'validate', 'schema', 'format', 'type'],
                'logging': ['log', 'logging', 'debug', 'trace', 'error'],
                'cache': ['cache', 'redis', 'memcached', 'session', 'storage']
            }
            
            search_terms = category_patterns.get(error_category.lower(), [error_category])
            if component_hint:
                search_terms.append(component_hint)
            
            # Find relevant files
            relevant_files = []
            for root, dirs, files in os.walk(effective_code_path):
                for file in files:
                    if file.endswith(('.py', '.js', '.ts', '.java', '.go', '.rs', '.php', '.rb', '.cs', '.cpp', '.c')):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                # Check if any search term is in the content
                                if any(term.lower() in content.lower() for term in search_terms):
                                    relevant_files.append(file_path)
                        except Exception:
                            continue
            
            if not relevant_files:
                result = f"No relevant files found for error category '{error_category}'."
                _code_analysis_cache[cache_key] = result
                return result
            
            # Group files by directory
            dir_groups = {}
            for file_path in relevant_files:
                dir_name = os.path.dirname(file_path)
                if dir_name not in dir_groups:
                    dir_groups[dir_name] = []
                dir_groups[dir_name].append(file_path)
            
            # Format results
            results = [f"📁 DIRECTORY ANALYSIS FOR '{error_category.upper()}' ERRORS"]
            if component_hint:
                results.append(f"Component Hint: {component_hint}")
            results.append(f"Relevant Files Found: {len(relevant_files)}")
            results.append(f"Directories: {len(dir_groups)}")
            results.append("")
            
            for dir_name, files in sorted(dir_groups.items()):
                results.append(f"📂 DIRECTORY: {dir_name}")
                results.append(f"  Files: {len(files)}")
                
                # Show file names
                for file_path in files[:5]:  # Limit to first 5 files per directory
                    file_name = os.path.basename(file_path)
                    results.append(f"    • {file_name}")
                
                if len(files) > 5:
                    results.append(f"    ... and {len(files) - 5} more files")
                results.append("")
            
            # Add summary
            results.append("📊 SUMMARY:")
            results.append(f"  Total files: {len(relevant_files)}")
            results.append(f"  Directories: {len(dir_groups)}")
            results.append(f"  Search terms used: {', '.join(search_terms)}")
            
            result = "\n".join(results)
            _code_analysis_cache[cache_key] = result
            return result
            
        except Exception as e:
            result = f"Error in directory analysis: {str(e)}"
            _code_analysis_cache[cache_key] = result
            return result
    
    return directory_language_analyzer_tool

# HELPER FUNCTIONS FOR TOOLS

def get_file_language(file_path: str) -> str:
    """Determine programming language from file extension."""
    ext = Path(file_path).suffix.lower()
    
    extension_map = {
        '.go': 'go',
        '.py': 'python',
        '.java': 'java',
        '.js': 'javascript',
        '.ts': 'javascript',
        '.jsx': 'javascript',
        '.tsx': 'javascript',
        '.rs': 'rust',
        '.c': 'c',
        '.cpp': 'c',
        '.h': 'c',
        '.hpp': 'c',
        '.cs': 'csharp',
        '.rb': 'ruby',
        '.php': 'php'
    }
    
    return extension_map.get(ext, 'unknown')

def is_source_file(file_path: str) -> bool:
    """Check if file is a source code file."""
    source_extensions = {'.go', '.py', '.java', '.js', '.ts', '.jsx', '.tsx', 
                        '.rs', '.c', '.cpp', '.h', '.hpp', '.cs', '.rb', '.php'}
    return Path(file_path).suffix.lower() in source_extensions

def extract_relevant_lines(content: str, search_terms: List[str], max_lines: int = 10) -> List[Dict]:
    """Extract lines containing search terms with context."""
    lines = content.split('\n')
    matches = []
    
    for i, line in enumerate(lines):
        for term in search_terms:
            if term.lower() in line.lower():
                matches.append({
                    'line_num': i + 1,
                    'line': line.strip(),
                    'term': term,
                    'context_before': lines[max(0, i-1)].strip() if i > 0 else '',
                    'context_after': lines[min(len(lines)-1, i+1)].strip() if i < len(lines)-1 else ''
                })
                if len(matches) >= max_lines:
                    return matches
                break  # One match per line
    
    return matches

# Legacy functions for backward compatibility
def find_api_handlers(api_route: str, code_path: str = None) -> str:
    """Legacy function - use create_find_api_handlers_tool instead."""
    tool = create_find_api_handlers_tool(code_path)
    return tool(api_route)

def find_dependencies(function_name: str = None, file_path: str = None, code_path: str = None) -> str:
    """Legacy function - use create_find_dependencies_tool instead."""
    tool = create_find_dependencies_tool(code_path)
    return tool(function_name, file_path)

def find_error_handlers(file_path: str = None, function_name: str = None, code_path: str = None) -> str:
    """Legacy function - use create_find_error_handlers_tool instead."""
    tool = create_find_error_handlers_tool(code_path)
    return tool(file_path, function_name)

def smart_code_search(primary_term: str, secondary_term: str = "", tertiary_term: str = "", code_path: str = None) -> str:
    """Legacy function - use create_smart_code_search_tool instead."""
    tool = create_smart_multilang_search_tool(code_path)
    return tool(primary_term, secondary_term, tertiary_term)

def directory_analyzer(error_type: str, component: str, code_path: str = None) -> str:
    """Legacy function - use create_directory_analyzer_tool instead."""
    tool = create_directory_language_analyzer_tool(code_path)
    return tool(error_type, component)      

def create_error_pattern_analyzer_tool(code_path: str = None):
    """Create an error pattern analyzer tool."""
    @tool("analyze_error_patterns")
    def analyze_error_patterns_tool(error_type: str, language: str = "python", code_path: str = None) -> str:
        """Analyze error patterns in code for a specific error type and language.
        
        Args:
            error_type: Type of error to analyze (exception, validation, etc.)
            language: Programming language to focus on
            code_path: Optional code path (if not provided, will use default or extracted path)
            
        Returns:
            String containing error pattern analysis
        """
        # Use provided code_path or fall back to default
        effective_code_path = code_path or ""
        
        # Check cache
        cache_key = f"error_patterns_{error_type}_{language}_{effective_code_path}"
        if cache_key in _code_analysis_cache:
            return f"[CACHED RESULT] {_code_analysis_cache[cache_key]}"
        
        if not effective_code_path or not os.path.exists(effective_code_path):
            result = "No valid code path provided."
            _code_analysis_cache[cache_key] = result
            return result
        
        try:
            # Define language-specific error patterns
            error_patterns = {
                'python': {
                    'exception': ['try:', 'except', 'raise', 'Exception', 'Error'],
                    'validation': ['assert', 'if not', 'isinstance', 'validate'],
                    'null_check': ['if', 'is None', 'is not None', 'None'],
                    'type_error': ['TypeError', 'isinstance', 'type(', 'str(', 'int(']
                },
                'javascript': {
                    'exception': ['try', 'catch', 'throw', 'Error', 'Exception'],
                    'validation': ['if', 'typeof', 'instanceof', 'validate'],
                    'null_check': ['if', 'null', 'undefined', '!==', '==='],
                    'type_error': ['TypeError', 'typeof', 'instanceof']
                },
                'java': {
                    'exception': ['try', 'catch', 'throw', 'Exception', 'Error'],
                    'validation': ['if', 'assert', 'validate', 'check'],
                    'null_check': ['if', 'null', '!= null', '== null'],
                    'type_error': ['ClassCastException', 'instanceof']
                }
            }
            
            patterns = error_patterns.get(language.lower(), {}).get(error_type.lower(), [error_type])
            
            # Find files with error patterns
            found_files = []
            for root, dirs, files in os.walk(effective_code_path):
                for file in files:
                    if file.endswith(('.py', '.js', '.ts', '.java', '.go', '.rs', '.php', '.rb', '.cs', '.cpp', '.c')):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                # Check if any pattern is in the content
                                if any(pattern.lower() in content.lower() for pattern in patterns):
                                    found_files.append(file_path)
                        except Exception:
                            continue
            
            if not found_files:
                result = f"No error patterns found for '{error_type}' in {language} code."
                _code_analysis_cache[cache_key] = result
                return result
            
            # Format results
            results = [f"🔍 ERROR PATTERN ANALYSIS"]
            results.append(f"Error Type: {error_type}")
            results.append(f"Language: {language}")
            results.append(f"Files Found: {len(found_files)}")
            results.append("")
            
            for i, file_path in enumerate(found_files[:10], 1):  # Limit to first 10
                results.append(f"📄 FILE #{i}: {file_path}")
                
                # Extract relevant lines
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                    
                    relevant_lines = []
                    for line_num, line in enumerate(lines, 1):
                        if any(pattern.lower() in line.lower() for pattern in patterns):
                            relevant_lines.append(f"  Line {line_num}: {line.strip()}")
                            if len(relevant_lines) >= 3:  # Limit to 3 relevant lines per file
                                break
                    
                    if relevant_lines:
                        results.extend(relevant_lines)
                    results.append("")
                    
                except Exception:
                    results.append("  [Error reading file]")
                    results.append("")
            
            if len(found_files) > 10:
                results.append(f"... and {len(found_files) - 10} more files")
            
            # Add summary
            results.append("📊 SUMMARY:")
            results.append(f"  Total files: {len(found_files)}")
            results.append(f"  Patterns searched: {', '.join(patterns)}")
            
            result = "\n".join(results)
            _code_analysis_cache[cache_key] = result
            return result
            
        except Exception as e:
            result = f"Error in pattern analysis: {str(e)}"
            _code_analysis_cache[cache_key] = result
            return result
    
    return analyze_error_patterns_tool 