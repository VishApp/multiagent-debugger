import os
import re
from typing import Dict, Any, List, Optional

from crewai import Crew, Task, Agent, Process
from crewai.tools import tool

from multiagent_debugger.agents.question_analyzer_agent import QuestionAnalyzerAgent
from multiagent_debugger.agents.log_agent import LogAgent
from multiagent_debugger.agents.code_path_analyzer_agent import CodePathAnalyzerAgent
from multiagent_debugger.agents.code_agent import CodeAgent
from multiagent_debugger.agents.root_cause_agent import RootCauseAgent

from multiagent_debugger.tools.log_tools import create_enhanced_grep_logs_tool, create_enhanced_filter_logs_tool, create_enhanced_extract_stack_traces_tool, create_error_pattern_analysis_tool
from multiagent_debugger.tools.code_tools import create_find_api_handlers_tool, create_find_dependencies_tool, create_find_error_handlers_tool, create_directory_language_analyzer_tool, create_smart_multilang_search_tool, create_error_pattern_analyzer_tool
from multiagent_debugger.tools.flowchart_tool import create_error_flowchart_tool, create_system_flowchart_tool, create_decision_flowchart_tool, create_sequence_flowchart_tool, create_debugging_storyboard_tool, create_clean_mermaid_tool, create_comprehensive_debugging_flowchart_tool
from multiagent_debugger.utils import set_crewai_env_vars, get_env_var_name_for_provider

