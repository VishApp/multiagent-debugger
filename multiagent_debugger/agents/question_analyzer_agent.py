from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import re
import os

from crewai import Agent
from crewai.tools import tool
from crewai.tools import BaseTool

from multiagent_debugger.utils import get_verbose_flag, create_crewai_llm, get_agent_llm_config

class QuestionAnalyzerAgent:
    """Agent that analyzes the user's question to extract relevant entities."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the QuestionAnalyzerAgent.
        
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
        provider, model, temperature, api_key, api_base = get_agent_llm_config(self.llm_config)
        verbose = get_verbose_flag(self.config)
        # Create LLM
        llm = create_crewai_llm(provider, model, temperature, api_key, api_base)
        
        # Debug: Print LLM info
        print(f"DEBUG: Using {provider} LLM: {model} with temperature {temperature}")
        
        try:
            agent = Agent(
        role="Error Pattern Detective & Creative Classifier",
        goal="Transform user questions into engaging detective cases with creative error classification and investigation roadmaps",
        backstory="You are a brilliant detective with a flair for creative problem-solving. You see every error as a mystery waiting to be solved, and you love creating engaging narratives around technical problems. You think like a crime scene investigator who can spot the smallest clues and turn them into compelling stories.",
                verbose=verbose,
                allow_delegation=False,
                tools=tools or [],
                llm=llm,
                max_iter=1,  # Reduced from 3 to 1 for efficiency
                memory=False,  # Disable individual agent memory, use crew-level memory instead
                instructions="""
        RAPID ERROR CLASSIFICATION & CREATIVE CASE BUILDING:
        
        🕵️ DETECTIVE CASE APPROACH:
        Transform every error into an engaging detective case with:
        - 🎭 Creative case titles and descriptions
        - 🎯 Engaging investigation roadmaps
        - 🎨 Visual metaphors for error types
        - 🎪 Compelling problem narratives
        
        From the input error, extract these key elements for the next agents:
        
        1. 🎭 CASE THEME: [Creative theme for the debugging story]
        2. 🕵️ ERROR CATEGORY: [API|Database|File|Network|Script|OS|Memory|Auth|Config]
        3. 🎯 SEVERITY: [P0-Critical|P1-Urgent|P2-High|P3-Medium]
        4. 🔍 SEARCH STRATEGY: [Specific terms for log search]
        5. 🗺️ CODE FOCUS: [File/function names mentioned in error]
        6. ⏰ TIME CONTEXT: [When did this happen - recent, ongoing, specific time]
        
        📋 CREATIVE OUTPUT TEMPLATE (STRUCTURED JSON WITH STORYTELLING):
        
        {
          "detective_case": {
            "case_title": "[Creative case title]",
            "mystery_description": "[Engaging problem description]",
            "crime_scene": "[Where the error occurred]",
            "victim": "[What system/feature is affected]",
            "suspects": ["[Potential causes with creative names]"]
          },
          "error_classification": {
            "type": "[API|Database|File|Network|Script|OS|Memory|Auth|Config]",
            "severity": "[P0-Critical|P1-Urgent|P2-High|P3-Medium]",
            "description": "[Brief error description with creative language]",
            "metaphor": "[Creative metaphor for this error type]"
          },
          "log_analysis_tasks": {
            "analysis_type": "[pattern_analysis|recent_search|comprehensive_search]",
            "search_terms": ["primary_term", "secondary_term"],
            "time_window": "[if specified]",
            "focus_areas": ["error_patterns", "stack_traces"],
            "investigation_style": "[detective approach for log analysis]"
          },
          "code_analysis_tasks": {
            "files": ["specific_files_if_mentioned"],
            "functions": ["specific_functions_if_mentioned"],
            "patterns": ["error_patterns_to_look_for"],
            "archaeological_sites": ["[Creative names for code areas to explore]"]
          },
          "investigation_roadmap": {
            "priority": "[high|medium|low]",
            "next_steps": ["step1", "step2", "step3"],
            "story_arc": "[Beginning, middle, end of the investigation]",
            "creative_theme": "[Visual theme for the debugging journey]"
          }
        }
        
        CRITICAL RULES - STRICT ENFORCEMENT:
        - NEVER use example file names like "base_tm_action.py", "dataProcessor.js", "/src/utils/dataProcessor.js", etc.
        - NEVER invent or assume file paths that are not explicitly mentioned in the user's error
        - ONLY extract information that is EXPLICITLY present in the user's error/question
        - If no specific files are mentioned, use empty array: "files": []
        - If no specific functions are mentioned, use empty array: "functions": []
        - If no specific error message is provided, use "description": "No specific error message provided"
        - Always work with the EXACT error text provided by the user, nothing more
        - DO NOT make assumptions about file locations or function names
        - DO NOT use common patterns or examples - only real data from the user
        
        STACK TRACE EXTRACTION:
        - When analyzing JSON logs, look for "stack_trace" fields
        - Extract file paths from stack trace lines like "File '/path/to/file.ext', line X"
        - Look for patterns in "exc_info" fields that contain stack traces
        - Pay attention to "Traceback" sections in log entries
        - Extract ALL file paths mentioned in stack traces, not just the first one
        
        FILE PATH EXTRACTION RULES:
        - Look for patterns like "File \"path/to/file.ext\", line X" or "in file path/to/file.ext"
        - Look for stack traces with patterns like "File \"/full/path/to/file.ext\", line X"
        - Look for patterns in JSON logs: "File \"/path/to/file.ext\", line X"
        - Support ALL programming languages: .py, .js, .ts, .java, .cpp, .c, .go, .rs, .php, .rb, .cs, .swift, .kt, .scala, .clj, .hs, .ml, .fs, .vb, .pl, .sh, .sql, .html, .css, .xml, .json, .yaml, .yml, .toml, .ini, .cfg, .conf, .md, .txt
        - Extract the COMPLETE file path including directory structure
        - If a file path is found, include it EXACTLY as written in the error
        - Do not modify, shorten, or change the file path in any way
        - If multiple files are mentioned, list all of them
        - Pay special attention to stack traces in log entries
        - Look for file paths in both simple error messages and complex JSON log structures
        
        QUERY TYPE DETECTION:
        - When users ask for "common errors", "frequent errors", "error patterns", "most common errors":
          * Set analysis_type to "pattern_analysis"
          * Set focus_areas to ["error_patterns"]
          * Use search_terms like ["error", "exception", "failed"]
          * This triggers the analyze_error_patterns tool instead of grep_logs
        - When users ask for "latest error", "last error", "recent error":
          * Set analysis_type to "recent_search"
          * Use specific error terms from the question
        - When users ask for "all errors", "show errors":
          * Set analysis_type to "comprehensive_search"
          * Use broad search terms
        
        LANGUAGE-AGNOSTIC ERROR PATTERNS:
        - API Errors: HTTP status codes, endpoint failures, request/response issues
        - Database Errors: Connection failures, query errors, constraint violations
        - File Errors: File not found, permission denied, I/O errors
        - Network Errors: Connection timeouts, DNS failures, SSL issues
        - Script Errors: Runtime exceptions, syntax errors, missing dependencies
        - OS Errors: System resource issues, permission problems
        - Memory Errors: Out of memory, memory leaks, allocation failures
        - Auth Errors: Authentication failures, authorization issues, token problems
        - Config Errors: Configuration parsing, missing settings, invalid values
        
        EXAMPLE OUTPUT (using real data only):
        {
          "error_classification": {
            "type": "[Based on actual error type in user's question]",
            "severity": "[Based on actual impact described]",
            "description": "[Exact error message from user's question]"
          },
          "log_analysis_tasks": {
            "search_terms": ["[Exact terms from the error message]"],
            "time_window": "[Only if time is mentioned in the error]",
            "focus_areas": ["error_patterns", "stack_traces"]
          },
          "code_analysis_tasks": {
            "files": ["[Only files actually mentioned in the error]"],
            "functions": ["[Only functions actually mentioned in the error]"],
            "patterns": ["[Real error patterns from the error]"]
          },
          "investigation_roadmap": {
            "priority": "[high|medium|low]",
            "next_steps": ["Analyze logs for error patterns", "Validate code paths", "Determine root cause"]
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
    
    def parse_question(self, question: str) -> Dict[str, Any]:
        """Parse the user's question to extract entities.
        
        Args:
            question: User's natural language question
            
        Returns:
            Dict containing extracted entities (API route, user ID, time window, etc.)
        """
        # This would be implemented as a task for the agent
        # For now, we'll provide a simple implementation
        entities = {
            "api_route": None,
            "user_id": None,
            "time_window": {
                "start": None,
                "end": None
            },
            "error_type": None
        }
        
        # Extract API route (simple pattern matching for now)
        if "/" in question:
            import re
            api_routes = re.findall(r'/\w+(?:/\w+)*', question)
            if api_routes:
                entities["api_route"] = api_routes[0]
        
        # Extract user ID (simple pattern matching for now)
        user_match = re.search(r'user (\d+)', question)
        if user_match:
            entities["user_id"] = user_match.group(1)
        
        # Extract time window (simple pattern matching for now)
        if "yesterday" in question.lower():
            today = datetime.now()
            yesterday = today - timedelta(days=1)
            entities["time_window"]["start"] = yesterday.replace(hour=0, minute=0, second=0).isoformat()
            entities["time_window"]["end"] = yesterday.replace(hour=23, minute=59, second=59).isoformat()
        elif "today" in question.lower():
            today = datetime.now()
            entities["time_window"]["start"] = today.replace(hour=0, minute=0, second=0).isoformat()
            entities["time_window"]["end"] = today.replace(hour=23, minute=59, second=59).isoformat()
        
        return entities 