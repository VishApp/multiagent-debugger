import os
import ast
import re
from typing import Dict, Any, List, Optional, Set
from pathlib import Path

from crewai import Agent
from crewai.tools import tool
from crewai.tools import BaseTool
from multiagent_debugger.utils import get_verbose_flag, create_crewai_llm, get_agent_llm_config

class CodeAgent:
    """Agent that analyzes code to find relevant information about API failures."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the CodeAgent.
        
        Args:
            config: Configuration dictionary with model settings
        """
        self.config = config
        
        # Handle both dict and DebuggerConfig objects
        if hasattr(config, 'llm'):
            self.llm_config = config.llm
        else:
            self.llm_config = config.get("llm", {})
        
    def create_agent(self, tools: List[BaseTool] = None) -> Agent:
        """Create and return the CrewAI agent.
        
        Args:
            tools: List of tools available to the agent
            
        Returns:
            Agent: The configured CrewAI agent
        """
        # Get LLM configuration parameters
        provider, model, temperature, api_key, api_base, additional_params = get_agent_llm_config(self.llm_config)
        verbose = get_verbose_flag(self.config)
        
        # Create LLM
        llm = create_crewai_llm(provider, model, temperature, api_key, api_base, additional_params)
        
        try:
            agent = Agent(
                role="Code Analysis Expert",
                goal="Analyze specific code files and lines to identify root causes of errors",
                backstory="You are a code analysis expert who examines source code to find bugs, identify issues, and suggest fixes.",
                verbose=verbose,
                allow_delegation=False,
                tools=tools or [],
                llm=llm,
                max_iter=1,
                memory=False,
                instructions="""
                Analyze code files to identify root causes and suggest fixes:
                
                1. Examine specific file and line number from error logs
                2. Identify code issues (null access, type errors, logic errors)
                3. Analyze function context and error handling
                4. Provide actionable fixes with line references
                
                OUTPUT FORMAT (JSON):
                {
                  "targeted_analysis": {
                    "target_file": "/path/to/analyzed/file.ext",
                    "target_line": 123,
                    "target_function": "function_name",
                    "file_exists": true/false,
                    "file_accessible": true/false,
                    "analysis_quality": "[high|medium|low]"
                  },
                  "line_analysis": {
                    "error_line_code": "[actual code at the error line]",
                    "error_line_context": "[context around the error line]",
                    "potential_issues": [
                      {
                        "issue_type": "[null_access|type_error|logic_error|etc]",
                        "description": "[specific issue description]",
                        "line_number": 123,
                        "confidence": "[high|medium|low]"
                      }
                    ]
                  },
                  "function_analysis": {
                    "function_name": "function_name",
                    "function_signature": "def function_name(param1, param2):",
                    "parameters": ["param1", "param2"],
                    "error_handling": "[present|missing|inadequate]",
                    "validation_logic": "[present|missing|inadequate]"
                  },
                  "code_issues": {
                    "immediate_fixes": [
                      {
                        "action": "[specific fix action]",
                        "line_number": 123,
                        "description": "[what to change]",
                        "impact": "[what this fix will solve]"
                      }
                    ],
                    "potential_issues": ["[list of potential issues found]"],
                    "missing_validation": ["[validation that should be added]"]
                  },
                  "analysis_summary": {
                    "root_cause": "[definitive cause of the error]",
                    "confidence_level": "[high|medium|low]",
                    "fix_complexity": "[simple|moderate|complex]"
                  }
                }
                
                RULES:
                - Focus on the specific file and line from log extraction
                - Only analyze files that actually exist and are accessible
                - Provide actionable fixes with exact line references
                - Be specific about code issues and their locations
                - If file doesn't exist, report file_exists: false
                """
            )
            return agent
        except Exception as e:
            import traceback
            print(f"ERROR: Failed to create CrewAI Agent: {e}")
            print(traceback.format_exc())
            raise
    
    def analyze_code(self, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze code for relevant information about API failures.
        
        Args:
            entities: Dictionary of entities extracted from the user's question
            
        Returns:
            Dict containing relevant code analysis results
        """
        results = {
            "api_handlers": [],
            "dependencies": [],
            "error_handlers": [],
            "summary": ""
        }
        
        # Find Python files in the code path
        python_files = self._find_python_files(self.code_path)
        
        # Extract API route from entities
        api_route = entities.get("api_route")
        
        # Analyze each Python file
        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Parse the Python file
                tree = ast.parse(content)
                
                # Find API handlers if route is provided
                if api_route:
                    handlers = self._find_api_handlers(tree, api_route, content)
                    results["api_handlers"].extend(handlers)
                
                # Find error handlers
                error_handlers = self._find_error_handlers(tree, content)
                results["error_handlers"].extend(error_handlers)
                
                # Extract dependencies
                dependencies = self._extract_dependencies(tree)
                results["dependencies"].extend(dependencies)
                
            except Exception as e:
                print(f"Error analyzing file {file_path}: {str(e)}")
        
        # Generate summary
        results["summary"] = f"Found {len(results['api_handlers'])} API handlers, " \
                            f"{len(results['error_handlers'])} error handlers, and " \
                            f"{len(results['dependencies'])} dependencies."
        
        return results
    
    def _find_python_files(self, path: str) -> List[Path]:
        """Find all Python files in the given path."""
        python_files = []
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith('.py'):
                    python_files.append(Path(root) / file)
        return python_files
    
    def _find_api_handlers(self, tree: ast.AST, route: str, content: str) -> List[Dict[str, Any]]:
        """Find API handlers that match the given route."""
        handlers = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check if function name or docstring contains route information
                function_name = node.name
                docstring = ast.get_docstring(node) or ""
                
                # Simple pattern matching for route
                if route in function_name or route in docstring:
                    handlers.append({
                        "name": function_name,
                        "line_number": node.lineno,
                        "file": content.split('\n')[node.lineno - 1].strip()
                    })
        
        return handlers
    
    def _find_related_functions(self, tree: ast.AST, handlers: List[Dict[str, Any]], content: str) -> List[Dict[str, Any]]:
        """Find functions related to the API handlers."""
        related_functions = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                function_name = node.name
                
                # Check if this function is called by any of the handlers
                for handler in handlers:
                    if function_name in content and handler["name"] in content:
                        # Simple heuristic: if both names appear in the same context
                        related_functions.append({
                            "name": function_name,
                            "line_number": node.lineno,
                            "related_to": handler["name"]
                        })
        
        return related_functions
    
    def _find_error_handlers(self, tree: ast.AST, content: str) -> List[Dict[str, Any]]:
        """Find error handling code in the AST."""
        error_handlers = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                # Found a try-except block
                error_handlers.append({
                    "type": "try_except",
                    "line_number": node.lineno,
                    "file": content.split('\n')[node.lineno - 1].strip()
                })
            elif isinstance(node, ast.Raise):
                # Found a raise statement
                error_handlers.append({
                    "type": "raise",
                    "line_number": node.lineno,
                    "file": content.split('\n')[node.lineno - 1].strip()
                })
        
        return error_handlers
    
    def _extract_dependencies(self, tree: ast.AST) -> List[str]:
        """Extract import statements from the AST."""
        dependencies = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    dependencies.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    dependencies.append(f"{module}.{alias.name}")
        
        return dependencies 