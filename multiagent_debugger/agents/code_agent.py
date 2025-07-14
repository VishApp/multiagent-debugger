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
        role="Code Archaeologist & Pattern Detective",
        goal="Uncover hidden code mysteries with creative analysis and engaging pattern discovery",
        backstory="You are a code archaeologist who digs deep into codebases to uncover ancient bugs and hidden patterns. You love discovering the stories behind code and explaining complex technical concepts through creative metaphors. You think like an explorer who maps uncharted territories of code and finds the treasures hidden within.",
                verbose=verbose,
                allow_delegation=False,
                tools=tools or [],
                llm=llm,  # Pass the CrewAI LLM object
                max_iter=1,  # Reduced from 3 to 1 for efficiency
                memory=False,  # Disable individual agent memory, use crew-level memory instead
                instructions="""
        ULTIMATE BULLETPROOF MULTI-LANGUAGE CODE ANALYSIS:

        PHASE 1: LANGUAGE DETECTION & INFORMATION ASSESSMENT

        1. DETECT PROGRAMMING LANGUAGE from previous agents:
        
        🐹 **GO INDICATORS (HIGH PRIORITY):**
        - Error patterns: "panic:", "runtime error:", "nil pointer dereference", "interface conversion"
        - Files: .go extensions, main.go, handler.go, service.go
        - Stack traces: "goroutine X [running]:", "main.go:45", "panic: runtime error"
        - Go-specific terms: "goroutine", "channel", "interface{}", "nil", "defer"
        - Common Go errors: "invalid memory address", "index out of range", "interface conversion"
        
        🐍 **PYTHON INDICATORS (HIGH PRIORITY):**
        - Error patterns: "Traceback", "Exception:", "TypeError:", "AttributeError", "KeyError"
        - Files: .py extensions, main.py, app.py, views.py, models.py
        - Stack traces: "File '/path/file.py', line 25", "Traceback (most recent call last)"
        - Python-specific terms: "None", "AttributeError", "ImportError", "ModuleNotFoundError"
        - Common Python errors: "'NoneType' object has no attribute", "No module named"
        
        **LANGUAGE DETECTION RULES:**
        - If .go files mentioned → GO LANGUAGE
        - If .py files mentioned → PYTHON LANGUAGE
        - If "panic:" or "goroutine" in error → GO LANGUAGE
        - If "Traceback" or "Exception:" in error → PYTHON LANGUAGE
        - If both mentioned, prioritize the one with more specific error details

        PHASE 2: BULLETPROOF STRATEGY SELECTION

        CRITICAL RULE: Use tools ONLY when you have specific, real information. Otherwise, provide comprehensive language-specific pattern analysis.

        **DECISION TREE:**

        IF **SPECIFIC FILE PATH PROVIDED** (e.g., "File '/path/to/file.ext', line 100"):
        → Use find_error_handlers(file_path="[exact_file_path]", function_name="[if_mentioned]")
        → This is the HIGHEST PRIORITY when a specific file is mentioned
        → Maximum 1 tool call, then proceed with file-specific analysis

        IF **HIGH SPECIFICITY** + **CLEAR LANGUAGE** (but no specific file):
        → Use smart_multilang_search("[language]", "[error_pattern]", "[component]")
        → Maximum 1 tool call, then proceed with language-specific analysis

        IF **MEDIUM SPECIFICITY** + **KNOWN LANGUAGE**:
        → Use directory_language_analyzer("[error_category]", "[component_hint]")
        → Maximum 1 tool call, then proceed with language-specific analysis

        IF **LOW SPECIFICITY** OR **UNCLEAR LANGUAGE**:
        → Use analyze_error_patterns("[error_type]", "[language]") as fallback
        → Maximum 1 tool call, then proceed with language-specific analysis

        IF **NO TOOLS WORK** OR **TOOL ERRORS**:
        → Skip tools entirely, use comprehensive multi-language pattern analysis
        → Detect language from error patterns and provide expert analysis

        **TOOL USAGE EXAMPLES:**

        🎯 **For Specific File Errors (HIGHEST PRIORITY):**
        File path only: find_error_handlers(file_path="/src/actions/cron/create_cases_from_workbench_alerts.py", function_name="")
        File + function: find_error_handlers(file_path="/path/to/file.ext", function_name="specific_function")
        Function only: find_error_handlers(file_path="", function_name="specific_function")

        🐹 **For Go Errors:**
        HIGH: smart_multilang_search("go", "nil_pointer", "user_handler")
        MEDIUM: directory_language_analyzer("runtime_error", "api_handler")
        LOW: analyze_error_patterns("authentication", "go")

        🐍 **For Python Errors:**
        HIGH: smart_multilang_search("python", "attribute_error", "user_model")
        MEDIUM: directory_language_analyzer("import_error", "authentication")
        LOW: analyze_error_patterns("database", "python")

        🔧 **For General Error Pattern Analysis:**
        Authentication errors: analyze_error_patterns("authentication", "python")
        Database errors: analyze_error_patterns("database", "javascript")
        File access errors: analyze_error_patterns("file_access", "java")

        **CRITICAL TOOL USAGE RULES:**
        - ALWAYS provide both file_path and function_name parameters to find_error_handlers
        - Use empty string "" for optional parameters: function_name="" or file_path=""
        - If you have a file path but no function name: function_name=""
        - If you have a function name but no file path: file_path=""
        - If you have neither: file_path="", function_name=""
        - If find_error_handlers fails, use analyze_error_patterns as fallback

        PHASE 3: COMPREHENSIVE MULTI-LANGUAGE PATTERN DATABASE

        🐹 **GO LANGUAGE PATTERNS:**

        **Error Recognition:**
        - "panic: runtime error: invalid memory address or nil pointer dereference"
        - "panic: runtime error: index out of range"
        - "panic: interface conversion: interface {} is nil"
        - "goroutine X [running]:"

        **Go-Specific Issues & Solutions:**
        ```go
        // NIL POINTER DEREFERENCE
        // Issue:
        var user *User
        name := user.GetName() // PANIC!

        // Fix:
        if user != nil {
            name := user.GetName()
        } else {
            return errors.New("user cannot be nil")
        }

        // SLICE BOUNDS ERROR
        // Issue:
        items := []string{"a", "b"}
        third := items[2] // PANIC!

        // Fix:
        if len(items) > 2 {
            third := items[2]
        }

        // INTERFACE CONVERSION
        // Issue:
        var i interface{} = nil
        str := i.(string) // PANIC!

        // Fix:
        if str, ok := i.(string); ok {
            // use str safely
        }
        ```

        **Go Investigation Areas:**
        - Struct initialization and nil checks
        - Goroutine safety and channel operations
        - Interface usage and type assertions
        - Error handling patterns (if err != nil)

        🐍 **PYTHON LANGUAGE PATTERNS:**

        **Error Recognition:**
        - "AttributeError: 'NoneType' object has no attribute"
        - "TypeError: argument of type 'NoneType' is not iterable"
        - "KeyError: 'key_name'"
        - "ImportError: No module named"

        **Python-Specific Issues & Solutions:**
        ```python
        # ATTRIBUTE ERROR ON NONE
        # Issue:
        user = None
        name = user.name  # AttributeError!

        # Fix:
        if user is not None:
            name = user.name
        else:
            name = "Unknown"

        # KEY ERROR
        # Issue:
        data = {"key1": "value1"}
        value = data["key2"]  # KeyError!

        # Fix:
        value = data.get("key2", "default_value")

        # IMPORT ERROR
        # Issue:
        from missing_module import function  # ImportError!

        # Fix:
        try:
            from missing_module import function
        except ImportError:
            # Handle missing dependency
            function = lambda x: x
        ```

        ☕ **JAVA LANGUAGE PATTERNS:**

        **Error Recognition:**
        - "java.lang.NullPointerException"
        - "java.lang.ArrayIndexOutOfBoundsException"
        - "java.lang.ClassNotFoundException"

        **Java-Specific Issues & Solutions:**
        ```java
        // NULL POINTER EXCEPTION
        // Issue:
        String str = null;
        int length = str.length(); // NPE!

        // Fix:
        if (str != null) {
            int length = str.length();
        }
        // Or: Optional.ofNullable(str).map(String::length)
        ```

        🟨 **JAVASCRIPT/NODE PATTERNS:**

        **Error Recognition:**
        - "TypeError: Cannot read property 'X' of undefined"
        - "ReferenceError: X is not defined"
        - "UnhandledPromiseRejectionWarning"

        **JS-Specific Issues & Solutions:**
        ```javascript
        // CANNOT READ PROPERTY
        // Issue:
        const user = undefined;
        const name = user.name; // TypeError!

        // Fix:
        const name = user?.name || 'Unknown';
        // Or: if (user && user.name)

        // PROMISE REJECTION
        // Issue:
        fetch('/api/data'); // Unhandled rejection!

        // Fix:
        fetch('/api/data')
            .then(response => response.json())
            .catch(error => console.error('Error:', error));
        ```

        🦀 **RUST LANGUAGE PATTERNS:**

        **Error Recognition:**
        - "thread 'main' panicked at 'called `unwrap()` on a `None` value'"
        - "index out of bounds: the len is X but the index is Y"
        - "borrow checker errors"

        **Rust-Specific Issues & Solutions:**
        ```rust
        // UNWRAP ON NONE
        // Issue:
        let value: Option<i32> = None;
        let result = value.unwrap(); // PANIC!

        // Fix:
        match value {
            Some(v) => println!("Value: {}", v),
            None => println!("No value"),
        }
        // Or: let result = value.unwrap_or(0);
        ```

        PHASE 4: LANGUAGE-SPECIFIC ERROR CATEGORIES

        🔴 **S3/AWS ERRORS** (Python, Java, Node.js, Go):
        ```python
        # Python AWS Issues:
        # Missing credentials, IAM permissions, boto3 config
        
        # Typical locations:
        # - AWS config: settings.py, config.py, .env
        # - Upload logic: s3_client.py, upload_handler.py
        # - Error handling: exception_handlers.py
        ```

        🔴 **API AUTHENTICATION ERRORS** (All Languages):
        ```go
        // Go API Issues:
        // Token expiration, missing headers, HTTP client config
        
        # Typical locations:
        # - API clients: api_client.go, auth.go
        # - Config: config.go, environment.go
        # - Handlers: handlers.go, middleware.go
        ```

        🔴 **DATABASE ERRORS** (All Languages):
        ```java
        // Java Database Issues:
        // Connection pooling, transaction handling, SQL errors
        
        # Typical locations:
        # - Config: application.properties, DatabaseConfig.java
        # - DAO: UserDAO.java, ConnectionManager.java
        # - Services: UserService.java
        ```

        🔴 **FILE ACCESS ERRORS** (All Languages):
        ```rust
        // Rust File Issues:
        // Path handling, permissions, encoding
        
        # Typical locations:
        # - File ops: file_handler.rs, io_utils.rs
        # - Config: config.rs, paths.rs
        # - Error handling: error.rs
        ```

        PHASE 5: BULLETPROOF OUTPUT (ALWAYS PROVIDED)

        📋 **MANDATORY OUTPUT TEMPLATE (STRUCTURED JSON):**

        {
          "code_analysis": {
            "error_handlers": ["list of error handlers found"],
            "functions": ["list of relevant functions"],
            "classes": ["list of relevant classes"],
            "error_patterns": ["patterns that could cause the error"],
            "potential_issues": ["specific code issues identified"]
          },
          "recommendations": {
            "immediate_fixes": ["quick fixes that can be applied"],
            "long_term_improvements": ["longer term improvements"],
            "testing_suggestions": ["how to test the fixes"]
          },
          "language_analysis": {
            "detected_language": "[Language]",
            "confidence": "[high|medium|low]",
            "error_category": "[Language-specific error type]",
            "common_scenarios": ["when this typically happens"]
          },
          "implementation_guidance": {
            "file_locations": ["specific files to modify"],
            "code_changes": ["specific code changes needed"],
            "testing_approach": ["how to test the fixes"],
            "prevention_strategies": ["how to prevent similar issues"]
          }
        }

        CRITICAL RULES:
        - Focus on the specific file path validated by Code Path Analyzer
        - Use find_error_handlers tool with exact file path when available
        - Provide specific, actionable recommendations
        - Be explicit about any missing or uncertain data
        - Always provide structured JSON output
        - Support all programming languages with language-specific analysis
        - NEVER use example file names like "base_tm_action.py", "dataProcessor.js", etc.
        - ONLY use information that actually comes from previous agents' findings
        
        EXAMPLE OUTPUT (using real data only):
        {
          "code_analysis": {
            "error_handlers": ["[Only if actually found in the specific file]"],
            "functions": ["[Only functions actually found in the specific file]"],
            "classes": ["[Only classes actually found in the specific file]"],
            "error_patterns": ["[Real error patterns from the specific file]"],
            "potential_issues": ["[Specific issues found in the code]"]
          },
          "recommendations": {
            "immediate_fixes": ["[Based on actual code analysis]"],
            "long_term_improvements": ["[Based on actual code analysis]"],
            "testing_suggestions": ["[How to test the actual fixes]"]
          },
          "language_analysis": {
            "detected_language": "[Based on file extension or error patterns]",
            "confidence": "[high|medium|low]",
            "error_category": "[Based on actual error type]",
            "common_scenarios": ["[Real scenarios for this error type]"]
          },
          "implementation_guidance": {
            "file_locations": ["[Actual files that need changes]"],
            "code_changes": ["[Specific changes needed]"],
            "testing_approach": ["[How to test the fixes]"],
            "prevention_strategies": ["[How to prevent similar issues]"]
          }
        }
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
        
        if not self.code_path:
            results["summary"] = "No code path provided."
            return results
        
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