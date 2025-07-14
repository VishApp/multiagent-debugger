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
        
        # Get code path from config for validation
        if hasattr(config, 'code_path'):
            self.code_path = config.code_path
        else:
            self.code_path = config.get("code_path", "")
        
    def create_agent(self, tools: List = None) -> Agent:
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
        role="Digital Forensics Expert & Log Storyteller",
        goal="Transform log analysis into compelling digital detective work with creative evidence presentation",
        backstory="You are a digital forensics expert who treats log files like crime scene evidence. You love uncovering hidden patterns and telling the story of what happened through creative log analysis. You think like a cyber detective who can read between the lines of log entries and find the smoking gun in the digital evidence.",
                verbose=verbose,
                allow_delegation=False,
                tools=tools or [],
                llm=llm,  # Pass the CrewAI LLM object
                max_iter=1,  # Reduced from 3 to 1 for efficiency
                memory=False,  # Disable individual agent memory, use crew-level memory instead
                instructions="""
        EFFICIENT LOG INVESTIGATION (MAX 3 TOOL CALLS):
        
        Use the search strategy from Question Analyzer to target your investigation.
        
        TOOL USAGE STRATEGY (BASED ON ANALYSIS TYPE):
        
        PATTERN ANALYSIS (for "common errors", "frequent errors"):
        STEP 1: ERROR PATTERN ANALYSIS
        ✅ analyze_error_patterns([time_window_hours])
        Example: analyze_error_patterns(24)
        
        STEP 2: DETAILED PATTERN BREAKDOWN (if patterns found)
        ✅ filter_logs("ERROR", [time_hours], "")
        Example: filter_logs("ERROR", 24, "")
        
        RECENT SEARCH (for "latest error", "last error"):
        STEP 1: PRIMARY EVIDENCE SEARCH
        ✅ grep_logs("[primary_search_term]", 2, false, false, [time_hours], true)
        Example: grep_logs("Invalid token", 2, false, false, 24, true)
        
        STEP 2: DETAILED ANALYSIS (Only if Step 1 found evidence)
        ✅ filter_logs("[error_level]", [time_hours], "")
        Example: filter_logs("ERROR", 4, "")
        
        COMPREHENSIVE SEARCH (for "all errors", "show errors"):
        STEP 1: BROAD ERROR SEARCH
        ✅ grep_logs("error", 2, false, false, [time_hours], true)
        
        STEP 2: ERROR LEVEL FILTERING
        ✅ filter_logs("ERROR", [time_hours], "")
        
        STEP 3: STACK TRACE EXTRACTION (if exceptions found)
        ✅ extract_stack_traces("[exception_type]")
        Example: extract_stack_traces("RuntimeError")
        
        EFFICIENCY RULES:
        - If grep_logs returns "No matches found" → try secondary search term once, then stop
        - If filter_logs fails → skip and continue with available info
        - Always provide analysis even if tools return limited results
        
        📋 OUTPUT TEMPLATE (STRUCTURED JSON):
        
        {
          "log_investigation": {
            "analysis_type": "[pattern_analysis|recent_search|comprehensive_search]",
            "primary_evidence": "[Key findings from tool search]",
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
            "supporting_evidence": "[Additional context from filter_logs or stack traces]",
            "code_path": "[extracted file path from stack trace or error message] OR null",
            "function_name": "[extracted function name if available]",
            "line_number": "[extracted line number if available]"
          },
          "config_validation": {
            "code_path_found": true/false,
            "in_config_yaml": true/false,
            "config_issues": [
              "Missing import in config.yaml",
              "Incorrect path reference",
              "Disabled module"
            ],
            "config_recommendations": [
              "Add module to config.yaml",
              "Update path reference",
              "Enable module in config"
            ]
          },
          "next_agent": "code_path_analyzer" OR "root_cause_analyzer"
        }
        
        CONDITIONAL FLOW LOGIC:
        - If code_path is found in logs (not null), set next_agent to "code_path_analyzer"
        - If code_path is null or not found, set next_agent to "root_cause_analyzer"
        - This determines which agent will be called next in the flow
        
        CONFIG VALIDATION INSTRUCTIONS:
        After extracting the code_path from logs, check if it's properly listed in config.yaml:
        1. Look for config.yaml files in the project root (self.config.code_path)
        2. Check if the code_path (or its module) is referenced in config
        3. Report any missing imports or configuration issues
        4. Provide specific recommendations for fixing config issues
        
        CONFIG CHECK PROCESS:
        - If you find a code_path in the logs, validate it against config.yaml
        - Check if the module/file is properly imported or referenced
        - Look for patterns like: imports, modules, paths, actions, cron jobs
        - If not found, suggest adding it to config.yaml
        - If found but disabled, suggest enabling it
        
        CRITICAL RULES:
        - NEVER use example file names like "dataProcessor.js", "base_tm_action.py", etc.
        - ONLY report files and functions that actually appear in your log search results
        - If no specific files are found, set code_path to null
        - If grep_logs returns "No matches found", report that truthfully
        - Always use real data from your actual log files, never example data
        - Always provide structured JSON output
        - Be explicit about missing or uncertain data
        
        EXAMPLE OUTPUT (using real data only):
        {
          "log_investigation": {
            "primary_evidence": "[Report actual findings from grep_logs - if no matches, say 'No matches found']",
            "error_timeline": {
              "first_occurrence": "[Use actual timestamps from your logs, or 'Timeline not available']",
              "pattern": "[single/recurring/periodic]",
              "last_occurrence": "[Use actual timestamps from your logs, or 'Timeline not available']"
            },
            "supporting_evidence": "[Real evidence from your logs]",
            "code_path": "[Only if actually found in logs, otherwise null]",
            "function_name": "[Only if actually found in logs, otherwise null]",
            "line_number": "[Only if actually found in logs, otherwise null]"
          },
          "config_validation": {
            "code_path_found": true/false,
            "in_config_yaml": true/false,
            "config_issues": ["Real config issues found"],
            "config_recommendations": ["Real config fixes needed"]
          },
          "next_agent": "code_path_analyzer" OR "root_cause_analyzer"
        }
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
        if self.code_path:
            project_root = Path(self.code_path)
            config_patterns = ["config.yaml", "config.yml", "app.yaml", "app.yml", "settings.yaml", "settings.yml"]
            
            for pattern in config_patterns:
                config_files.extend(project_root.rglob(pattern))
        
        if not config_files:
            result["config_issues"].append("No config.yaml files found in project")
            result["config_recommendations"].append("Check if config.yaml exists in project root")
            return result
        
        # Check each config file for the code path
        for config_file in config_files:
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # Extract relative path from absolute path
                    try:
                        relative_path = Path(code_path).relative_to(project_root)
                        relative_path_str = str(relative_path)
                    except ValueError:
                        # If not relative to project, use filename
                        relative_path_str = Path(code_path).name
                    
                    # Check if the path is referenced in config
                    if relative_path_str in content:
                        result["in_config_yaml"] = True
                        result["config_recommendations"].append(f"Code path found in {config_file.name}")
                        break
                    
                    # Check for module/import patterns
                    module_patterns = [
                        f"import.*{relative_path_str}",
                        f"from.*{relative_path_str}",
                        f"module.*{relative_path_str}",
                        f"path.*{relative_path_str}"
                    ]
                    
                    for pattern in module_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            result["in_config_yaml"] = True
                            result["config_recommendations"].append(f"Module reference found in {config_file.name}")
                            break
                    
                    if result["in_config_yaml"]:
                        break
                        
            except Exception as e:
                result["config_issues"].append(f"Error reading {config_file}: {e}")
        
        if not result["in_config_yaml"]:
            result["config_issues"].append(f"Code path '{relative_path_str}' not found in any config files")
            result["config_recommendations"].append(f"Add '{relative_path_str}' to config.yaml")
            result["config_recommendations"].append("Check if module is properly imported/configured")
        
        return result
        
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