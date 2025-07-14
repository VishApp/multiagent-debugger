import os
from typing import Dict, Any, List, Optional
from pathlib import Path

from crewai import Agent
from crewai.tools import BaseTool

from multiagent_debugger.utils import get_verbose_flag, create_crewai_llm, get_agent_llm_config

class CodePathAnalyzerAgent:
    """Agent that validates code paths exist and are reachable within the project structure."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the CodePathAnalyzerAgent.
        
        Args:
            config: Configuration dictionary with model settings
        """
        self.config = config
        
        # Handle both dict and DebuggerConfig objects
        if hasattr(config, 'llm'):
            self.llm_config = config.llm
        else:
            self.llm_config = config.get("llm", {})
        
        # Get code path from config
        if hasattr(config, 'code_path'):
            self.code_path = config.code_path
        else:
            self.code_path = config.get("code_path", "")
        
    def create_agent(self, tools: List[BaseTool] = None) -> Agent:
        """Create and return the CrewAI agent.
        
        Args:
            tools: List of tools available to the agent
            
        Returns:
            Agent: The configured CrewAI agent
        """
        # Get LLM configuration parameters
        provider, model, temperature, api_key, api_base = get_agent_llm_config(self.llm_config)
        verbose = get_verbose_flag(self.config)
        
        # Create LLM
        llm = create_crewai_llm(provider, model, temperature, api_key, api_base)
        
        try:
            agent = Agent(
                role="Code Path Validation Specialist",
                goal="Validate that code paths exist on disk and are reachable within the expected project structure",
                backstory="You are an expert at analyzing file system structures and validating that code paths are accessible and properly organized within project directories.",
                verbose=verbose,
                allow_delegation=False,
                tools=tools or [],
                llm=llm,
                max_iter=1,
                memory=False,
                instructions="""
        CODE PATH VALIDATION ANALYSIS:
        
        Your mission is to validate code paths found in error logs and ensure they are:
        1. EXISTENT: The file actually exists on disk
        2. REACHABLE: The file is within the expected project structure
        3. ACCESSIBLE: The file can be read and analyzed
        4. RELEVANT: The file is part of the codebase being analyzed
        
        VALIDATION PROCESS:
        
        1. PATH EXISTENCE CHECK:
        - Verify the file exists at the specified path
        - Check if it's a regular file (not directory, symlink, etc.)
        - Confirm file permissions allow reading
        
        2. PROJECT STRUCTURE VALIDATION:
        - Ensure the file is within the configured code_path
        - Check if it follows expected project organization
        - Validate against common project patterns (src/, lib/, etc.)
        
        3. ACCESSIBILITY ASSESSMENT:
        - Test if the file can be opened and read
        - Check for any permission issues
        - Verify file encoding is readable
        
        4. RELEVANCE DETERMINATION:
        - Confirm the file is part of the active codebase
        - Check if it's a source file (not config, docs, tests, etc.)
        - Validate it's the correct file for the error context
        
        OUTPUT FORMAT (STRUCTURED JSON):
        
        {
          "validation_result": {
            "exists": true/false,
            "reachable": true/false,
            "accessible": true/false,
            "relevant": true/false,
            "project_root": "/path/to/project",
            "relative_path": "src/actions/file.ext",
            "file_size": 1234,
            "last_modified": "2024-01-01T12:00:00Z",
            "permissions": "rw-r--r--",
            "language": "python/javascript/java/go/rust/etc",
            "issues": [
              "File not found",
              "Outside project directory",
              "Permission denied"
            ]
          },
          "config_validation": {
            "in_config_yaml": true/false,
            "config_issues": ["list of config issues"],
            "config_recommendations": ["list of config fixes"]
          },
          "code_analysis": {
            "functions": ["list of functions in the file"],
            "classes": ["list of classes in the file"],
            "error_related_objects": ["objects related to the error"],
            "suggested_focus": ["specific areas to investigate"]
          },
          "next_agent": "code_analyzer"
        }
        
        LANGUAGE-AGNOSTIC SUPPORT:
        - Support all programming languages: Python, JavaScript, TypeScript, Java, Go, Rust, PHP, Ruby, C#, Swift, etc.
        - Detect language from file extension
        - Provide language-specific analysis patterns
        - Handle different project structures and conventions
        
        CRITICAL RULES:
        - Always provide structured JSON output
        - Be explicit about any issues found
        - If file doesn't exist, mark exists=false and provide clear reason
        - If file is outside project scope, mark reachable=false
        - If validation fails, provide detailed recommendations
        - If validation succeeds, analyze the file for error-related code
        - Always check config.yaml for proper module references
        - Be explicit about missing or uncertain data
        
        ERROR HANDLING:
        - Handle missing files gracefully
        - Provide alternative paths if possible
        - Suggest common file locations
        - Check for case sensitivity issues
        - Look for similar file names in the project
        - Handle different file path formats (absolute, relative, etc.)
        
        EXAMPLE OUTPUT (using real data only):
        {
          "validation_result": {
            "exists": true,
            "reachable": true,
            "accessible": true,
            "relevant": true,
            "project_root": "/path/to/project",
            "relative_path": "src/actions/file.py",
            "file_size": 1234,
            "last_modified": "2024-01-01T12:00:00Z",
            "language": "python",
            "issues": []
          },
          "config_validation": {
            "in_config_yaml": true,
            "config_issues": [],
            "config_recommendations": ["File properly configured"]
          },
          "code_analysis": {
            "functions": ["function1", "function2"],
            "classes": ["Class1"],
            "error_related_objects": ["error_handler", "validation_function"],
            "suggested_focus": ["error handling logic", "input validation"]
          },
          "next_agent": "code_analyzer"
        }
        """
            )
            return agent
        except Exception as e:
            import traceback
            print(f"ERROR: Failed to create CrewAI Agent: {e}")
            print(traceback.format_exc())
            raise
    
    def validate_code_path(self, code_path: str) -> Dict[str, Any]:
        """Validate a code path and return structured results.
        
        Args:
            code_path: The code path to validate
            
        Returns:
            Dict containing validation results
        """
        result = {
            "validation_result": {
                "exists": False,
                "reachable": False,
                "accessible": False,
                "relevant": False,
                "project_root": self.code_path,
                "relative_path": "",
                "file_size": 0,
                "last_modified": "",
                "permissions": "",
                "language": "unknown",
                "issues": []
            },
            "config_validation": {
                "in_config_yaml": False,
                "config_issues": [],
                "config_recommendations": []
            },
            "code_analysis": {
                "functions": [],
                "classes": [],
                "error_related_objects": [],
                "suggested_focus": []
            },
            "next_agent": "code_analyzer"
        }
        
        try:
            # Check if code path is provided
            if not code_path or code_path == "None":
                result["validation_result"]["issues"].append("No code path provided")
                return result
            
            # Normalize the path
            path_obj = Path(code_path)
            
            # Check if file exists
            if not path_obj.exists():
                result["validation_result"]["issues"].append(f"File not found: {code_path}")
                return result
            
            result["validation_result"]["exists"] = True
            
            # Check if it's a file
            if not path_obj.is_file():
                result["validation_result"]["issues"].append(f"Path is not a file: {code_path}")
                return result
            
            # Check if it's within the project directory
            try:
                relative_path = path_obj.relative_to(Path(self.code_path))
                result["validation_result"]["reachable"] = True
                result["validation_result"]["relative_path"] = str(relative_path)
            except ValueError:
                result["validation_result"]["issues"].append(f"File outside project directory: {code_path}")
                return result
            
            # Check if file is accessible
            try:
                with open(path_obj, 'r') as f:
                    f.read(1)  # Try to read first character
                result["validation_result"]["accessible"] = True
            except (PermissionError, OSError) as e:
                result["validation_result"]["issues"].append(f"File not accessible: {e}")
                return result
            
            # Get file metadata
            stat = path_obj.stat()
            result["validation_result"]["file_size"] = stat.st_size
            result["validation_result"]["last_modified"] = str(stat.st_mtime)
            
            # Determine language from extension
            ext = path_obj.suffix.lower()
            language_map = {
                '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
                '.java': 'java', '.go': 'go', '.rs': 'rust', '.php': 'php',
                '.rb': 'ruby', '.cs': 'csharp', '.swift': 'swift', '.kt': 'kotlin',
                '.scala': 'scala', '.clj': 'clojure', '.hs': 'haskell', '.ml': 'ocaml',
                '.fs': 'fsharp', '.vb': 'vbnet', '.pl': 'perl', '.sh': 'bash',
                '.sql': 'sql', '.html': 'html', '.css': 'css', '.xml': 'xml',
                '.json': 'json', '.yaml': 'yaml', '.yml': 'yaml', '.toml': 'toml',
                '.ini': 'ini', '.cfg': 'config', '.conf': 'config'
            }
            result["validation_result"]["language"] = language_map.get(ext, 'unknown')
            
            # Check if file is relevant (source file, not config/docs)
            if self._is_source_file(path_obj):
                result["validation_result"]["relevant"] = True
                # Analyze the file for functions, classes, etc.
                self._analyze_file_content(path_obj, result)
            else:
                result["validation_result"]["issues"].append("File is not a source file")
            
        except Exception as e:
            result["validation_result"]["issues"].append(f"Validation error: {e}")
        
        return result
    
    def _is_source_file(self, path: Path) -> bool:
        """Check if a file is a source code file."""
        # Source file extensions
        source_extensions = {
            '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs', '.php', 
            '.rb', '.cs', '.swift', '.kt', '.scala', '.clj', '.hs', '.ml', '.fs', 
            '.vb', '.pl', '.sh', '.sql', '.html', '.css', '.xml'
        }
        
        # Config/documentation extensions to exclude
        config_extensions = {
            '.yaml', '.yml', '.json', '.xml', '.ini', '.cfg', '.conf', '.md', 
            '.txt', '.rst', '.toml'
        }
        
        ext = path.suffix.lower()
        
        # Check if it's a source file
        if ext in source_extensions:
            return True
        
        # Check if it's a config file (exclude)
        if ext in config_extensions:
            return False
        
        # Check directory patterns
        path_str = str(path).lower()
        exclude_patterns = ['test', 'tests', 'docs', 'documentation', 'examples', 'samples']
        
        for pattern in exclude_patterns:
            if pattern in path_str:
                return False
        
        return True
    
    def _analyze_file_content(self, path: Path, result: Dict[str, Any]) -> None:
        """Analyze file content for functions, classes, and error-related objects."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Extract functions and classes based on language
            language = result["validation_result"]["language"]
            
            if language == 'python':
                self._analyze_python_content(content, result)
            elif language in ['javascript', 'typescript']:
                self._analyze_js_content(content, result)
            elif language == 'java':
                self._analyze_java_content(content, result)
            elif language == 'go':
                self._analyze_go_content(content, result)
            elif language == 'rust':
                self._analyze_rust_content(content, result)
            else:
                # Generic analysis for other languages
                self._analyze_generic_content(content, result)
                
        except Exception as e:
            result["code_analysis"]["suggested_focus"].append(f"Error analyzing file content: {e}")
    
    def _analyze_python_content(self, content: str, result: Dict[str, Any]) -> None:
        """Analyze Python file content."""
        import re
        
        # Find function definitions
        function_pattern = r'def\s+(\w+)\s*\('
        functions = re.findall(function_pattern, content)
        result["code_analysis"]["functions"].extend(functions)
        
        # Find class definitions
        class_pattern = r'class\s+(\w+)'
        classes = re.findall(class_pattern, content)
        result["code_analysis"]["classes"].extend(classes)
        
        # Find error-related patterns
        error_patterns = [
            r'try:', r'except', r'raise', r'assert', r'logging\.error',
            r'logger\.error', r'print.*error', r'return.*error'
        ]
        
        for pattern in error_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                result["code_analysis"]["error_related_objects"].append(pattern)
        
        if result["code_analysis"]["error_related_objects"]:
            result["code_analysis"]["suggested_focus"].append("Error handling logic")
    
    def _analyze_js_content(self, content: str, result: Dict[str, Any]) -> None:
        """Analyze JavaScript/TypeScript file content."""
        import re
        
        # Find function definitions
        function_patterns = [
            r'function\s+(\w+)\s*\(',
            r'const\s+(\w+)\s*=\s*\([^)]*\)\s*=>',
            r'let\s+(\w+)\s*=\s*\([^)]*\)\s*=>',
            r'(\w+)\s*\([^)]*\)\s*{'
        ]
        
        for pattern in function_patterns:
            functions = re.findall(pattern, content)
            result["code_analysis"]["functions"].extend(functions)
        
        # Find class definitions
        class_pattern = r'class\s+(\w+)'
        classes = re.findall(class_pattern, content)
        result["code_analysis"]["classes"].extend(classes)
        
        # Find error-related patterns
        error_patterns = [
            r'try\s*{', r'catch\s*\(', r'throw', r'console\.error',
            r'logger\.error', r'error.*handler'
        ]
        
        for pattern in error_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                result["code_analysis"]["error_related_objects"].append(pattern)
    
    def _analyze_java_content(self, content: str, result: Dict[str, Any]) -> None:
        """Analyze Java file content."""
        import re
        
        # Find method definitions
        method_pattern = r'(?:public|private|protected)?\s*(?:static\s+)?(?:final\s+)?\w+\s+(\w+)\s*\('
        methods = re.findall(method_pattern, content)
        result["code_analysis"]["functions"].extend(methods)
        
        # Find class definitions
        class_pattern = r'class\s+(\w+)'
        classes = re.findall(class_pattern, content)
        result["code_analysis"]["classes"].extend(classes)
        
        # Find error-related patterns
        error_patterns = [
            r'try\s*{', r'catch\s*\(', r'throw', r'System\.err',
            r'logger\.error', r'Exception'
        ]
        
        for pattern in error_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                result["code_analysis"]["error_related_objects"].append(pattern)
    
    def _analyze_go_content(self, content: str, result: Dict[str, Any]) -> None:
        """Analyze Go file content."""
        import re
        
        # Find function definitions
        function_pattern = r'func\s+(\w+)\s*\('
        functions = re.findall(function_pattern, content)
        result["code_analysis"]["functions"].extend(functions)
        
        # Find error-related patterns
        error_patterns = [
            r'if\s+err\s*!=', r'return.*err', r'panic\(',
            r'log\.Error', r'fmt\.Errorf'
        ]
        
        for pattern in error_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                result["code_analysis"]["error_related_objects"].append(pattern)
    
    def _analyze_rust_content(self, content: str, result: Dict[str, Any]) -> None:
        """Analyze Rust file content."""
        import re
        
        # Find function definitions
        function_pattern = r'fn\s+(\w+)\s*\('
        functions = re.findall(function_pattern, content)
        result["code_analysis"]["functions"].extend(functions)
        
        # Find error-related patterns
        error_patterns = [
            r'Result<', r'Option<', r'\.unwrap\(\)', r'\.expect\(',
            r'panic!', r'eprintln!', r'println!.*error'
        ]
        
        for pattern in error_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                result["code_analysis"]["error_related_objects"].append(pattern)
    
    def _analyze_generic_content(self, content: str, result: Dict[str, Any]) -> None:
        """Generic analysis for other languages."""
        import re
        
        # Look for common patterns
        function_patterns = [
            r'function\s+(\w+)', r'def\s+(\w+)', r'func\s+(\w+)',
            r'fn\s+(\w+)', r'(\w+)\s*\([^)]*\)\s*{'
        ]
        
        for pattern in function_patterns:
            functions = re.findall(pattern, content, re.IGNORECASE)
            result["code_analysis"]["functions"].extend(functions)
        
        # Look for error-related patterns
        error_patterns = [
            r'error', r'exception', r'fail', r'panic', r'throw',
            r'try', r'catch', r'except', r'assert'
        ]
        
        for pattern in error_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                result["code_analysis"]["error_related_objects"].append(pattern) 