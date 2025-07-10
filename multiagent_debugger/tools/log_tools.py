import os
import re
import subprocess
from typing import Dict, Any, List, Optional
from datetime import datetime

from crewai.tools import tool

# Global cache to prevent repeated tool calls
_tool_call_cache = {}

def clear_tool_cache():
    """Clear the tool call cache. Should be called between debug sessions."""
    global _tool_call_cache
    _tool_call_cache.clear()
    print("[DEBUG] Tool cache cleared")

def get_cache_stats():
    """Get statistics about the tool cache."""
    return {
        "cache_size": len(_tool_call_cache),
        "cached_keys": list(_tool_call_cache.keys())
    }

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
        
        # Check cache to prevent repeated calls
        cache_key = f"grep_{query}_{str(log_paths)}"
        if cache_key in _tool_call_cache:
            return f"[CACHED RESULT] {_tool_call_cache[cache_key]}"
        
        print(f"[DEBUG] GrepLogsTool called with query='{query}'")
        print(f"[DEBUG] Using log_paths: {log_paths}")
        
        if not log_paths:
            result = "No log paths provided."
            _tool_call_cache[cache_key] = result
            return result
        
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
                        # Limit output to prevent overwhelming responses
                        lines = output.split('\n')
                        if len(lines) > 10:
                            results.append(f"Results from {log_path} (showing last 10 of {len(lines)} matches):")
                            results.append('\n'.join(lines[-10:]))
                        else:
                            results.append(f"Results from {log_path}:")
                            results.append(output)
                    else:
                        results.append(f"No matches found in {log_path}")
                else:
                    results.append(f"No matches found in {log_path}")
            except Exception as e:
                results.append(f"Error searching {log_path}: {str(e)}")
        
        result = "\n\n".join(results)
        _tool_call_cache[cache_key] = result
        return result
    
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
        
        # Check cache to prevent repeated calls
        cache_key = f"filter_{error_level}_{str(log_paths)}"
        if cache_key in _tool_call_cache:
            return f"[CACHED RESULT] {_tool_call_cache[cache_key]}"
        
        print(f"[DEBUG] FilterLogsTool using log_paths: {log_paths}")
        
        if not log_paths:
            result = "No log paths provided."
            _tool_call_cache[cache_key] = result
            return result
        
        if not error_level:
            result = "Please provide an error level to filter by."
            _tool_call_cache[cache_key] = result
            return result
        
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
                        # Limit output to prevent overwhelming responses
                        lines = output.split('\n')
                        if len(lines) > 10:
                            results.append(f"Results from {log_path} (showing last 10 of {len(lines)} matches):")
                            results.append('\n'.join(lines[-10:]))
                        else:
                            results.append(f"Results from {log_path}:")
                            results.append(output)
                    else:
                        results.append(f"No matches found in {log_path}")
                else:
                    results.append(f"No matches found in {log_path}")
            except Exception as e:
                results.append(f"Error filtering {log_path}: {str(e)}")
        
        result = "\n\n".join(results)
        _tool_call_cache[cache_key] = result
        return result
    
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
        
        # Check cache to prevent repeated calls
        cache_key = f"stack_{filter_term}_{str(log_paths)}"
        if cache_key in _tool_call_cache:
            return f"[CACHED RESULT] {_tool_call_cache[cache_key]}"
        
        print(f"[DEBUG] ExtractStackTracesTool using log_paths: {log_paths}")
        
        if not log_paths:
            result = "No log paths provided."
            _tool_call_cache[cache_key] = result
            return result
        
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
                trace_count = 0
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
                                trace_count += 1
                                if trace_count >= 5:  # Limit to 5 stack traces
                                    break
                # If still in_trace at end of file
                if in_trace and trace_count < 5:
                    trace_str = ''.join(stack_trace)
                    if not filter_term or filter_term in trace_str:
                        results.append(trace_str)
            except Exception as e:
                results.append(f"Error extracting stack traces from {log_path}: {str(e)}")
        
        if not results:
            result = "No stack traces found."
        else:
            result = "\n\n".join(results[:5])  # Limit to 5 stack traces max
            
        _tool_call_cache[cache_key] = result
        return result
    
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