import os
import re
import subprocess
from typing import Dict, Any, List, Optional
from datetime import datetime

from crewai.tools import tool

def create_grep_logs_tool(log_paths: List[str] = None):
    """Create a grep logs tool with the specified log paths."""
    @tool("grep_logs")
    def grep_logs_tool(query: str) -> str:
        """Search log files for specific patterns using grep.
        Useful for finding error messages, user IDs, API routes, etc.
        
        Args:
            query: The pattern to search for
            
        Returns:
            String containing the grep results
        """
        log_paths = tool_log_paths
        print(f"[DEBUG] GrepLogsTool called with query='{query}'")
        print(f"[DEBUG] Using log_paths: {log_paths}")
        
        if not log_paths:
            return "No log paths provided."
        
        results = []
        
        for log_path in log_paths:
            if not os.path.exists(log_path):
                results.append(f"Log file not found: {log_path}")
                continue
            
            try:
                # Run grep command
                cmd = ["grep", "-i", query, log_path]
                process = subprocess.run(cmd, capture_output=True, text=True)
                
                if process.returncode == 0:
                    output = process.stdout.strip()
                    if output:
                        results.append(f"Results from {log_path}:\n{output}")
                    else:
                        results.append(f"No matches found in {log_path}")
                else:
                    results.append(f"No matches found in {log_path}")
            except Exception as e:
                results.append(f"Error searching {log_path}: {str(e)}")
        
        return "\n\n".join(results)
    
    # Capture the log_paths in the closure
    tool_log_paths = log_paths or []
    return grep_logs_tool

def create_filter_logs_tool(log_paths: List[str] = None):
    """Create a filter logs tool with the specified log paths."""
    @tool("filter_logs")
    def filter_logs_tool(error_level: str = None) -> str:
        """Filter log files by error level.
        Returns matching log entries.
        
        Args:
            error_level: Error level to filter by (ERROR, WARN, INFO, DEBUG)
            
        Returns:
            String containing the filtered log entries
        """
        log_paths = tool_log_paths
        
        print(f"[DEBUG] FilterLogsTool using log_paths: {log_paths}")
        
        if not log_paths:
            return "No log paths provided."
        
        if not error_level:
            return "Please provide an error level to filter by."
        
        # Build grep command
        grep_cmd = ["grep", "-i", error_level.upper()]
        
        results = []
        
        for log_path in log_paths:
            if not os.path.exists(log_path):
                results.append(f"Log file not found: {log_path}")
                continue
            
            try:
                # Execute grep command
                cmd = grep_cmd.copy()
                cmd.append(log_path)
                process = subprocess.run(cmd, capture_output=True, text=True)
                
                if process.returncode == 0:
                    output = process.stdout.strip()
                    if output:
                        results.append(f"Results from {log_path}:\n{output}")
                    else:
                        results.append(f"No matches found in {log_path}")
                else:
                    results.append(f"No matches found in {log_path}")
            except Exception as e:
                results.append(f"Error filtering {log_path}: {str(e)}")
        
        return "\n\n".join(results)
    
    # Capture the log_paths in the closure
    tool_log_paths = log_paths or []
    return filter_logs_tool

def create_extract_stack_traces_tool(log_paths: List[str] = None):
    """Create an extract stack traces tool with the specified log paths."""
    @tool("extract_stack_traces")
    def extract_stack_traces_tool(filter_term: str = None) -> str:
        """Extract stack traces from log files.
        Useful for finding detailed error information.
        
        Args:
            filter_term: Optional term to filter stack traces
            
        Returns:
            String containing the extracted stack traces
        """
        log_paths = tool_log_paths
        
        print(f"[DEBUG] ExtractStackTracesTool using log_paths: {log_paths}")
        
        if not log_paths:
            return "No log paths provided."
        
        results = []
        
        for log_path in log_paths:
            if not os.path.exists(log_path):
                results.append(f"Log file not found: {log_path}")
                continue
            
            try:
                with open(log_path, 'r') as f:
                    lines = f.readlines()
                stack_trace = []
                in_trace = False
                for line in lines:
                    if 'Traceback' in line or 'stack trace' in line:
                        in_trace = True
                        stack_trace = [line]
                    elif in_trace:
                        stack_trace.append(line)
                        if line.strip() == '':
                            in_trace = False
                            trace_str = ''.join(stack_trace)
                            if not filter_term or filter_term in trace_str:
                                results.append(trace_str)
                # If still in_trace at end of file
                if in_trace:
                    trace_str = ''.join(stack_trace)
                    if not filter_term or filter_term in trace_str:
                        results.append(trace_str)
            except Exception as e:
                results.append(f"Error extracting stack traces from {log_path}: {str(e)}")
        
        if not results:
            return "No stack traces found."
        
        return "\n\n".join(results)
    
    # Capture the log_paths in the closure
    tool_log_paths = log_paths or []
    return extract_stack_traces_tool

# Legacy functions for backward compatibility
def grep_logs(query: str, log_paths: List[str] = None) -> str:
    """Legacy function - use create_grep_logs_tool instead."""
    tool = create_grep_logs_tool(log_paths)
    return tool(query, log_paths)

def filter_logs(log_paths: List[str] = None, **kwargs) -> str:
    """Legacy function - use create_filter_logs_tool instead."""
    tool = create_filter_logs_tool(log_paths)
    return tool(log_paths, **kwargs)

def extract_stack_traces(log_paths: List[str] = None, **kwargs) -> str:
    """Legacy function - use create_extract_stack_traces_tool instead."""
    tool = create_extract_stack_traces_tool(log_paths)
    return tool(log_paths, **kwargs) 