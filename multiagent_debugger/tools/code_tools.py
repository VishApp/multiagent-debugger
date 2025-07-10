import os
import ast
import re
from typing import Dict, Any, List, Optional
from pathlib import Path

from crewai.tools import tool

def create_find_api_handlers_tool(code_path: str = None):
    """Create a find API handlers tool with the specified code path."""
    @tool("find_api_handlers")
    def find_api_handlers_tool(api_route: str) -> str:
        """Find API handler functions in the codebase for a specific API route.
        Useful for locating where an API endpoint is implemented.
        
        Args:
            api_route: The API route to find handlers for
            
        Returns:
            String containing the found API handlers
        """
        code_path = tool_code_path
        
        if not code_path or not os.path.exists(code_path):
            return "No valid code path provided."
        
        # Clean API route for searching
        clean_route = api_route.strip('/')
        
        results = []
        
        # Find Python files in the codebase
        python_files = _find_python_files(code_path)
        
        # Search for files that might contain the API route handler
        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # Check if file contains the API route
                    route_pattern = re.compile(r'[\'"]/?{}[\'"]'.format(re.escape(clean_route)))
                    if route_pattern.search(content):
                        # Parse the file with AST
                        try:
                            tree = ast.parse(content)
                            
                            # Find API handler functions
                            api_handlers = _find_api_handlers_in_ast(tree, clean_route, content)
                            if api_handlers:
                                results.append(f"API handlers found in {file_path}:")
                                for handler in api_handlers:
                                    results.append(f"- {handler['name']} (line {handler['line_number']}):")
                                    results.append(f"{handler['source']}\n")
                        except SyntaxError:
                            # Skip files with syntax errors
                            results.append(f"Could not parse {file_path} due to syntax errors.")
            except Exception as e:
                results.append(f"Error analyzing file {file_path}: {str(e)}")
        
        if not results:
            return f"No API handlers found for route '{api_route}'."
        
        return "\n".join(results)
    
    # Capture the code_path in the closure
    tool_code_path = code_path or ""
    return find_api_handlers_tool

def create_find_dependencies_tool(code_path: str = None):
    """Create a find dependencies tool with the specified code path."""
    @tool("find_dependencies")
    def find_dependencies_tool(function_name: str = None, file_path: str = None) -> str:
        """Find dependencies of a specific function or module in the codebase.
        Useful for understanding what other components an API depends on.
        
        Args:
            function_name: Optional name of the function to find dependencies for
            file_path: Optional path to the file to find dependencies for
            
        Returns:
            String containing the found dependencies
        """
        code_path = tool_code_path
        
        if not code_path or not os.path.exists(code_path):
            return "No valid code path provided."
        
        if not function_name and not file_path:
            return "Please provide either a function name or a file path."
        
        # Implementation for finding dependencies
        return "Dependencies found: ..."
    
    # Capture the code_path in the closure
    tool_code_path = code_path or ""
    return find_dependencies_tool

def create_find_error_handlers_tool(code_path: str = None):
    """Create a find error handlers tool with the specified code path."""
    @tool("find_error_handlers")
    def find_error_handlers_tool(file_path: str = None, function_name: str = None) -> str:
        """Find error handling code in the codebase.
        Useful for understanding how errors are handled for a specific API.
        
        Args:
            file_path: Optional path to the file to search in
            function_name: Optional name of the function to search in
            
        Returns:
            String containing the found error handlers
        """
        code_path = tool_code_path
        
        if not code_path or not os.path.exists(code_path):
            return "No valid code path provided."
        
        # Implementation for finding error handlers
        return "Error handlers found: ..."
    
    # Capture the code_path in the closure
    tool_code_path = code_path or ""
    return find_error_handlers_tool

def _find_python_files(path: str) -> List[Path]:
    """Find all Python files in the given path."""
    path_obj = Path(path)
    if path_obj.is_file() and path_obj.suffix == '.py':
        return [path_obj]
    
    python_files = []
    for root, _, files in os.walk(path):
        for file in files:
            if file.endswith('.py'):
                python_files.append(Path(root) / file)
    
    return python_files

def _find_api_handlers_in_ast(tree: ast.AST, route: str, content: str) -> List[Dict[str, Any]]:
    """Find API handler functions in the AST."""
    handlers = []
    
    # This is a simplified implementation that looks for common patterns
    # in web frameworks like Flask, FastAPI, Django, etc.
    for node in ast.walk(tree):
        # Look for route decorators
        if isinstance(node, ast.FunctionDef):
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call):
                    if hasattr(decorator.func, 'attr') and decorator.func.attr in ['route', 'get', 'post', 'put', 'delete']:
                        # Check if route matches
                        for arg in decorator.args:
                            if isinstance(arg, ast.Str) and route in arg.s:
                                # Extract function source
                                start_line = node.lineno
                                end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line
                                source_lines = content.splitlines()[start_line-1:end_line]
                                source = '\n'.join(source_lines)
                                
                                handlers.append({
                                    "name": node.name,
                                    "type": "function",
                                    "source": source,
                                    "line_number": start_line
                                })
        
        # Look for route registrations (e.g., app.add_url_rule)
        if isinstance(node, ast.Call):
            if hasattr(node.func, 'attr') and node.func.attr in ['add_url_rule', 'register']:
                for arg in node.args:
                    if isinstance(arg, ast.Str) and route in arg.s:
                        handlers.append({
                            "name": "route_registration",
                            "type": "registration",
                            "source": ast.unparse(node) if hasattr(ast, 'unparse') else str(node),
                            "line_number": node.lineno
                        })
    
    return handlers

# Legacy functions for backward compatibility
def find_api_handlers(api_route: str, code_path: str = None) -> str:
    """Legacy function - use create_find_api_handlers_tool instead."""
    tool = create_find_api_handlers_tool(code_path)
    return tool(api_route, code_path)

def find_dependencies(function_name: str = None, file_path: str = None, code_path: str = None) -> str:
    """Legacy function - use create_find_dependencies_tool instead."""
    tool = create_find_dependencies_tool(code_path)
    return tool(function_name, file_path, code_path)

def find_error_handlers(file_path: str = None, function_name: str = None, code_path: str = None) -> str:
    """Legacy function - use create_find_error_handlers_tool instead."""
    tool = create_find_error_handlers_tool(code_path)
    return tool(file_path, function_name, code_path) 