class DebuggerCrew:
    """Main class for orchestrating the multi-agent debugger crew."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the DebuggerCrew.
        
        Args:
            config: Configuration dictionary with model settings, log paths, and code path
        """
        self.config = config
        # Handle both dict and DebuggerConfig objects
        if hasattr(config, 'log_paths'):
            self.log_paths = config.log_paths
        else:
            self.log_paths = config.get("log_paths", [])
            
        if hasattr(config, 'code_path'):
            self.code_path = config.code_path
        else:
            self.code_path = config.get("code_path", "")
        
        # Get provider and set environment variables
        if hasattr(config, 'llm'):
            provider = config.llm.provider
            api_key = config.llm.api_key if hasattr(config.llm, 'api_key') else None
        else:
            provider = config.get("llm", {}).get("provider", "openai")
            api_key = config.get("llm", {}).get("api_key")
        
        # Set environment variable for API key
        if api_key:
            env_var_name = get_env_var_name_for_provider(provider, "api_key")
            if env_var_name:
                os.environ[env_var_name] = api_key
        
        # Set CrewAI environment variables for memory
        set_crewai_env_vars(provider, api_key)
        
        # Initialize agents
        self.question_analyzer = QuestionAnalyzerAgent(config)
        self.log_agent = LogAgent(config)
        self.code_path_analyzer = CodePathAnalyzerAgent(config)
        self.code_agent = CodeAgent(config)
        self.root_cause_agent = RootCauseAgent(config)
        
        # Initialize tools
        self.log_tools = self._create_log_tools()
        self.code_tools = self._create_code_tools()
        self.flowchart_tools = self._create_flowchart_tools()
        
        # Create CrewAI agents with retry configuration
        self.question_analyzer_agent = self.question_analyzer.create_agent()
        self.log_agent_agent = self.log_agent.create_agent(tools=self.log_tools + self.flowchart_tools)
        self.code_path_analyzer_agent = self.code_path_analyzer.create_agent()
        self.code_agent_agent = self.code_agent.create_agent(tools=self.code_tools + self.flowchart_tools)
        self.root_cause_agent_agent = self.root_cause_agent.create_agent(tools=self.flowchart_tools)
        
        # Create crew
        self.crew = self._create_crew()
    def _create_flowchart_tools(self) -> List:
        """Create tools for flowchart generation."""
        return [
            create_error_flowchart_tool(),
            create_system_flowchart_tool(),
            create_decision_flowchart_tool(),
            create_sequence_flowchart_tool(),
            create_debugging_storyboard_tool(),
            create_clean_mermaid_tool(),
            create_comprehensive_debugging_flowchart_tool()
        ]
    
    def _create_log_tools(self) -> List:
        """Create tools for log analysis."""
        return [
            create_enhanced_grep_logs_tool(self.log_paths),
            create_enhanced_filter_logs_tool(self.log_paths), 
            create_enhanced_extract_stack_traces_tool(self.log_paths),
            create_error_pattern_analysis_tool(self.log_paths),
        ]
    
    def _create_code_tools(self) -> List:
        """Create tools for code analysis."""
        return [
            create_find_api_handlers_tool(self.code_path),
            create_find_dependencies_tool(self.code_path),
            create_find_error_handlers_tool(self.code_path),
            create_directory_language_analyzer_tool(self.code_path),
            create_smart_multilang_search_tool(self.code_path),
            create_error_pattern_analyzer_tool(self.code_path),
        ]
    
    def _create_crew(self) -> Crew:
        """Create and return a CrewAI crew.
        
        Returns:
            Crew: The configured CrewAI crew
        """
        # Get provider info for memory configuration
        if hasattr(self.config, 'llm'):
            provider = self.config.llm.provider.lower()
        else:
            provider = self.config.get("llm", {}).get("provider", "openai").lower()
        
        # Configure memory based on provider
        memory_config = {
            "memory": False,
            "cache": True
        }
        
        # Create crew with retry configuration
        crew = Crew(
            agents=[
                self.question_analyzer_agent,
                self.log_agent_agent,
                self.code_path_analyzer_agent,
                self.code_agent_agent,
                self.root_cause_agent_agent
            ],
            tasks=self._create_tasks(""),  # Placeholder, will be replaced in debug()
            verbose=True,
            process=Process.sequential,  # Use sequential process
            max_rpm=15,  # Maximum requests per minute
            max_iter=1,  # Reduced to 1 to prevent infinite loops
            **memory_config
        )
        
        return crew
    
    def debug(self, question: str) -> str:
        """Run the debugging process.
        
        Args:
            question: The debugging question to answer
            
        Returns:
            String containing the debugging result
        """
        # Validate paths before starting
        validation_result = self._validate_paths()
        if validation_result:
            return validation_result

        # Create tasks
        tasks = self._create_tasks(question)
        self.crew.tasks = tasks
        
        # Run the crew with detailed error logging
        try:
            result = self.crew.kickoff()
        except Exception as e:
            import traceback
            print(f"ERROR: Exception during CrewAI kickoff: {e}")
            print(traceback.format_exc())
            raise
        
        # Determine final result string
        final_result = (
            result.raw_output if hasattr(result, 'raw_output')
            else result if isinstance(result, str)
            else str(result)
        )

        return final_result
    
    def _validate_paths(self) -> str:
        """Validate that required paths exist and are accessible."""
        issues = []
        
        # Check log paths
        if not self.log_paths:
            issues.append("❌ No log paths configured")
        else:
            valid_log_paths = []
            for log_path in self.log_paths:
                if os.path.exists(log_path):
                    valid_log_paths.append(log_path)
                else:
                    issues.append(f"❌ Log path does not exist: {log_path}")
            
            if not valid_log_paths:
                issues.append("❌ No valid log files found - cannot perform log analysis")
        
        # Check code path
        if not self.code_path:
            issues.append("❌ No code path configured")
        elif not os.path.exists(self.code_path):
            issues.append(f"❌ Code path does not exist: {self.code_path}")
        
        if issues:
            return f"""
🚨 CONFIGURATION VALIDATION FAILED

The following issues prevent debugging from proceeding:

{chr(10).join(issues)}

📋 REQUIRED ACTIONS:
1. Update your config.yaml with valid paths
2. Ensure log files exist and are readable
3. Ensure code path points to a valid directory
4. Run the debugger again

Example valid configuration:
```yaml
log_paths:
  - /var/log/myapp/app.log
  - /var/log/nginx/access.log
code_path: /path/to/your/codebase
```
"""
        
        return None
    
        """Validate that question analysis doesn't contain fake data."""
        # Common fake file patterns that agents might generate
        fake_patterns = [
            r'/src/utils/dataProcessor\.js',
            r'base_tm_action\.py',
            r'dataProcessor\.js',
            r'processData',
            r'/src/api\.js',
            r'fetchData',
            r'/v1/data',
            r'base_tm_action',
            r'get_siem'
        ]
        
        # Check if analysis contains fake patterns
        found_fake_data = []
        for pattern in fake_patterns:
            if re.search(pattern, analysis_result, re.IGNORECASE):
                found_fake_data.append(pattern)
        
        if found_fake_data:
            return f"""
🚨 FAKE DATA DETECTED

The question analyzer extracted fake data that doesn't exist in your actual error:

Fake patterns found: {', '.join(found_fake_data)}

Your original question: "{question}"

The analyzer should only extract information that is EXPLICITLY mentioned in your error/question.

📋 REQUIRED ACTIONS:
1. Provide a more specific error message with actual file names and error details
2. If you don't have specific file names, just describe the error without them
3. The system will work with general error descriptions

Example good error descriptions:
- "My API is returning 500 errors"
- "Database connection is failing"
- "Authentication is not working"
- "File upload is failing with permission errors"
"""
        
        # Check if the question contains a specific file path but analysis doesn't extract it
        file_path_patterns = [
            r'File\s+"([^"]+)"',
            r'File\s+\'([^\']+)\'',
            r'File\s+"([^"]+\.(py|js|ts|java|cpp|c|go|rs|php|rb|cs|swift|kt|scala|clj|hs|ml|fs|vb|pl|sh|sql|html|css|xml|json|yaml|yml|toml|ini|cfg|conf|md|txt))"',
            r'File\s+\'([^\']+\.(py|js|ts|java|cpp|c|go|rs|php|rb|cs|swift|kt|scala|clj|hs|ml|fs|vb|pl|sh|sql|html|css|xml|json|yaml|yml|toml|ini|cfg|conf|md|txt))\'',
            r'in\s+([^\s]+\.(py|js|ts|java|cpp|c|go|rs|php|rb|cs|swift|kt|scala|clj|hs|ml|fs|vb|pl|sh|sql|html|css|xml|json|yaml|yml|toml|ini|cfg|conf|md|txt))',
            r'at\s+([^\s]+\.(py|js|ts|java|cpp|c|go|rs|php|rb|cs|swift|kt|scala|clj|hs|ml|fs|vb|pl|sh|sql|html|css|xml|json|yaml|yml|toml|ini|cfg|conf|md|txt))',
            r'([^\s]+\.(py|js|ts|java|cpp|c|go|rs|php|rb|cs|swift|kt|scala|clj|hs|ml|fs|vb|pl|sh|sql|html|css|xml|json|yaml|yml|toml|ini|cfg|conf|md|txt))'
        ]
        
        question_file_paths = []
        for pattern in file_path_patterns:
            matches = re.findall(pattern, question)
            question_file_paths.extend(matches)
        
        analysis_file_paths = []
        for pattern in file_path_patterns:
            matches = re.findall(pattern, analysis_result)
            analysis_file_paths.extend(matches)
        
        # If question has file paths but analysis doesn't extract them
        if question_file_paths and not analysis_file_paths:
            return f"""
🚨 FILE PATH EXTRACTION FAILED

The question analyzer failed to extract file paths that are present in your error:

File paths found in your error: {', '.join(question_file_paths)}
File paths extracted by analyzer: {', '.join(analysis_file_paths) if analysis_file_paths else 'None'}

Your original question: "{question}"

The analyzer should extract ALL file paths mentioned in your error/question.

📋 REQUIRED ACTIONS:
1. The system will retry with enhanced file path extraction
2. If the issue persists, provide the error message in a simpler format
3. Focus on the specific file path that contains the error
"""
        
        return None
    
    def _create_tasks(self, question: str) -> List[Task]:
        """Create tasks for the debugging process with conditional flow logic.
        
        Args:
            question: The debugging question to answer
            
        Returns:
            List of CrewAI Task objects
        """
        # Task 1: Question Analyzer - Break user's question into clear tasks
        analyze_task = Task(
            description=f"""
        SYSTEM INSTRUCTION: You are a multi-agent system designed to debug application issues.

        TASK: Break the user's question into clear tasks for log agent, code agent, root cause agent, and flowchart analysis agent.

        USER QUESTION: '{question}'

        ANALYSIS REQUIREMENTS:
        1. Extract error type, severity, and key details
        2. Identify search terms for log analysis
        3. Determine code focus areas
        4. Create investigation roadmap

        OUTPUT FORMAT (STRUCTURED JSON):
        {{
          "error_classification": {{
            "type": "[API|Database|File|Network|Script|OS|Memory|Auth|Config]",
            "severity": "[P0-Critical|P1-Urgent|P2-High|P3-Medium]",
            "description": "[Brief error description]"
          }},
          "log_analysis_tasks": {{
            "search_terms": ["primary_term", "secondary_term"],
            "time_window": "[if specified]",
            "focus_areas": ["error_patterns", "stack_traces"]
          }},
          "code_analysis_tasks": {{
            "files": ["specific_files_if_mentioned"],
            "functions": ["specific_functions_if_mentioned"],
            "patterns": ["error_patterns_to_look_for"]
          }},
          "investigation_roadmap": {{
            "priority": "[high|medium|low]",
            "next_steps": ["step1", "step2", "step3"]
          }}
        }}

        CRITICAL RULES:
        - ONLY extract information EXPLICITLY mentioned in the user's question
        - NEVER invent or assume file names, function names, or paths
        - If no specific details are mentioned, mark as "not_specified"
        - Be concise, clear, and developer-friendly
        """,
            agent=self.question_analyzer_agent,
            expected_output="Structured JSON with error classification and investigation roadmap",
            max_iter=1,
            async_execution=False,
        )
        
        # Task 2: Log Analyzer - Extract latest relevant error from logs
        log_task = Task(
            description="""
        SYSTEM INSTRUCTION: You are a multi-agent system designed to debug application issues.

        TASK: Analyze logs based on the analysis type from Question Analyzer:
        - For "pattern_analysis": Find common error patterns and frequencies
        - For "recent_search": Extract the latest relevant error
        - For "comprehensive_search": Show all errors with context

        TOOL USAGE STRATEGY (BASED ON ANALYSIS TYPE):
        
        PATTERN ANALYSIS (for "common errors", "frequent errors"):
        1. Use analyze_error_patterns to find common patterns
        2. Use filter_logs for detailed breakdown if needed
        
        RECENT SEARCH (for "latest error", "last error"):
        1. Use grep_logs with search terms (sorted by time)
        2. Use filter_logs for additional context
        3. Use extract_stack_traces if exceptions found
        
        COMPREHENSIVE SEARCH (for "all errors", "show errors"):
        1. Use grep_logs for broad error search
        2. Use filter_logs for error level filtering
        3. Use extract_stack_traces for detailed analysis

        OUTPUT FORMAT (STRUCTURED JSON):
        {
          "log_investigation": {
            "analysis_type": "[pattern_analysis|recent_search|comprehensive_search]",
            "primary_evidence": "[Key findings from log search]",
            "error_patterns": {
              "total_patterns": "[number]",
              "most_common": "[pattern with highest frequency]",
              "frequency_distribution": "[summary of pattern frequencies]"
            },
            "error_timeline": {
              "first_occurrence": "[timestamp]",
              "pattern": "[frequency - single/recurring/periodic]",
              "last_occurrence": "[timestamp]"
            },
            "supporting_evidence": "[Additional context from logs]",
            "code_path": "[extracted file path from stack trace] OR null",
            "function_name": "[extracted function name if available]",
            "line_number": "[extracted line number if available]"
          },
          "config_validation": {
            "code_path_found": true/false,
            "in_config_yaml": true/false,
            "config_issues": ["list of config issues"],
            "config_recommendations": ["list of config fixes"]
          },
          "next_agent": "code_path_analyzer" OR "root_cause_analyzer"
        }

        CRITICAL RULES:
        - If no code_path is found in logs, mark "code_path": null
        - If code_path is null, set next_agent to "root_cause_analyzer"
        - If code_path is found, set next_agent to "code_path_analyzer"
        - Validate code_path against config.yaml if found
        - Be explicit about missing or uncertain data
        """,
            agent=self.log_agent_agent,
            expected_output="Structured JSON with log findings and next agent decision",
            context=[analyze_task],
            max_iter=1,
            async_execution=False,
        )
        
        # Task 3: Code Path Analyzer - Verify code path exists and validate config
        code_path_task = Task(
            description="""
        SYSTEM INSTRUCTION: You are a multi-agent system designed to debug application issues.

        TASK: Given the code_path from log analysis, verify it exists in the project and is reachable. Check config.yaml to see if the code_path or its module is correctly referenced.

        VALIDATION REQUIREMENTS:
        1. Verify file exists on disk
        2. Check if file is within project structure
        3. Validate file is accessible and readable
        4. Check if code_path is properly referenced in config.yaml
        5. If code_path is correct, analyze the file for functions, classes, objects related to the error

        OUTPUT FORMAT (STRUCTURED JSON):
        {
          "validation_result": {
            "exists": true/false,
            "reachable": true/false,
            "accessible": true/false,
            "relevant": true/false,
            "project_root": "/path/to/project",
            "relative_path": "src/actions/file.py",
            "file_size": 1234,
            "last_modified": "2024-01-01T12:00:00Z",
            "language": "python",
            "issues": ["list of validation issues"]
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
          "next_agent": "root_cause_analyzer"
        }

        CRITICAL RULES:
        - If validation fails, provide clear reasons and recommendations
        - If validation succeeds, analyze the file for error-related code
        - Always check config.yaml for proper module references
        - Be explicit about any missing or uncertain data
        """,
            agent=self.code_path_analyzer_agent,
            expected_output="Structured JSON with validation results and code analysis",
            context=[log_task],
            max_iter=1,
            async_execution=False,
        )
        
        # Task 4: Code Analyzer - Analyze specific code for error patterns
        code_task = Task(
            description="""
        SYSTEM INSTRUCTION: You are a multi-agent system designed to debug application issues.

        TASK: Analyze the validated code path for error patterns, functions, classes, and objects related to the error.

        ANALYSIS REQUIREMENTS:
        1. Use find_error_handlers with the validated file path and function_name (use empty string "" if not available)
        2. Analyze error handling patterns in the code
        3. Identify functions and classes related to the error
        4. Find potential root causes in the code

        TOOL USAGE EXAMPLES:
        - If you have a file path: find_error_handlers(file_path="/path/to/file.py", function_name="")
        - If you have both: find_error_handlers(file_path="/path/to/file.py", function_name="function_name")
        - If you have neither: find_error_handlers(file_path="", function_name="")

        OUTPUT FORMAT (STRUCTURED JSON):
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
          }
        }

        CRITICAL RULES:
        - Focus on the specific file path validated by Code Path Analyzer
        - Use find_error_handlers tool with exact file path
        - Provide specific, actionable recommendations
        - Be explicit about any missing or uncertain data
        """,
            agent=self.code_agent_agent,
            expected_output="Structured JSON with code analysis and recommendations",
            context=[code_path_task],
            max_iter=1,
            async_execution=False,
        )
        
        # Task 5: Root Cause Analyzer - Correlate findings and propose fixes
        root_cause_task = Task(
            description="""
        SYSTEM INSTRUCTION: You are a multi-agent system designed to debug application issues.

        TASK: Correlate findings from all previous agents to determine the root cause and propose precise debugging and fix steps.

        SYNTHESIS REQUIREMENTS:
        1. Cross-validate findings from question, log, code path, and code analysis
        2. Determine definitive root cause with confidence level
        3. Create comprehensive solution roadmap
        4. Generate visual flowcharts for documentation
        5. Create copyable error flow chart using create_clean_error_flow tool

        TOOL USAGE:
        - ALWAYS use create_clean_error_flow tool to generate a copyable error flow chart
        - Extract error_type, error_message, components, timeline, severity from previous agents' findings
        - Include the clean mermaid code in flowchart_data.error_flow

        OUTPUT FORMAT (STRUCTURED JSON):
        {
          "root_cause_analysis": {
            "primary_cause": "[definitive technical explanation]",
            "confidence_level": "[high|medium|low]",
            "contributing_factors": ["list of contributing factors"],
            "error_chain": ["sequence of events leading to error"]
          },
          "solution_roadmap": {
            "immediate_fixes": [
              {
                "action": "[specific action]",
                "file": "[file:line reference]",
                "description": "[what to change]"
              }
            ],
            "long_term_improvements": ["list of improvements"],
            "testing_steps": ["how to verify the fix"],
            "rollback_plan": ["how to rollback if needed"]
          },
          "flowchart_data": {
            "error_flow": "[clean mermaid code from create_clean_error_flow tool]"
          }
        }

        CRITICAL RULES:
        - Use EXACT information from previous agents
        - Be concise, clear, and developer-friendly
        - Always recommend actionable next steps
        - Explicitly note missing or uncertain data
        - Generate mermaid diagrams for visual representation
        - ALWAYS include error_flow in flowchart_data using create_clean_error_flow tool
        """,
            agent=self.root_cause_agent_agent,
            expected_output="Structured JSON with root cause analysis, solution roadmap, and flowchart data",
            context=[analyze_task, log_task, code_path_task, code_task],
            max_iter=1,
            async_execution=False,
        )
        
        return [analyze_task, log_task, code_path_task, code_task, root_cause_task] 