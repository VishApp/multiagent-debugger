import os
import re
import subprocess
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path

from crewai import Agent
from crewai.tools import tool
from crewai.tools import BaseTool
from typing import Dict, Any, List, Optional

from multiagent_debugger.utils import get_verbose_flag, create_crewai_llm, get_agent_llm_config
from multiagent_debugger.tools.log_tools import LogAnalyzer, AnalysisMode

# Add this helper function to filter out log files
SOURCE_CODE_EXTENSIONS = [
    '.py', '.go', '.js', '.ts', '.java', '.cpp', '.c', '.rs', '.php', '.rb', '.cs', '.swift', '.kt', '.scala', '.clj', '.hs', '.ml', '.fs', '.vb', '.pl', '.sh', '.sql', '.html', '.css', '.xml', '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf', '.md', '.txt'
]

def is_source_code_file(path: str) -> bool:
    path = path.lower()
    if path.endswith('.log'):
        return False
    for ext in SOURCE_CODE_EXTENSIONS:
        if path.endswith(ext):
            return True
    return False

class LogAgent:
    """Agent that analyzes logs to find relevant information about API failures."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the LogAgent.
        
        Args:
            config: Configuration dictionary with model settings
        """
        self.config = config
        
        # Handle both dict and DebuggerConfig objects
        if hasattr(config, 'llm'):
            self.llm_config = config.llm
        else:
            self.llm_config = config.get("llm", {})
        
        # Get log paths from config
        if hasattr(config, 'log_paths'):
            self.log_paths = config.log_paths
        else:
            self.log_paths = config.get("log_paths", [])
        
        # Get analysis mode and parameters
        self.analysis_mode = AnalysisMode.FREQUENT  # Default to frequent
        
        # Handle both dict and DebuggerConfig objects
        if hasattr(config, 'time_window_hours'):
            self.time_window_hours = config.time_window_hours
        elif hasattr(config, 'get'):
            self.time_window_hours = config.get("time_window_hours", 24)
        else:
            self.time_window_hours = 24
            
        if hasattr(config, 'max_lines'):
            self.max_lines = config.max_lines
        elif hasattr(config, 'get'):
            self.max_lines = config.get("max_lines", 10000)
        else:
            self.max_lines = 10000
        
        # Override with mode if specified
        if hasattr(config, 'analysis_mode'):
            try:
                self.analysis_mode = AnalysisMode(config.analysis_mode)
            except ValueError:
                pass  # Use default
        elif hasattr(config, 'get') and 'analysis_mode' in config:
            try:
                self.analysis_mode = AnalysisMode(config['analysis_mode'])
            except ValueError:
                pass  # Use default
        
    def create_agent(self, tools: List = None) -> Agent:
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
                role="Log Analysis Expert",
                goal="Extract code paths and error patterns from logs for debugging",
                backstory="You are a log analysis expert who extracts code paths, line numbers, and function names from error logs.",
                verbose=verbose,
                allow_delegation=False,
                tools=tools or [],
                llm=llm,
                max_iter=1,
                memory=False,
                instructions="""
                Extract code paths and error information from logs:
                
                1. Code path extraction from stack traces and error messages
                2. Line number and function name identification
                3. Error pattern analysis and timeline
                4. Decision on whether code analysis is needed
                
                OUTPUT FORMAT (JSON):
                {
                  "log_analysis": {
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
                    "supporting_evidence": "[Additional context from filter_logs]"
                  },
                  "code_path_extraction": {
                    "extracted_code_paths": [
                      {
                        "file_path": "/full/path/to/file.ext",
                        "line_number": 123,
                        "function_name": "function_name",
                        "error_context": "[error message or stack trace line]",
                        "timestamp": "[when this error occurred]",
                        "confidence": "[high|medium|low]"
                      }
                    ],
                    "most_recent_error": {
                      "file_path": "/path/to/most/recent/file.ext",
                      "line_number": 456,
                      "function_name": "recent_function",
                      "error_message": "[the actual error message]",
                      "timestamp": "[most recent timestamp]"
                    },
                    "extraction_quality": "[high|medium|low] - based on clarity of stack traces"
                  },
                  "code_analysis_decision": {
                    "should_analyze_code": true/false,
                    "reason": "[why code analysis is needed or not]",
                    "target_file": "/path/to/analyze.ext",
                    "target_line": 123,
                    "target_function": "function_name",
                    "code_path": "/directory/containing/the/file"
                  }
                }
                
                DECISION LOGIC:
                - If code paths found: set should_analyze_code = true and provide code_path
                - If no code paths found: set should_analyze_code = false
                - The code_path should be the directory containing the target file
                
                RULES:
                - CRITICAL: If no errors are found in logs, return should_analyze_code = false and explain why
                - NEVER fabricate or hallucinate error data if logs are empty or contain no errors
                - Extract source code file paths from log content, not log file names
                - Look for stack traces with file paths and line numbers
                - Prioritize the most recent error for analysis
                - Be explicit about missing or uncertain data
                - If logs exist but contain no errors, state this clearly in the reason field
                """
            )
            return agent
        except Exception as e:
            import traceback
            print(f"ERROR: Failed to create CrewAI Agent: {e}")
            print(traceback.format_exc())
            raise
    
    def scan_logs(self, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Scan logs for entries matching the provided entities.
        
        Args:
            entities: Dictionary of entities extracted from the user's question
            
        Returns:
            Dict containing relevant log entries and analysis
        """
        results = {
            "matching_logs": [],
            "error_logs": [],
            "stack_traces": [],
            "summary": ""
        }
        
        if not self.log_paths:
            results["summary"] = "No log paths provided."
            return results
    
    def extract_code_paths(self) -> dict:
        """
        Extract code paths and line numbers from log content using intelligent analysis.
        Returns a dict suitable for the code_path_extraction section with smart routing.
        """
        analyzer = LogAnalyzer(
            self.log_paths, 
            mode=self.analysis_mode,
            time_window_hours=self.time_window_hours,
            max_lines=self.max_lines
        )
        
        # Use intelligent analysis
        analysis = analyzer.analyze_errors_intelligent()
        
        # CRITICAL: Check if any errors were actually found
        if analysis['total_errors'] == 0:
            return {
                "extracted_code_paths": [],
                "most_recent_error": {},
                "extraction_quality": "no_errors_found",
                "analysis_summary": {
                    "total_errors": 0,
                    "unique_patterns": 0,
                    "latest_unique_errors": 0,
                    "time_window_hours": analysis['time_window_hours'],
                    "analysis_mode": analysis['analysis_mode'],
                    "message": "No errors found in log files - nothing to analyze"
                }
            }
        
        # Extract code paths from patterns and latest errors
        extracted_code_paths = []
        most_recent_error = {}
        
        # Process patterns (frequent errors)
        for pattern in analysis['patterns']:
            if pattern.signature.code_path:
                extracted_code_paths.append({
                    "file_path": pattern.signature.code_path,
                    "line_number": pattern.signature.line_number,
                    "function_name": pattern.signature.function_name,
                    "error_context": pattern.pattern,
                    "timestamp": pattern.last_occurrence.isoformat() if pattern.last_occurrence else None,
                    "confidence": "high",
                    "frequency": pattern.count,
                    "frequency_score": pattern.frequency_score
                })
        
        # Process latest unique errors (new/critical errors)
        for error in analysis['latest_unique_errors']:
            if error.error_signature and error.error_signature.code_path:
                # Check if this code path is already in extracted_code_paths
                existing = any(cp["file_path"] == error.error_signature.code_path for cp in extracted_code_paths)
                if not existing:
                    extracted_code_paths.append({
                        "file_path": error.error_signature.code_path,
                        "line_number": error.error_signature.line_number,
                        "function_name": error.error_signature.function_name,
                        "error_context": error.message,
                        "timestamp": error.timestamp.isoformat() if error.timestamp else None,
                        "confidence": "high",
                        "frequency": 1,
                        "frequency_score": 0.1  # Lower score for new errors
                    })
        
        # Set most recent error for routing
        if extracted_code_paths:
            # Sort by frequency score and timestamp
            extracted_code_paths.sort(key=lambda x: (x.get('frequency_score', 0), x.get('timestamp', '')), reverse=True)
            most_recent = extracted_code_paths[0]
            most_recent_error = {
                "file_path": most_recent["file_path"],
                "line_number": most_recent["line_number"],
                "function_name": most_recent["function_name"],
                "error_message": most_recent["error_context"],
                "timestamp": most_recent["timestamp"]
            }
        
        return {
            "extracted_code_paths": extracted_code_paths,
            "most_recent_error": most_recent_error,
            "extraction_quality": "high" if extracted_code_paths else "low",
            "analysis_summary": {
                "total_errors": analysis['total_errors'],
                "unique_patterns": len(analysis['patterns']),
                "latest_unique_errors": len(analysis['latest_unique_errors']),
                "time_window_hours": analysis['time_window_hours'],
                "analysis_mode": analysis['analysis_mode']
            }
        }

    def validate_code_path_in_config(self, code_path: str) -> Dict[str, Any]:
        """Check if the code path is properly listed in config.yaml.
        
        Args:
            code_path: The code path to validate
            
        Returns:
            Dict containing config validation results
        """
        result = {
            "code_path_found": False,
            "in_config_yaml": False,
            "config_issues": [],
            "config_recommendations": []
        }
        
        if not code_path or code_path == "None":
            result["config_issues"].append("No code path provided for validation")
            return result
        
        result["code_path_found"] = True
        
        # Look for config.yaml files in the project
        config_files = []
        # Note: We no longer use hardcoded code_path since we extract it from logs
        # The code path validation is now handled dynamically based on log extraction
        
        return {
            "config_files_found": config_files,
            "validation_status": "dynamic_extraction_enabled"
        }
        
        for log_path in self.log_paths:
            if not os.path.exists(log_path):
                continue
                
            # Build grep command based on entities
            grep_cmd = ["grep", "-i"]
            
            # Add time filter if available
            time_window = entities.get("time_window", {})
            time_filter = ""
            if time_window.get("start") and time_window.get("end"):
                # This is a simplification; actual implementation would depend on log format
                start_date = datetime.fromisoformat(time_window["start"]).strftime("%Y-%m-%d")
                end_date = datetime.fromisoformat(time_window["end"]).strftime("%Y-%m-%d")
                time_filter = f"{start_date}|{end_date}"
                if time_filter:
                    grep_cmd.extend(["-E", time_filter])
            
            # Add user ID filter if available
            user_id = entities.get("user_id")
            if user_id:
                grep_cmd.extend(["-e", user_id])
            
            # Add API route filter if available
            api_route = entities.get("api_route")
            if api_route:
                # Escape special characters in the API route
                escaped_route = re.escape(api_route)
                grep_cmd.extend(["-e", escaped_route])
            
            # Add error filter
            grep_cmd.extend(["-e", "ERROR", "-e", "WARN", "-e", "Exception", "-e", "fail", "-e", "error"])
            
            # Add log path
            grep_cmd.append(log_path)
            
            try:
                # Execute grep command
                process = subprocess.run(grep_cmd, capture_output=True, text=True)
                if process.returncode == 0 and process.stdout:
                    # Process and categorize log entries
                    log_entries = process.stdout.strip().split('\n')
                    for entry in log_entries:
                        results["matching_logs"].append(entry)
                        if any(error_term in entry.lower() for error_term in ["error", "exception", "fail", "warn"]):
                            results["error_logs"].append(entry)
                        if "stack trace" in entry.lower() or "traceback" in entry.lower():
                            # Collect stack trace (this is simplified)
                            results["stack_traces"].append(entry)
            except Exception as e:
                print(f"Error scanning log {log_path}: {str(e)}")
        
        # Generate summary
        results["summary"] = f"Found {len(results['matching_logs'])} matching log entries, " \
                            f"{len(results['error_logs'])} error logs, and " \
                            f"{len(results['stack_traces'])} stack traces."
        
        return results 