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
    def find_api_handlers_tool(api_route: str) -> str:
        """Find API handler functions in the codebase for a specific API route.
        
        Args:
            api_route: The API route to find handlers for
            
        Returns:
            String containing detailed information about found API handlers
        """
        # Check cache
        cache_key = f"api_handlers_{api_route}_{code_path}"
        if cache_key in _code_analysis_cache:
            return f"[CACHED RESULT] {_code_analysis_cache[cache_key]}"
        
        print(f"[DEBUG] Finding API handlers for route: {api_route}")
        
        if not code_path:
            result = "❌ ERROR: No code path configured. Cannot perform code analysis."
            _code_analysis_cache[cache_key] = result
            return result
        
        if not os.path.exists(code_path):
            result = f"❌ ERROR: Code path does not exist: {code_path}"
            _code_analysis_cache[cache_key] = result
            return result
        
        try:
            analyzer = CodeAnalyzer(code_path)
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
    def find_dependencies_tool(function_name: str = None, file_path: str = None) -> str:
        """Find dependencies of a specific function or module.
        
        Args:
            function_name: Optional name of the function to analyze
            file_path: Optional path to the file to analyze
            
        Returns:
            String containing detailed dependency information
        """
        # Check cache
        cache_key = f"dependencies_{function_name}_{file_path}_{code_path}"
        if cache_key in _code_analysis_cache:
            return f"[CACHED RESULT] {_code_analysis_cache[cache_key]}"
        
        print(f"[DEBUG] Finding dependencies for function: {function_name}, file: {file_path}")
        
        if not code_path or not os.path.exists(code_path):
            result = "No valid code path provided."
            _code_analysis_cache[cache_key] = result
            return result
        
        if not function_name and not file_path:
            result = "Please provide either a function name or a file path."
            _code_analysis_cache[cache_key] = result
            return result
        
        try:
            analyzer = CodeAnalyzer(code_path)
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
    def find_error_handlers_tool(file_path: str, function_name: str = "") -> str:
        """Find error handling code in the codebase.
        
        Args:
            file_path: Path to the file to search in (required)
            function_name: Name of the function to search in (optional, defaults to empty string)
            
        Returns:
            String containing detailed error handler information
        """
        # Check cache
        cache_key = f"error_handlers_{file_path}_{function_name}_{code_path}"
        if cache_key in _code_analysis_cache:
            return f"[CACHED RESULT] {_code_analysis_cache[cache_key]}"
        
        print(f"[DEBUG] Finding error handlers in file: {file_path}, function: {function_name}")
        
        if not code_path or not os.path.exists(code_path):
            result = "No valid code path provided."
            _code_analysis_cache[cache_key] = result
            return result
        
        # Convert empty strings to None for the analyzer
        file_path = file_path if file_path else None
        function_name = function_name if function_name else None
        
        try:
            analyzer = CodeAnalyzer(code_path)
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
    """
    Creates a language-aware code search tool that adapts patterns based on programming language.
    This tool understands different languages and searches for relevant patterns automatically.
    """
    @tool("smart_multilang_search")
    def smart_multilang_search_tool(language: str, error_pattern: str, component: str = "") -> str:
        """
        Search code with language-specific patterns and intelligence.
        
        Args:
            language: Programming language (go, python, java, javascript, rust, c, csharp)
            error_pattern: Error pattern to search for (nil_pointer, attribute_error, null_exception, etc.)
            component: Optional component/module name (user, auth, api, database, etc.)
            
        Returns:
            String containing found code patterns with file locations and relevant code snippets
        """
        
        try:
            print(f"[DEBUG] Smart multilang search: {language} | {error_pattern} | {component}")
            
            # LANGUAGE-SPECIFIC CONFIGURATIONS
            language_config = {
                'go': {
                    'extensions': ['.go'],
                    'patterns': {
                        'nil_pointer': ['nil', '*', 'pointer', 'dereference', 'struct', 'interface{}'],
                        'panic': ['panic', 'recover', 'runtime.Error', 'defer'],
                        'goroutine': ['goroutine', 'channel', 'go func', 'sync.', 'mutex'],
                        'interface': ['interface{}', 'type assertion', '.(', 'switch.*type'],
                        'slice': ['make([]', 'append(', '[:]', 'len(', 'cap('],
                        'error': ['error', 'fmt.Errorf', 'errors.New', 'if err != nil']
                    },
                    'keywords': ['func', 'type', 'struct', 'interface', 'package', 'import']
                },
                'python': {
                    'extensions': ['.py'],
                    'patterns': {
                        'none': ['None', 'is None', 'is not None', 'AttributeError'],
                        'attribute_error': ['AttributeError', 'hasattr', 'getattr', 'setattr'],
                        'import': ['import', 'from', 'ImportError', 'ModuleNotFoundError'],
                        'type_error': ['TypeError', 'isinstance', 'type(', '__class__'],
                        'key_error': ['KeyError', '.get(', '.keys()', '.items()'],
                        'async': ['async', 'await', 'asyncio', 'coroutine']
                    },
                    'keywords': ['def', 'class', 'import', 'from', 'try', 'except']
                },
                'java': {
                    'extensions': ['.java'],
                    'patterns': {
                        'null_pointer': ['null', 'NullPointerException', 'Objects.isNull', 'Optional'],
                        'exception': ['Exception', 'try', 'catch', 'finally', 'throw'],
                        'class_not_found': ['ClassNotFoundException', 'Class.forName', 'classLoader'],
                        'array_bounds': ['ArrayIndexOutOfBoundsException', '.length', 'Arrays.'],
                        'concurrent': ['ConcurrentModificationException', 'synchronized', 'volatile']
                    },
                    'keywords': ['public', 'private', 'class', 'interface', 'extends', 'implements']
                },
                'javascript': {
                    'extensions': ['.js', '.ts', '.jsx', '.tsx'],
                    'patterns': {
                        'undefined': ['undefined', 'null', 'TypeError', '?.', '??'],
                        'reference_error': ['ReferenceError', 'is not defined', 'let', 'const', 'var'],
                        'promise': ['Promise', 'async', 'await', '.then', '.catch', '.finally'],
                        'callback': ['callback', 'function(', '=>', 'addEventListener'],
                        'dom': ['document', 'element', 'getElementById', 'querySelector']
                    },
                    'keywords': ['function', 'const', 'let', 'var', 'class', 'import', 'export']
                },
                'rust': {
                    'extensions': ['.rs'],
                    'patterns': {
                        'panic': ['panic!', 'unwrap()', 'expect(', 'Result', 'Option'],
                        'option': ['Option', 'Some(', 'None', 'unwrap_or', 'map('],
                        'result': ['Result', 'Ok(', 'Err(', 'match', '?'],
                        'borrow': ['borrow', '&mut', '&', 'RefCell', 'Rc']
                    },
                    'keywords': ['fn', 'struct', 'enum', 'impl', 'trait', 'use']
                },
                'c': {
                    'extensions': ['.c', '.cpp', '.h', '.hpp'],
                    'patterns': {
                        'segfault': ['NULL', 'segmentation fault', 'malloc', 'free', 'pointer'],
                        'memory': ['malloc', 'calloc', 'realloc', 'free', 'memcpy'],
                        'undefined': ['undefined reference', 'undefined symbol', 'extern'],
                        'buffer': ['buffer overflow', 'strcpy', 'strcat', 'gets']
                    },
                    'keywords': ['#include', 'int', 'char', 'void', 'struct', 'typedef']
                }
            }
            
            # Get language configuration
            lang_config = language_config.get(language.lower(), language_config.get('javascript', {}))  # Default to JavaScript patterns
            extensions = lang_config['extensions']
            patterns = lang_config['patterns']
            keywords = lang_config['keywords']
            
            # Get search terms for the error pattern
            search_terms = patterns.get(error_pattern, [error_pattern])
            if component:
                search_terms.append(component)
            
            print(f"[DEBUG] Using extensions: {extensions}")
            print(f"[DEBUG] Search terms: {search_terms}")
            
            # SMART FILE DISCOVERY
            found_files = []
            file_count = 0
            
            for root, dirs, files in os.walk(code_path):
                # Skip common non-source directories
                dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', 'node_modules', 'target', 'build', 'dist']]
                
                for file in files:
                    if any(file.endswith(ext) for ext in extensions):
                        file_path = os.path.join(root, file)
                        file_count += 1
                        
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                
                                # INTELLIGENT PATTERN MATCHING
                                matches = []
                                lines = content.split('\n')
                                
                                for i, line in enumerate(lines):
                                    line_lower = line.lower()
                                    
                                    # Check if any search terms are in the line
                                    for term in search_terms:
                                        if term.lower() in line_lower:
                                            # Add context around the match
                                            start_line = max(0, i - 1)
                                            end_line = min(len(lines), i + 2)
                                            context_lines = lines[start_line:end_line]
                                            
                                            matches.append({
                                                'line_num': i + 1,
                                                'line': line.strip(),
                                                'context': context_lines,
                                                'term': term
                                            })
                                            break  # One match per line is enough
                                
                                # If we found matches, include this file
                                if matches:
                                    found_files.append({
                                        'file': file_path,
                                        'matches': matches[:5],  # Top 5 matches per file
                                        'relevance': len(matches)
                                    })
                                    
                        except Exception as e:
                            print(f"[DEBUG] Error reading {file_path}: {e}")
                            continue
                
                # Limit total files processed for performance
                if len(found_files) >= 10:
                    break
            
            # GENERATE RESULTS
            if found_files:
                # Sort by relevance (number of matches)
                found_files.sort(key=lambda x: x['relevance'], reverse=True)
                
                result = f"🔍 SMART {language.upper()} CODE SEARCH RESULTS\n\n"
                result += f"Pattern: '{error_pattern}' | Component: '{component}'\n"
                result += f"Searched: {file_count} {language} files\n"
                result += f"Found: {len(found_files)} relevant files\n\n"
                
                for i, file_info in enumerate(found_files[:5], 1):  # Top 5 files
                    file_path = file_info['file']
                    matches = file_info['matches']
                    
                    result += f"📁 {i}. {file_path} ({file_info['relevance']} matches)\n"
                    
                    for match in matches[:3]:  # Top 3 matches per file
                        result += f"   Line {match['line_num']}: {match['line']}\n"
                        if len(match['context']) > 1:
                            result += f"   Context: {match['context'][0].strip()}\n"
                    result += "\n"
                
                # Add analysis summary
                all_matches = [match for file_info in found_files for match in file_info['matches']]
                common_terms = Counter([match['term'] for match in all_matches])
                
                result += f"📊 PATTERN ANALYSIS:\n"
                result += f"Most common patterns: {dict(common_terms.most_common(3))}\n"
                result += f"Files to focus on: {[f['file'] for f in found_files[:3]]}\n"
                
                return result
            else:
                return f"No specific {language} code patterns found for '{error_pattern}'. Recommend checking:\n" \
                       f"- Main {language} files ({', '.join(extensions)})\n" \
                       f"- Configuration files\n" \
                       f"- {component} related modules if specified\n" \
                       f"Proceeding with {language}-specific pattern analysis."
                
        except Exception as e:
            return f"Smart {language} search unavailable: {str(e)}. Using {language}-specific pattern analysis for '{error_pattern}' issues."
    
    return smart_multilang_search_tool

