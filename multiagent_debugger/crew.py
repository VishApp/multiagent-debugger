import os
import re
from typing import Dict, Any, List, Optional

from crewai import Crew, Task, Agent, Process
from crewai.tools import tool

from multiagent_debugger.agents.question_analyzer_agent import QuestionAnalyzerAgent
from multiagent_debugger.agents.log_agent import LogAgent
from multiagent_debugger.agents.code_agent import CodeAgent
from multiagent_debugger.agents.root_cause_agent import RootCauseAgent

from multiagent_debugger.tools.log_tools import create_enhanced_grep_logs_tool, create_enhanced_filter_logs_tool, create_enhanced_extract_stack_traces_tool, create_error_pattern_analysis_tool, create_intelligent_error_analysis_tool
from multiagent_debugger.tools.code_tools import create_find_api_handlers_tool, create_find_dependencies_tool, create_find_error_handlers_tool, create_directory_language_analyzer_tool, create_smart_multilang_search_tool, create_error_pattern_analyzer_tool
from multiagent_debugger.tools.flowchart_tool import create_error_flowchart_tool, create_system_flowchart_tool, create_decision_flowchart_tool, create_sequence_flowchart_tool, create_debugging_storyboard_tool, create_clean_mermaid_tool, create_comprehensive_debugging_flowchart_tool
from multiagent_debugger.utils import set_crewai_env_vars, get_env_var_name_for_provider, get_verbose_flag

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
        self.code_agent = CodeAgent(config)
        self.root_cause_agent = RootCauseAgent(config)
        
        # Initialize tools
        self.log_tools = self._create_log_tools()
        self.code_tools = self._create_code_tools()
        self.flowchart_tools = self._create_flowchart_tools()
        
        # Create CrewAI agents with retry configuration
        self.question_analyzer_agent = self.question_analyzer.create_agent()
        self.log_agent_agent = self.log_agent.create_agent(tools=self.log_tools + self.flowchart_tools)
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
        # Create agent config dict for tools with proper defaults
        agent_config = {
            'analysis_mode': getattr(self.config, 'analysis_mode', 'frequent'),
            'time_window_hours': getattr(self.config, 'time_window_hours', 24),
            'max_lines': getattr(self.config, 'max_lines', 10000)
        }
        
        return [
            create_intelligent_error_analysis_tool(self.log_paths, agent_config),  # Primary tool
            create_enhanced_grep_logs_tool(self.log_paths, agent_config),          # Fallback
            create_enhanced_filter_logs_tool(self.log_paths, agent_config),        # Fallback
            create_enhanced_extract_stack_traces_tool(self.log_paths, agent_config), # Fallback
            create_error_pattern_analysis_tool(self.log_paths, agent_config),      # Fallback
        ]
    
    def _create_code_tools(self) -> List:
        """Create code analysis tools."""
        return [
            create_find_api_handlers_tool(""),  # Will be set dynamically based on log extraction
            create_find_dependencies_tool(""),  # Will be set dynamically based on log extraction
            create_find_error_handlers_tool(""),  # Will be set dynamically based on log extraction
            create_directory_language_analyzer_tool(""),  # Will be set dynamically based on log extraction
            create_smart_multilang_search_tool(""),  # Will be set dynamically based on log extraction
            create_error_pattern_analyzer_tool(""),  # Will be set dynamically based on log extraction
        ]
    
    def _create_crew(self) -> Crew:
        """Create and return a CrewAI crew.
        
        Returns:
            Crew: The configured CrewAI crew
        """
        # Get provider info for memory configuration
        if hasattr(self.config, 'llm'):
            provider = self.config.llm.provider.lower()
        elif isinstance(self.config, dict):
            provider = self.config.get("llm", {}).get("provider", "openai").lower()
        else:
            provider = "openai"
        
        # Get verbose flag from config
        verbose = get_verbose_flag(self.config)
        
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
                self.code_agent_agent,
                self.root_cause_agent_agent
            ],
            tasks=self._create_tasks(""),  # Placeholder, will be replaced in debug()
            verbose=verbose,
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
        
        if issues:
            return f"""
🚨 CONFIGURATION VALIDATION FAILED

The following issues prevent debugging from proceeding:

{chr(10).join(issues)}

📋 REQUIRED ACTIONS:
1. Update your config.yaml with valid log paths
2. Ensure log files exist and are readable
3. Run the debugger again

Example valid configuration:
```yaml
log_paths:
  - /var/log/myapp/app.log
  - /var/log/nginx/access.log
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
        """Create tasks for the crew based on the question.
        
        Args:
            question: The debugging question to answer
            
        Returns:
            List of tasks for the crew
        """
        from crewai import Task
        
        # Task 1: Question Analysis
        question_task = Task(
            description=f"""
            SYSTEM INSTRUCTION: You are a multi-agent system designed to debug application issues.
            
            TASK: Break the user's question into clear tasks for log agent, code agent, and root cause agent.
            
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
            expected_output="Structured JSON with error classification and analysis tasks"
        )
        
        # Task 2: Log Analysis with Code Path Extraction
        log_task = Task(
            description=f"""
            SYSTEM INSTRUCTION: You are a log analysis agent that extracts code paths and line numbers from error logs.
            
            TASK: Analyze logs to extract code paths, line numbers, and function names for code analysis.
            
            USER QUESTION: '{question}'
            
            CRITICAL EXTRACTION TASKS:
            1. Extract code paths from stack traces and error messages
            2. Identify line numbers where errors occurred
            3. Extract function names from error context
            4. Determine the most recent error occurrence
            
            OUTPUT FORMAT (STRUCTURED JSON):
            {{
              "log_analysis": {{
                "analysis_type": "[pattern_analysis|recent_search|comprehensive_search]",
                "primary_evidence": "[Key findings from log search]",
                "error_patterns": {{
                  "total_patterns": "[number]",
                  "most_common": "[pattern with highest frequency]",
                  "frequency_distribution": "[summary of pattern frequencies]"
                }},
                "error_timeline": {{
                  "first_occurrence": "[timestamp]",
                  "pattern": "[frequency - single/recurring/periodic]",
                  "last_occurrence": "[timestamp]"
                }},
                "supporting_evidence": "[Additional context from filter_logs]"
              }},
              "code_path_extraction": {{
                "extracted_code_paths": [
                  {{
                    "file_path": "/full/path/to/file.ext",
                    "line_number": 123,
                    "function_name": "function_name",
                    "error_context": "[error message or stack trace line]",
                    "timestamp": "[when this error occurred]",
                    "confidence": "[high|medium|low]"
                  }}
                ],
                "most_recent_error": {{
                  "file_path": "/path/to/most/recent/file.ext",
                  "line_number": 456,
                  "function_name": "recent_function",
                  "error_message": "[the actual error message]",
                  "timestamp": "[most recent timestamp]"
                }},
                "extraction_quality": "[high|medium|low] - based on clarity of stack traces"
              }},
              "code_analysis_decision": {{
                "should_analyze_code": true/false,
                "reason": "[why code analysis is needed or not]",
                "target_file": "/path/to/analyze.ext",
                "target_line": 123,
                "target_function": "function_name",
                "code_path": "/directory/containing/the/file"
              }}
            }}
            
            DECISION LOGIC:
            - If code paths found: set should_analyze_code = true and provide code_path
            - If no code paths found: set should_analyze_code = false
            - The code_path should be the directory containing the target file
            """,
            agent=self.log_agent_agent,
            expected_output="Structured JSON with log analysis and code analysis decision",
            context=[question_task]
        )
        
        # Task 3: Conditional Code Analysis (only if code paths found)
        code_task = Task(
            description=f"""
            SYSTEM INSTRUCTION: You are a targeted code analysis agent that analyzes specific files and line numbers.
            
            TASK: Analyze the specific file and line number extracted from logs to identify the root cause.
            
            CONTEXT: Use the code_analysis_decision from the log agent to determine what to analyze.
            
            CRITICAL: You MUST use the exact file paths and line numbers extracted by the log agent.
            The log agent provides extracted_code_paths with file_path, line_number, and function_name.
            Use these exact values in your analysis and file references.
            
            ANALYSIS FOCUS:
            1. Analyze the target file and line number from log extraction
            2. Examine the function containing the error line
            3. Identify potential null/undefined access, type mismatches, etc.
            4. Provide specific fixes with line references
            
            CRITICAL: Use the code_path parameter in all code analysis tools. The log agent extracts this from stack traces.
            
            TOOL USAGE GUIDE:
            - Use find_error_handlers to analyze error handling in the target file
            - Use find_dependencies to analyze function dependencies
            - Use smart_multilang_search to search for specific error patterns
            - Use directory_language_analyzer for broader code analysis
            - DO NOT use find_api_handlers for file analysis (it's for API routes only)
            
            OUTPUT FORMAT (STRUCTURED JSON):
            {{
              "validation": {{
                "is_log_file": true/false,
                "should_analyze": true/false,
                "reason": "[why analysis should/should not proceed]"
              }},
              "targeted_analysis": {{
                "target_file": "/path/to/analyzed/file.ext",
                "target_line": 123,
                "target_function": "function_name",
                "file_exists": true/false,
                "file_accessible": true/false,
                "analysis_quality": "[high|medium|low]"
              }},
              "line_analysis": {{
                "error_line_code": "[actual code at the error line]",
                "error_line_context": "[context around the error line]",
                "potential_issues": [
                  {{
                    "issue_type": "[null_access|type_error|logic_error|etc]",
                    "description": "[specific issue description]",
                    "line_number": 123,
                    "confidence": "[high|medium|low]"
                  }}
                ]
              }},
              "function_analysis": {{
                "function_name": "function_name",
                "function_signature": "def function_name(param1, param2):",
                "parameters": ["param1", "param2"],
                "return_type": "[expected return type]",
                "error_handling": "[present|missing|inadequate]",
                "validation_logic": "[present|missing|inadequate]"
              }},
              "code_issues": {{
                "immediate_fixes": [
                  {{
                    "action": "[specific fix action]",
                    "line_number": 123,
                    "description": "[what to change]",
                    "impact": "[what this fix will solve]"
                  }}
                ]
              }},
              "analysis_summary": {{
                "root_cause": "[definitive cause of the error]",
                "confidence_level": "[high|medium|low]",
                "evidence_quality": "[strong|medium|weak]",
                "fix_complexity": "[simple|moderate|complex]"
              }}
            }}
            
            CRITICAL RULES:
            - Focus on the specific file and line from log extraction
            - Provide actionable fixes with exact line references
            - If file doesn't exist, report file_exists: false
            - ALWAYS use the exact file paths from the log agent's extracted_code_paths
            - NEVER reference log files (.log files) in your analysis
            - Always pass the extracted code_path to code analysis tools
            - MUST analyze the actual code in the extracted files using appropriate tools
            - Use find_error_handlers with the extracted file_path to examine error handling
            - Use find_dependencies with the extracted file_path to understand dependencies
            - CRITICAL: If the target_file ends with .log or contains /logs/, DO NOT analyze it
            - CRITICAL: If the target_file is a log file, report "No source code files found for analysis"
            - CRITICAL: Only analyze actual source code files (.go, .py, .js, etc.), never log files
            """,
            agent=self.code_agent_agent,
            expected_output="Structured JSON with targeted code analysis",
            context=[question_task, log_task]
        )
        
        # Task 4: Root Cause Analysis (final synthesis)
        root_cause_task = Task(
            description=f"""
            SYSTEM INSTRUCTION: You are a root cause analysis agent that synthesizes findings into actionable solutions.
            
            TASK: Synthesize findings from all previous agents to determine the root cause and provide solutions.
            
            CONTEXT: Use results from question analysis, log analysis, and code analysis (if available).
            
            SYNTHESIS PROCESS:
            1. Combine findings from all agents
            2. Determine the definitive root cause
            3. Create actionable solutions
            4. Generate visual flowcharts
            
            OUTPUT FORMAT (STRUCTURED JSON):
            {{
              "root_cause_analysis": {{
                "primary_cause": "[definitive technical explanation]",
                "confidence_level": "[high|medium|low]",
                "contributing_factors": ["list of contributing factors"],
                "error_chain": ["sequence of events"]
              }},
              "solution_roadmap": {{
                "immediate_fixes": [
                  {{
                    "action": "[specific action]",
                    "file": "[file:line reference]",
                    "description": "[what to change]",
                    "impact": "[what this will solve]"
                  }}
                ],
                "long_term_improvements": ["list of improvements"],
                "testing_steps": ["how to test the fixes"],
                "rollback_plan": ["how to rollback if needed"]
              }},
              "flowchart_data": {{
                "error_flow": "[clean mermaid code from create_clean_error_flow or create_minimal_error_flow tool]",
                "flowchart_style": "[clean|minimal]"
              }},
              "synthesis_summary": {{
                "classification": "[Error type]",
                "evidence_quality": "[Strong/Medium/Weak]",
                "consistency": "[High/Medium/Low across all agents]"
              }}
            }}
            
            CRITICAL RULES:
            - Use EXACT information from previous agents
            - Generate clean, minimal mermaid diagrams
            - Provide actionable next steps
            - Be explicit about missing or uncertain data
            - ALWAYS use the exact file paths from the code analysis agent
            - NEVER reference log files (.log files) in your solutions
            - Use the target_file and target_line from the code analysis for file references
            """,
            agent=self.root_cause_agent_agent,
            expected_output="Structured JSON with root cause analysis and solutions",
            context=[question_task, log_task, code_task]
        )
        
        return [question_task, log_task, code_task, root_cause_task] 