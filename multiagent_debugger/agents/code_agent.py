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
            self.code_path = getattr(config, 'code_path', None)
        else:
            self.llm_config = config.get("llm", {})
            self.code_path = config.get("code_path", None)
        
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
                role="Multi-Language Code Analysis Expert",
                goal="Analyze specific code files and lines across multiple programming languages to identify root causes of errors",
                backstory="You are a multi-language code analysis expert who examines source code in Python, Go, JavaScript, Java, Rust, and other languages to find bugs, identify issues, and suggest fixes.",
                verbose=verbose,
                allow_delegation=False,
                tools=tools or [],
                llm=llm,
                max_iter=1,
                memory=False,
                instructions="""
                You are a Multi-Language Code Analysis Expert. Your task is to analyze specific code files and lines to identify root causes of errors and suggest fixes.

                STEP-BY-STEP ANALYSIS WORKFLOW:

                STEP 1: EXTRACT INFORMATION FROM CONTEXT
                - Look for previous agent results containing "code_analysis_decision"
                - Extract target_file, target_line, target_function, and code_path from those results
                - Extract error_message and error_context from "most_recent_error"
                - If no previous results, use the provided task context

                STEP 2: VALIDATE TARGET FILE PATH
                - Check if the extracted target file path is within the configured code_path
                - Set validation flags accordingly

                STEP 3: USE TOOLS WITH EXTRACTED INFORMATION
                - Use directory_language_analyzer with error category based on error message and target file info
                - Use find_error_handlers with the specific target file path
                - Use find_dependencies with the target file and function name
                - Use smart_multilang_search with specific error patterns if needed

                STEP 3: ANALYZE TOOL RESULTS
                - Extract file existence and accessibility from tool outputs
                - Identify the programming language from file extension
                - Parse error handlers and dependencies from tool responses
                - Extract specific code lines and context from tool outputs

                STEP 4: POPULATE JSON RESPONSE
                Based on tool results, populate ALL JSON fields with specific information:

                TOOL USAGE INSTRUCTIONS:
                1. FIRST extract target information from context (target_file, target_line, target_function, code_path)
                2. Use directory_language_analyzer with relevant error category (e.g., "database" for DoesNotExist errors, "api" for endpoint errors)
                3. Use find_error_handlers with the SPECIFIC target file path (e.g., "/path/to/file.py")
                4. Use find_dependencies with target file and function name if available
                5. Extract specific code snippets, line numbers, and function information from tool outputs
                6. Parse tool responses to identify issues like null access, type errors, missing validation
                7. Generate actionable fixes based on error patterns found in tool results

                EXAMPLE INFORMATION EXTRACTION:
                If you see context like:
                "target_file": "/Users/vishnu_p/PycharmProjects/v1-soar/api/query_builder/views.py"
                "target_line": 182
                "target_function": "post"
                "error_message": "Chart matching query does not exist"
                "code_path": "/Users/vishnu_p/PycharmProjects/v1-soar/api/query_builder"

                Then call tools like:
                - directory_language_analyzer(error_category="database", component_hint="Chart", code_path="/Users/vishnu_p/PycharmProjects/v1-soar/api/query_builder")
                - find_error_handlers(file_path="/Users/vishnu_p/PycharmProjects/v1-soar/api/query_builder/views.py", function_name="post", code_path="/Users/vishnu_p/PycharmProjects/v1-soar/api/query_builder")

                HOW TO POPULATE JSON FROM TOOL RESULTS:
                - validation: Set based on path validation logic
                - targeted_analysis: Extract file info, language, existence from tool outputs
                - line_analysis: Extract specific code lines and issues from find_error_handlers results
                - function_analysis: Parse function signatures and parameters from tool outputs
                - code_issues: Identify specific fixes from error patterns in tool results
                - analysis_summary: Synthesize root cause from all tool findings

                OUTPUT FORMAT (JSON):
                {
                  "validation": {
                    "target_file_within_code_path": true/false,
                    "code_path_configured": true/false,
                    "validation_message": "[detailed validation explanation]",
                    "should_analyze": true/false,
                    "reason": "[why analysis should/should not proceed]"
                  },
                  "targeted_analysis": {
                    "target_file": "/path/to/analyzed/file.ext",
                    "target_line": 123,
                    "target_function": "function_name",
                    "programming_language": "[detected from file extension]",
                    "file_exists": true/false,
                    "file_accessible": true/false,
                    "analysis_quality": "[based on tool results quality]"
                  },
                  "line_analysis": {
                    "error_line_code": "[extract from find_error_handlers output]",
                    "error_line_context": "[extract context from tool results]",
                    "potential_issues": [
                      {
                        "issue_type": "[identified from error patterns]",
                        "description": "[specific issue from tool analysis]",
                        "line_number": 123,
                        "confidence": "[based on tool results]"
                      }
                    ]
                  },
                  "function_analysis": {
                    "function_name": "[extract from tool outputs]",
                    "function_signature": "[parse from find_error_handlers results]",
                    "parameters": ["param1", "param2"],
                    "return_type": "[extract if available]",
                    "error_handling": "[analyze from find_error_handlers output]",
                    "validation_logic": "[assess from code analysis]"
                  },
                  "code_issues": {
                    "immediate_fixes": [
                      {
                        "action": "[specific fix based on error analysis]",
                        "line_number": 123,
                        "description": "[what to change based on tool findings]",
                        "impact": "[what this fix will solve]"
                      }
                    ]
                  },
                  "analysis_summary": {
                    "root_cause": "[synthesize from all tool results]",
                    "confidence_level": "[based on tool analysis quality]",
                    "evidence_quality": "[assess tool result completeness]",
                    "fix_complexity": "[estimate based on identified issues]"
                  }
                }

                CRITICAL RULES:
                1. ONLY analyze real files that exist and are provided in context
                2. NEVER fabricate or hallucinate code analysis if no real data is available
                3. If no target file is provided or file doesn't exist, return should_analyze: false
                4. Extract specific information from tool outputs to populate JSON fields
                5. If tools return no results, explain why in the analysis
                6. Support all programming languages (.py, .go, .js, .ts, .java, .rs, .php, .rb, .cs, .cpp, .c, etc.)
                7. Validate file path before analysis - reject files outside code_path
                8. Provide specific, actionable fixes with exact line references
                9. Base all analysis on actual tool results, not assumptions
                10. If file doesn't exist or tools fail, report this clearly in the JSON
                """
            )
            return agent
        except Exception as e:
            import traceback
            print(f"ERROR: Failed to create CrewAI Agent: {e}")
            print(traceback.format_exc())
            raise
    
    def _is_path_allowed(self, file_path: str) -> bool:
        """Check if a file path is within the allowed code_path directory.
        
        Args:
            file_path: The file path to check
            
        Returns:
            bool: True if the path is allowed, False otherwise
        """
        if not self.code_path:
            # If no code_path is configured, allow all paths (backward compatibility)
            return True
        
        try:
            # Convert to absolute paths for comparison
            code_path_abs = os.path.abspath(self.code_path)
            file_path_abs = os.path.abspath(file_path)
            
            # Check if the file is within the code directory
            # Use os.path.commonpath to ensure proper path comparison
            common_path = os.path.commonpath([code_path_abs, file_path_abs])
            
            # If code_path is a file, check exact match
            if os.path.isfile(code_path_abs):
                return code_path_abs == file_path_abs
            
            # If code_path is a directory, check if file is within it
            return common_path == code_path_abs
            
        except (ValueError, OSError):
            # If there's any error in path comparison, deny access for security
            return False
    
    def validate_target_file_path(self, target_file_path: str) -> Dict[str, Any]:
        """Validate that a target file path from log extraction is within the allowed code_path.
        
        Args:
            target_file_path: The file path extracted from logs to validate
            
        Returns:
            Dict with validation results
        """
        validation_result = {
            "target_file_within_code_path": False,
            "code_path_configured": bool(self.code_path),
            "validation_message": "",
            "should_analyze": False
        }
        
        # Check if code_path is configured
        if not self.code_path:
            validation_result["validation_message"] = "No code_path configured in settings. Cannot validate target file path."
            return validation_result
        
        # Check if target file path is provided
        if not target_file_path:
            validation_result["validation_message"] = "No target file path provided for validation."
            return validation_result
        
        # Use the existing path validation logic
        if self._is_path_allowed(target_file_path):
            validation_result["target_file_within_code_path"] = True
            validation_result["should_analyze"] = True
            validation_result["validation_message"] = f"Target file '{target_file_path}' is within configured code_path '{self.code_path}'"
        else:
            validation_result["validation_message"] = f"Target file '{target_file_path}' is OUTSIDE configured code_path '{self.code_path}'. Analysis rejected for security."
        
        return validation_result
    
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
            "summary": "",
            "code_path_configured": bool(self.code_path),
            "code_path_accessible": False
        }
        
        # Check if code_path is configured and accessible
        if not self.code_path:
            results["summary"] = "No code_path configured in settings. Cannot analyze source code."
            return results
        
        if not os.path.exists(self.code_path):
            results["summary"] = f"Configured code_path '{self.code_path}' does not exist."
            return results
        
        results["code_path_accessible"] = True
        
        # Find source code files in the code path
        source_files = self._find_source_files(self.code_path)
        
        # Extract API route from entities
        api_route = entities.get("api_route")
        
        # Analyze each source file
        for file_path in source_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Get file extension to determine analysis approach
                file_ext = file_path.suffix.lower()
                
                # Use Python AST for Python files, generic text analysis for others
                if file_ext == '.py':
                    try:
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
                    except SyntaxError:
                        # If AST parsing fails, fall back to text analysis
                        self._analyze_file_as_text(file_path, content, api_route, results)
                else:
                    # For non-Python files, use generic text analysis
                    self._analyze_file_as_text(file_path, content, api_route, results)
                
            except Exception as e:
                print(f"Error analyzing file {file_path}: {str(e)}")
        
        # Generate summary
        total_files = len(source_files)
        file_types = set(f.suffix.lower() for f in source_files)
        results["summary"] = f"Analyzed {total_files} source files ({', '.join(file_types)}). " \
                            f"Found {len(results['api_handlers'])} API handlers, " \
                            f"{len(results['error_handlers'])} error handlers, and " \
                            f"{len(results['dependencies'])} dependencies."
        
        return results
    
    def _find_source_files(self, path: str) -> List[Path]:
        """Find all source code files in the given path (restricted to code_path)."""
        source_files = []
        
        if not path or not os.path.exists(path):
            return source_files
        
        # Define source code extensions
        source_extensions = [
            '.py', '.go', '.js', '.ts', '.java', '.cpp', '.c', '.rs', '.php', '.rb', 
            '.cs', '.swift', '.kt', '.scala', '.clj', '.hs', '.ml', '.fs', '.vb', 
            '.pl', '.sh', '.sql', '.html', '.css', '.toml', '.ini', '.cfg', '.conf'
        ]
        
        # If path is a single file, return it if it's a source file and allowed
        if os.path.isfile(path):
            if any(path.endswith(ext) for ext in source_extensions) and self._is_path_allowed(path):
                source_files.append(Path(path))
            return source_files
        
        # If path is a directory, walk through it
        for root, dirs, files in os.walk(path):
            for file in files:
                if any(file.endswith(ext) for ext in source_extensions):
                    file_path = os.path.join(root, file)
                    # Only include files that are within the allowed code_path
                    if self._is_path_allowed(file_path):
                        source_files.append(Path(file_path))
        return source_files
    
    def _analyze_file_as_text(self, file_path: Path, content: str, api_route: str, results: Dict[str, Any]) -> None:
        """Analyze a file using generic text patterns (for non-Python files)."""
        file_ext = file_path.suffix.lower()
        
        # Generic patterns for different languages
        if api_route:
            # Look for API route patterns
            api_patterns = [
                rf'{re.escape(api_route)}',  # Exact match
                rf'["\'{api_route}["\']',   # Quoted route
                rf'/{api_route}',           # Path with leading slash
                rf'{api_route}.*handler',   # Route with handler
            ]
            
            for pattern in api_patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    # Find the line number
                    line_num = content[:match.start()].count('\n') + 1
                    results["api_handlers"].append({
                        "name": f"handler_at_line_{line_num}",
                        "line_number": line_num,
                        "file": str(file_path),
                        "pattern": pattern
                    })
        
        # Look for error handling patterns across languages
        error_patterns = [
            r'try\s*{',                    # Java/C#/JavaScript try blocks
            r'try:',                       # Python try blocks
            r'catch\s*\(',                 # Java/JavaScript catch
            r'except\s*\w*:',             # Python except
            r'throw\s+new\s+\w+',         # Java/JavaScript throw
            r'raise\s+\w+',               # Python raise
            r'if\s+err\s*!=\s*nil',       # Go error handling
            r'Result<.*,.*>',             # Rust Result type
            r'Error\s*:',                 # Generic error labels
            r'panic!',                    # Rust panic
        ]
        
        for pattern in error_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                results["error_handlers"].append({
                    "type": "generic_error_handling",
                    "line_number": line_num,
                    "file": str(file_path),
                    "pattern": match.group()
                })
        
        # Look for import/dependency patterns
        import_patterns = {
            '.py': [r'^import\s+(\w+)', r'^from\s+(\w+)\s+import'],
            '.js': [r'^import\s+.*from\s+["\']([^"\']+)["\']', r'^const\s+.*=\s+require\(["\']([^"\']+)["\']\)'],
            '.ts': [r'^import\s+.*from\s+["\']([^"\']+)["\']', r'^import\s+.*=\s+require\(["\']([^"\']+)["\']\)'],
            '.go': [r'^import\s+["\']([^"\']+)["\']', r'^\s*["\']([^"\']+)["\']'],
            '.java': [r'^import\s+([\w\.]+);'],
            '.rs': [r'^use\s+([\w:]+);', r'^extern\s+crate\s+(\w+);'],
            '.php': [r'^use\s+([\w\\]+);', r'^include\s+["\']([^"\']+)["\']', r'^require\s+["\']([^"\']+)["\']'],
            '.rb': [r'^require\s+["\']([^"\']+)["\']', r'^gem\s+["\']([^"\']+)["\']'],
        }
        
        if file_ext in import_patterns:
            for pattern in import_patterns[file_ext]:
                matches = re.finditer(pattern, content, re.MULTILINE)
                for match in matches:
                    if match.groups():
                        results["dependencies"].append(match.group(1))
    
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