# 2. DIRECTORY LANGUAGE ANALYZER TOOL
def create_directory_language_analyzer_tool(code_path: str = None):
    """
    Creates a directory analyzer that detects languages and finds relevant files for any error category.
    This tool provides a broad overview of the codebase and identifies focus areas.
    """
    @tool("directory_language_analyzer")
    def directory_language_analyzer_tool(error_category: str, component_hint: str = "") -> str:
        """
        Analyze directory structure to detect languages and find relevant files.
        
        Args:
            error_category: Category of error (runtime, compile, auth, database, api, file, network, etc.)
            component_hint: Hint about component (user, auth, api, upload, database, etc.)
            
        Returns:
            String containing language detection results and relevant file recommendations
        """
        
        try:
            print(f"[DEBUG] Directory analysis: {error_category} | {component_hint}")
            
            # COMPREHENSIVE LANGUAGE DETECTION
            language_patterns = {
                'go': {
                    'extensions': ['.go'],
                    'markers': ['go.mod', 'go.sum', 'main.go'],
                    'keywords': ['package main', 'func main()', 'import (']
                },
                'python': {
                    'extensions': ['.py'],
                    'markers': ['requirements.txt', 'setup.py', 'pyproject.toml', '__init__.py'],
                    'keywords': ['def ', 'import ', 'from ', 'class ']
                },
                'java': {
                    'extensions': ['.java'],
                    'markers': ['pom.xml', 'build.gradle', 'src/main/java'],
                    'keywords': ['public class', 'public static void main', 'package ']
                },
                'javascript': {
                    'extensions': ['.js', '.ts', '.jsx', '.tsx'],
                    'markers': ['package.json', 'node_modules', 'tsconfig.json'],
                    'keywords': ['function', 'const ', 'let ', 'import ']
                },
                'rust': {
                    'extensions': ['.rs'],
                    'markers': ['Cargo.toml', 'src/main.rs', 'src/lib.rs'],
                    'keywords': ['fn ', 'struct ', 'impl ', 'use ']
                },
                'c_cpp': {
                    'extensions': ['.c', '.cpp', '.h', '.hpp'],
                    'markers': ['Makefile', 'CMakeLists.txt', 'configure'],
                    'keywords': ['#include', 'int main(', 'void ', 'struct ']
                }
            }
            
            # ERROR CATEGORY TO FILE PATTERNS MAPPING
            error_file_patterns = {
                'runtime': ['main', 'app', 'server', 'handler', 'service'],
                'auth': ['auth', 'login', 'user', 'session', 'token', 'security'],
                'database': ['db', 'database', 'model', 'repository', 'dao', 'orm'],
                'api': ['api', 'handler', 'controller', 'route', 'endpoint'],
                'file': ['file', 'upload', 'download', 'io', 'storage'],
                'network': ['client', 'http', 'request', 'connection', 'network'],
                'config': ['config', 'settings', 'env', 'properties'],
                'compile': ['build', 'compile', 'make', 'gradle', 'maven']
            }
            
            # SCAN DIRECTORY STRUCTURE
            detected_languages = defaultdict(lambda: {'files': [], 'markers': [], 'confidence': 0})
            all_files = []
            relevant_files = []
            
            for root, dirs, files in os.walk(code_path):
                # Skip common non-source directories
                dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', 'node_modules', 'target', 'build', 'dist', '.vscode', '.idea']]
                
                for file in files:
                    file_path = os.path.join(root, file)
                    all_files.append(file_path)
                    
                    # LANGUAGE DETECTION
                    for lang, config in language_patterns.items():
                        # Check file extensions
                        if any(file.endswith(ext) for ext in config['extensions']):
                            detected_languages[lang]['files'].append(file_path)
                            detected_languages[lang]['confidence'] += 1
                        
                        # Check for language markers
                        if file in config['markers']:
                            detected_languages[lang]['markers'].append(file)
                            detected_languages[lang]['confidence'] += 5  # Markers are stronger indicators
                    
                    # RELEVANCE DETECTION
                    file_lower = file.lower()
                    path_lower = file_path.lower()
                    
                    # Check for error category patterns
                    category_patterns = error_file_patterns.get(error_category, [error_category])
                    if any(pattern in file_lower or pattern in path_lower for pattern in category_patterns):
                        relevant_files.append(file_path)
                    
                    # Check for component hint
                    if component_hint and (component_hint.lower() in file_lower or component_hint.lower() in path_lower):
                        relevant_files.append(file_path)
            
            # DETERMINE PRIMARY LANGUAGE
            if detected_languages:
                primary_lang = max(detected_languages.keys(), key=lambda k: detected_languages[k]['confidence'])
            else:
                primary_lang = 'unknown'
            
            # GENERATE ANALYSIS RESULTS
            result = f"🌐 DIRECTORY LANGUAGE ANALYSIS\n\n"
            
            # Language Detection Results
            result += f"📊 DETECTED LANGUAGES:\n"
            sorted_langs = sorted(detected_languages.items(), key=lambda x: x[1]['confidence'], reverse=True)
            
            for lang, info in sorted_langs[:5]:  # Top 5 languages
                file_count = len(info['files'])
                markers = info['markers']
                confidence = info['confidence']
                
                result += f"  {lang.upper()}: {file_count} files (confidence: {confidence})\n"
                if markers:
                    result += f"    Markers: {', '.join(markers)}\n"
            
            result += f"\n🎯 PRIMARY LANGUAGE: {primary_lang.upper()}\n\n"
            
            # Relevant Files for Error Category
            if relevant_files:
                # Remove duplicates and limit results
                unique_relevant = list(set(relevant_files))[:15]
                
                result += f"📁 RELEVANT FILES FOR '{error_category.upper()}' ERRORS:\n"
                
                # Group by language if possible
                lang_files = defaultdict(list)
                for file_path in unique_relevant:
                    file_lang = 'other'
                    for lang, config in language_patterns.items():
                        if any(file_path.endswith(ext) for ext in config['extensions']):
                            file_lang = lang
                            break
                    lang_files[file_lang].append(file_path)
                
                for lang, files in lang_files.items():
                    if files:
                        result += f"\n  {lang.upper()} files:\n"
                        for file_path in files[:5]:  # Top 5 per language
                            result += f"    - {file_path}\n"
            else:
                result += f"📁 NO SPECIFIC FILES FOUND for '{error_category}'\n"
                result += f"   Recommend checking main {primary_lang} files and configuration\n"
            
            # Recommendations
            result += f"\n💡 ANALYSIS RECOMMENDATIONS:\n"
            
            if primary_lang != 'unknown':
                config = language_patterns[primary_lang]
                result += f"  1. Focus on {primary_lang.upper()} files with extensions: {', '.join(config['extensions'])}\n"
                result += f"  2. Check {primary_lang} project markers: {', '.join(config['markers'])}\n"
            
            if component_hint:
                result += f"  3. Search for '{component_hint}' in file names and directory structure\n"
            
            result += f"  4. For '{error_category}' errors, examine: {', '.join(error_file_patterns.get(error_category, [error_category]))}\n"
            
            # Statistics
            total_files = len(all_files)
            result += f"\n📈 STATISTICS:\n"
            result += f"  Total files scanned: {total_files}\n"
            result += f"  Languages detected: {len(detected_languages)}\n"
            result += f"  Relevant files found: {len(set(relevant_files))}\n"
            
            return result
            
        except Exception as e:
            return f"Directory analysis unavailable: {str(e)}. Recommend manual inspection of codebase structure for {error_category} error patterns."
    
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
    """Create a tool for analyzing error patterns without requiring a specific file path."""
    @tool("analyze_error_patterns")
    def analyze_error_patterns_tool(error_type: str, language: str = "python") -> str:
        """Analyze error patterns in the codebase for a specific error type and language.
        
        Args:
            error_type: Type of error to search for (e.g., "authentication", "database", "file_access")
            language: Programming language to focus on (defaults to python)
            
        Returns:
            String containing error pattern analysis
        """
        # Check cache
        cache_key = f"error_patterns_{error_type}_{language}_{code_path}"
        if cache_key in _code_analysis_cache:
            return f"[CACHED RESULT] {_code_analysis_cache[cache_key]}"
        
        print(f"[DEBUG] Analyzing error patterns for: {error_type} in {language}")
        
        if not code_path or not os.path.exists(code_path):
            result = "No valid code path provided."
            _code_analysis_cache[cache_key] = result
            return result
        
        try:
            analyzer = CodeAnalyzer(code_path)
            
            # Get all source files for the specified language
            language_extensions = {
                'python': ['.py'],
                'javascript': ['.js', '.ts', '.jsx', '.tsx'],
                'java': ['.java'],
                'go': ['.go'],
                'rust': ['.rs'],
                'c': ['.c', '.cpp', '.h', '.hpp']
            }
            
            extensions = language_extensions.get(language.lower(), ['.py'])
            source_files = []
            
            for root, dirs, files in os.walk(code_path):
                # Skip common non-source directories
                dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', 'node_modules', 'target', 'build', 'dist']]
                
                for file in files:
                    if any(file.endswith(ext) for ext in extensions):
                        source_files.append(os.path.join(root, file))
            
            if not source_files:
                result = f"No {language} source files found in the codebase."
                _code_analysis_cache[cache_key] = result
                return result
            
            # Analyze error patterns
            error_patterns = []
            for file_path in source_files[:10]:  # Limit to first 10 files for performance
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Language-specific error pattern matching
                    patterns = []
                    if language.lower() == 'python':
                        patterns = [
                            r'try\s*:', r'except\s+\w+', r'raise\s+\w+', r'assert\s+',
                            r'if\s+.*error', r'if\s+.*exception', r'if\s+.*fail',
                            r'logging\.error', r'logger\.error'
                        ]
                    elif language.lower() in ['javascript', 'typescript']:
                        patterns = [
                            r'try\s*{', r'catch\s*\(', r'throw\s+', r'if\s*\(.*error',
                            r'\.catch\(', r'Promise\.reject', r'console\.error'
                        ]
                    elif language.lower() == 'java':
                        patterns = [
                            r'try\s*{', r'catch\s*\(', r'throw\s+', r'throws\s+\w+',
                            r'if\s*\(.*error', r'Exception', r'RuntimeException'
                        ]
                    elif language.lower() == 'go':
                        patterns = [
                            r'if\s+err\s*!=\s*nil', r'panic\(', r'recover\(\)',
                            r'return\s+.*err', r'fmt\.Errorf'
                        ]
                    elif language.lower() == 'rust':
                        patterns = [
                            r'Result<', r'Option<', r'match\s+', r'\.unwrap\(',
                            r'\.expect\(', r'panic!', r'if\s+.*\.is_err\('
                        ]
                    
                    # Search for error patterns
                    for pattern in patterns:
                        matches = re.finditer(pattern, content, re.IGNORECASE)
                        for match in matches:
                            line_num = content[:match.start()].count('\n') + 1
                            line_content = content.split('\n')[line_num - 1].strip()
                            
                            # Check if this matches the error type we're looking for
                            if error_type.lower() in line_content.lower():
                                error_patterns.append({
                                    'file': file_path,
                                    'line': line_num,
                                    'pattern': pattern,
                                    'content': line_content
                                })
                
                except Exception as e:
                    continue  # Skip files that can't be read
            
            if not error_patterns:
                result = f"No {error_type} error patterns found in {language} files."
                _code_analysis_cache[cache_key] = result
                return result
            
            # Format results
            results = [f"🔍 ERROR PATTERN ANALYSIS FOR '{error_type.upper()}' IN {language.upper()}\n"]
            results.append(f"Found {len(error_patterns)} relevant error patterns:\n")
            
            for i, pattern in enumerate(error_patterns[:5], 1):  # Limit to first 5
                results.append(f"📍 PATTERN #{i}:")
                results.append(f"  File: {pattern['file']}:{pattern['line']}")
                results.append(f"  Pattern: {pattern['pattern']}")
                results.append(f"  Content: {pattern['content']}")
                results.append("")
            
            if len(error_patterns) > 5:
                results.append(f"... and {len(error_patterns) - 5} more patterns found")
            
            result = "\n".join(results)
            _code_analysis_cache[cache_key] = result
            return result
            
        except Exception as e:
            result = f"Error analyzing error patterns: {str(e)}"
            _code_analysis_cache[cache_key] = result
            return result
    
    return analyze_error_patterns_tool 