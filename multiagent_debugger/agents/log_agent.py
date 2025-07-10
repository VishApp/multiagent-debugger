import os
import re
import subprocess
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from crewai import Agent
from langchain.tools import BaseTool

from multiagent_debugger.utils import get_verbose_flag, create_langchain_llm, get_agent_llm_config

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
        
        # Create the appropriate LangChain LLM based on provider
        llm = create_langchain_llm(provider, model, temperature, api_key, api_base)
        
        try:
            agent = Agent(
                role="Log Analyzer",
                goal="Search and analyze logs to find relevant information about API failures",
                backstory="""You are an expert at analyzing application logs to find patterns and errors.
                You can search through log files, filter by time ranges, and extract stack traces
                to help identify the root cause of API failures.""",
                verbose=verbose,
                allow_delegation=False,
                tools=tools or [],
                llm=llm,  # Pass the LangChain LLM object
                max_iter=1,  # Retry up to 3 times if agent fails
                memory=False,  # Disable memory to avoid API key issues
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