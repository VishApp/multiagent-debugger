import os
import re
import json
import subprocess
import hashlib
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass
from collections import defaultdict, Counter
import gzip
from enum import Enum

from crewai.tools import tool

# Global cache to prevent repeated tool calls
_log_analysis_cache = {}

class AnalysisMode(Enum):
    LATEST = "latest"
    FREQUENT = "frequent"
    ALL = "all"

@dataclass
class ErrorSignature:
    """Unique signature for an error pattern."""
    error_type: str
    message_hash: str
    code_path: Optional[str]
    line_number: Optional[int]
    function_name: Optional[str]
    
    def __hash__(self):
        return hash((self.error_type, self.message_hash, self.code_path, self.line_number, self.function_name))

@dataclass
class ErrorPattern:
    pattern: str
    count: int
    first_occurrence: datetime
    last_occurrence: datetime
    affected_files: Set[str]
    sample_entries: List['LogEntry']
    signature: ErrorSignature
    frequency_score: float = 0.0

@dataclass
class LogEntry:
    timestamp: Optional[datetime]
    level: str
    message: str
    file_path: str
    line_number: int
    raw_line: str
    context: Dict[str, Any] = None
    error_signature: Optional[ErrorSignature] = None

@dataclass
class StackTrace:
    exception_type: str
    message: str
    file_path: str
    line_number: int
    full_trace: str
    function_calls: List[str] = None
    files_involved: List[str] = None



def clear_log_analysis_cache():
    """Clear the log analysis cache."""
    global _log_analysis_cache
    _log_analysis_cache.clear()

def get_log_cache_stats():
    """Get statistics about the log analysis cache."""
    return {
        "cache_size": len(_log_analysis_cache),
        "cached_keys": list(_log_analysis_cache.keys())
    }

class LogAnalyzer:
    """Enhanced log analyzer with structured parsing and pattern detection."""
    
    def __init__(self, log_paths: List[str], mode: AnalysisMode = AnalysisMode.FREQUENT, 
                 time_window_hours: int = 24, max_lines: int = 10000, code_path: str = None):
        self.log_paths = log_paths
        self.mode = mode
        self.time_window_hours = time_window_hours
        self.max_lines = max_lines
        self.code_path = code_path
        
        self.timestamp_patterns = [
            r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}',  # 2025-07-14 07:32:03
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',    # 2025-07-14T07:32:03
            r'\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}',    # Jul 14 07:32:03
            r'\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2}',  # 07/14/2025 07:32:03
        ]
        self.level_patterns = [
            r'\b(CRITICAL|FATAL|ERROR|WARN|WARNING|INFO|DEBUG|TRACE)\b',
            r'"levelname":\s*"(CRITICAL|FATAL|ERROR|WARN|WARNING|INFO|DEBUG|TRACE)"',
        ]
        self.error_indicators = [
            'error', 'exception', 'traceback', 'failed', 'failure', 'panic',
            'fatal', 'critical', 'timeout', 'refused', 'denied', 'invalid',
            'unauthorized', 'forbidden', 'not found', 'internal server error'
        ]
    
    def _is_code_path_allowed(self, file_path: str) -> bool:
        """Check if a code file path is within the allowed code_path directory.
        
        Args:
            file_path: The file path to check
            
        Returns:
            bool: True if the path is allowed or no code_path is configured, False otherwise
        """
        if not self.code_path:
            # If no code_path is configured, allow all paths (backward compatibility)
            return True
        
        if not file_path:
            return False
        
        try:
            # Convert to absolute paths for comparison
            code_path_abs = os.path.abspath(self.code_path)
            file_path_abs = os.path.abspath(file_path)
            
            # Check if the file is within the code directory
            # Use os.path.commonpath to ensure proper path comparison
            common_path = os.path.commonpath([code_path_abs, file_path_abs])
            
            # If code_path is a file, check exact match
            if os.path.isfile(code_path_abs):
                return code_path_abs == file_path_abs
            
            # If code_path is a directory, check if file is within it
            return common_path == code_path_abs
            
        except (ValueError, OSError):
            # If there's any error in path comparison, deny access for security
            return False
    
    def parse_log_line(self, line: str, file_path: str, line_number: int) -> LogEntry:
        """Parse a single log line into structured format."""
        # Try to parse as JSON first
        if line.strip().startswith('{'):
            try:
                json_data = json.loads(line.strip())
                timestamp = self._extract_timestamp_from_json(json_data)
                level = json_data.get('levelname', json_data.get('level', 'UNKNOWN'))
                message = json_data.get('message', json_data.get('msg', line))
                
                return LogEntry(
                    timestamp=timestamp,
                    level=level.upper(),
                    message=message,
                    file_path=file_path,
                    line_number=line_number,
                    raw_line=line,
                    context=json_data
                )
            except json.JSONDecodeError:
                pass
        
        # Parse as regular log format
        timestamp = self._extract_timestamp(line)
        level = self._extract_level(line)
        message = self._extract_message(line, timestamp, level)
        
        return LogEntry(
            timestamp=timestamp,
            level=level,
            message=message,
            file_path=file_path,
            line_number=line_number,
            raw_line=line
        )
    
    def _extract_timestamp_from_json(self, json_data: Dict) -> Optional[datetime]:
        """Extract timestamp from JSON log entry."""
        timestamp_fields = ['asctime', 'timestamp', '@timestamp', 'time', 'datetime']
        
        for field in timestamp_fields:
            if field in json_data:
                try:
                    timestamp_str = json_data[field]
                    # Try different parsing formats
                    formats = [
                        '%Y-%m-%d %H:%M:%S',
                        '%Y-%m-%dT%H:%M:%S',
                        '%Y-%m-%dT%H:%M:%S.%fZ',
                        '%Y-%m-%dT%H:%M:%S.%f',
                    ]
                    
                    for fmt in formats:
                        try:
                            return datetime.strptime(timestamp_str, fmt)
                        except ValueError:
                            continue
                except (ValueError, TypeError):
                    continue
        
        return None
    
    def _extract_timestamp(self, line: str) -> Optional[datetime]:
        """Extract timestamp from log line."""
        for pattern in self.timestamp_patterns:
            match = re.search(pattern, line)
            if match:
                timestamp_str = match.group()
                try:
                    # Try different parsing formats
                    formats = [
                        '%Y-%m-%d %H:%M:%S',
                        '%Y-%m-%dT%H:%M:%S',
                        '%b %d %H:%M:%S',
                        '%m/%d/%Y %H:%M:%S',
                    ]
                    
                    for fmt in formats:
                        try:
                            return datetime.strptime(timestamp_str, fmt)
                        except ValueError:
                            continue
                except ValueError:
                    pass
        
        return None
    
    def _extract_level(self, line: str) -> str:
        """Extract log level from line."""
        for pattern in self.level_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                return match.group(1).upper()
        
        # Check for error indicators
        line_lower = line.lower()
        if any(indicator in line_lower for indicator in self.error_indicators):
            return 'ERROR'
        
        return 'UNKNOWN'
    
    def _extract_message(self, line: str, timestamp: Optional[datetime], level: str) -> str:
        """Extract the main message from log line."""
        # Remove timestamp and level from message
        message = line
        
        if timestamp:
            # Remove timestamp pattern
            for pattern in self.timestamp_patterns:
                message = re.sub(pattern, '', message).strip()
        
        # Remove level pattern
        for pattern in self.level_patterns:
            message = re.sub(pattern, '', message, flags=re.IGNORECASE).strip()
        
        # Clean up common log prefixes
        prefixes_to_remove = [r'^\[\w+\]', r'^\w+:', r'^\d+\s+']
        for prefix in prefixes_to_remove:
            message = re.sub(prefix, '', message).strip()
        
        return message or line
    
    def search_logs(
        self,
        query: str,
        context_lines: int = 2,
        case_sensitive: bool = False,
        regex_mode: bool = False,
        time_range: Optional[Tuple[datetime, datetime]] = None
    ) -> List[LogEntry]:
        """Enhanced log search with context and filtering."""
        results = []
        
        for log_path in self.log_paths:
            if not os.path.exists(log_path):
                continue
            
            try:
                # Handle compressed files
                if log_path.endswith('.gz'):
                    opener = gzip.open
                    mode = 'rt'
                else:
                    opener = open
                    mode = 'r'
                
                with opener(log_path, mode, encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                
                # Search for matches
                for i, line in enumerate(lines):
                    match_found = False
                    
                    if regex_mode:
                        flags = 0 if case_sensitive else re.IGNORECASE
                        match_found = re.search(query, line, flags)
                    else:
                        if case_sensitive:
                            match_found = query in line
                        else:
                            match_found = query.lower() in line.lower()
                    
                    if match_found:
                        log_entry = self.parse_log_line(line, log_path, i + 1)
                        
                        # Apply time filtering
                        if time_range and log_entry.timestamp:
                            if not (time_range[0] <= log_entry.timestamp <= time_range[1]):
                                continue
                        
                        # Add context lines
                        context_start = max(0, i - context_lines)
                        context_end = min(len(lines), i + context_lines + 1)
                        context_data = {
                            'before': lines[context_start:i],
                            'after': lines[i+1:context_end],
                            'line_numbers': list(range(context_start + 1, context_end + 1))
                        }
                        log_entry.context = log_entry.context or {}
                        log_entry.context['surrounding_lines'] = context_data
                        
                        results.append(log_entry)
            
            except Exception as e:
                pass
        
        return results
    
    def extract_stack_traces(self, filter_term: str = None) -> List[StackTrace]:
        """Enhanced stack trace extraction with better pattern detection."""
        stack_traces = []
        
        # Enhanced stack trace patterns
        trace_start_patterns = [
            r'Traceback \(most recent call last\):',
            r'Exception in thread',
            r'Stack trace:',
            r'java\.lang\.\w+Exception:',
            r'^\s*at\s+\w+',  # Java stack traces
            r'Error:\s+\w+',
            r'Fatal error:',
            r'Unhandled exception:',
        ]
        
        for log_path in self.log_paths:
            if not os.path.exists(log_path):
                continue
            
            try:
                # Handle compressed files
                if log_path.endswith('.gz'):
                    opener = gzip.open
                    mode = 'rt'
                else:
                    opener = open
                    mode = 'r'
                
                with opener(log_path, mode, encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                
                i = 0
                while i < len(lines):
                    line = lines[i]
                    
                    # Check if line starts a stack trace
                    trace_start = False
                    for pattern in trace_start_patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            trace_start = True
                            break
                    
                    if trace_start:
                        # Extract the full stack trace
                        trace_lines = [line]
                        j = i + 1
                        
                        # Continue until we find the end of the trace
                        while j < len(lines):
                            next_line = lines[j]
                            
                            # Stack trace continues if:
                            # - Line starts with whitespace (indented)
                            # - Contains "File", "line", "in", etc.
                            # - Contains exception patterns
                            if (next_line.startswith((' ', '\t')) or
                                re.search(r'\s+File\s+".+",\s+line\s+\d+', next_line) or
                                re.search(r'\s+at\s+\w+', next_line) or
                                re.search(r'^\w+Error:', next_line) or
                                re.search(r'^\w+Exception:', next_line)):
                                trace_lines.append(next_line)
                                j += 1
                            else:
                                break
                        
                        full_trace = ''.join(trace_lines)
                        
                        # Filter if requested
                        if filter_term and filter_term.lower() not in full_trace.lower():
                            i = j
                            continue
                        
                        # Parse the stack trace
                        stack_trace = self._parse_stack_trace(full_trace, log_path, i + 1)
                        if stack_trace:
                            stack_traces.append(stack_trace)
                        
                        i = j
                    else:
                        i += 1
            
            except Exception as e:
                pass
        
        return stack_traces[:20]  # Limit to 20 stack traces
    
    def _parse_stack_trace(self, trace_text: str, file_path: str, line_number: int) -> Optional[StackTrace]:
        """Parse a stack trace to extract structured information."""
        lines = trace_text.strip().split('\n')
        
        # Extract exception type and message
        exception_type = "Unknown"
        message = ""
        
        # Look for the final exception line
        for line in reversed(lines):
            if ':' in line and not line.startswith(' '):
                parts = line.split(':', 1)
                if len(parts) == 2:
                    exception_type = parts[0].strip()
                    message = parts[1].strip()
                    break
        
        # Extract function calls and files
        function_calls = []
        files_involved = []
        source_code_file_path = None
        source_code_line_number = None
        function_name = None
        
        for line in lines:
            # Python stack trace format
            file_match = re.search(r'File\s+"([^"]+)",\s+line\s+(\d+),\s+in\s+(\w+)', line)
            if file_match:
                file_name = file_match.group(1)
                line_num = int(file_match.group(2))
                func_name = file_match.group(3)
                function_calls.append(f"{func_name}() in {file_name}")
                files_involved.append(file_name)
                
                # Set the most relevant source code file (first one found)
                if source_code_file_path is None and self._is_source_code_file(file_name):
                    source_code_file_path = file_name
                    source_code_line_number = line_num
                    function_name = func_name
            
            # Java stack trace format
            java_match = re.search(r'at\s+([^\(]+)\(([^\:]+):(\d+)\)', line)
            if java_match:
                method_name = java_match.group(1)
                file_name = java_match.group(2)
                line_num = int(java_match.group(3))
                function_calls.append(f"{method_name} in {file_name}")
                files_involved.append(file_name)
                
                # Set the most relevant source code file (first one found)
                if source_code_file_path is None and self._is_source_code_file(file_name):
                    source_code_file_path = file_name
                    source_code_line_number = line_num
                    function_name = method_name
            
            # Go stack trace format (look for file paths with line numbers)
            go_match = re.search(r'([/\w\-\.]+\.go):(\d+)', line)
            if go_match:
                file_name = go_match.group(1)
                line_num = int(go_match.group(2))
                files_involved.append(file_name)
                
                # Set the most relevant source code file (first one found)
                if source_code_file_path is None and self._is_source_code_file(file_name):
                    source_code_file_path = file_name
                    source_code_line_number = line_num
                    # Try to extract function name from the line
                    func_match = re.search(r'(\w+)\(', line)
                    if func_match:
                        function_name = func_match.group(1)
            
            # General file path extraction (for any programming language)
            # Look for absolute paths that end with common source code extensions
            path_match = re.search(r'(/[^\s]+\.(py|js|ts|java|go|rs|php|rb|cs|swift|kt|scala|clj|hs|ml|fs|vb|pl|sh|sql|html|css|xml|json|yaml|yml|toml|ini|cfg|conf|md|txt))', line)
            if path_match:
                file_name = path_match.group(1)
                files_involved.append(file_name)
                
                # Set the most relevant source code file (first one found)
                if source_code_file_path is None and self._is_source_code_file(file_name):
                    source_code_file_path = file_name
                    # Try to extract line number from the same line
                    line_num_match = re.search(r':(\d+)', line)
                    if line_num_match:
                        source_code_line_number = int(line_num_match.group(1))
                    # Try to extract function name from the same line
                    func_match = re.search(r'(\w+)\(', line)
                    if func_match:
                        function_name = func_match.group(1)
            
            # Go error format: "exit status 1" followed by file path
            go_error_match = re.search(r'exit status \d+\s*$', line)
            if go_error_match:
                # Look for file path in the same line or previous line
                file_path_in_line = re.search(r'(/[^\s]+\.go)', line)
                if file_path_in_line:
                    file_name = file_path_in_line.group(1)
                    files_involved.append(file_name)
                    
                    if source_code_file_path is None and self._is_source_code_file(file_name):
                        source_code_file_path = file_name
                        # Try to extract function name from the line
                        func_match = re.search(r'(\w+)\(', line)
                        if func_match:
                            function_name = func_match.group(1)
        
        # Use the extracted source code file path instead of the log file path
        actual_file_path = source_code_file_path if source_code_file_path else file_path
        actual_line_number = source_code_line_number if source_code_line_number else line_number
        
        return StackTrace(
            exception_type=exception_type,
            message=message,
            file_path=actual_file_path,
            line_number=actual_line_number,
            full_trace=trace_text,
            function_calls=function_calls,
            files_involved=list(set(files_involved))
        )
    
    def _is_source_code_file(self, file_path: str) -> bool:
        """Check if a file path is a source code file (not a log file or data file) and within allowed code_path."""
        if not file_path:
            return False
        
        file_path_lower = file_path.lower()
        
        # CRITICAL: Exclude log files and temporary files
        if file_path_lower.endswith('.log'):
            return False
        
        # Exclude common log and temporary directories
        log_patterns = ['/logs/', '/log/', '/var/log/', '/tmp/', '/temp/']
        if any(pattern in file_path_lower for pattern in log_patterns):
            return False
        
        # Exclude temporary files and data files
        temp_patterns = ['/tmp/', '/temp/', '/cache/', '/var/cache/']
        if any(pattern in file_path_lower for pattern in temp_patterns):
            return False
        
        # Include JSON files when they're mentioned in error messages (they can be the target of errors)
        # BUT exclude them if they're in log/temp directories
        if file_path_lower.endswith('.json'):
            # Only include JSON files that are not in log/temp directories
            if not any(pattern in file_path_lower for pattern in log_patterns + temp_patterns):
                return True
            return False
        
        # Exclude other data files (YAML, XML, etc.) - these are not source code
        data_file_extensions = ['.yaml', '.yml', '.xml', '.csv', '.txt', '.md']
        for ext in data_file_extensions:
            if file_path_lower.endswith(ext):
                return False
        
        # Include actual source code files
        source_code_extensions = [
            '.py', '.go', '.js', '.ts', '.java', '.cpp', '.c', '.rs', '.php', '.rb', 
            '.cs', '.swift', '.kt', '.scala', '.clj', '.hs', '.ml', '.fs', '.vb', 
            '.pl', '.sh', '.sql', '.html', '.css', '.toml', '.ini', '.cfg', '.conf'
        ]
        
        for ext in source_code_extensions:
            if file_path_lower.endswith(ext):
                # CRITICAL: Also check if the file is within the allowed code_path
                return self._is_code_path_allowed(file_path)
        
        return False
    
    def analyze_error_patterns(self, time_window_hours: int = 24) -> List[ErrorPattern]:
        """Analyze error patterns over time."""
        error_patterns = defaultdict(lambda: {
            'count': 0,
            'first_occurrence': None,
            'last_occurrence': None,
            'affected_files': set(),
            'sample_entries': []
        })
        
        cutoff_time = datetime.now() - timedelta(hours=time_window_hours)
        
        for log_path in self.log_paths:
            if not os.path.exists(log_path):
                continue
            
            try:
                # Handle compressed files
                if log_path.endswith('.gz'):
                    opener = gzip.open
                    mode = 'rt'
                else:
                    opener = open
                    mode = 'r'
                
                with opener(log_path, mode, encoding='utf-8', errors='ignore') as f:
                    for line_num, line in enumerate(f, 1):
                        log_entry = self.parse_log_line(line, log_path, line_num)
                        
                        # Skip if not an error or outside time window
                        if log_entry.level not in ['ERROR', 'CRITICAL', 'FATAL']:
                            continue
                        
                        if log_entry.timestamp and log_entry.timestamp < cutoff_time:
                            continue
                        
                        # Extract error pattern (normalize similar errors)
                        pattern = self._normalize_error_message(log_entry.message)
                        
                        # Update pattern statistics
                        pattern_data = error_patterns[pattern]
                        pattern_data['count'] += 1
                        pattern_data['affected_files'].add(log_path)
                        
                        if log_entry.timestamp:
                            if not pattern_data['first_occurrence'] or log_entry.timestamp < pattern_data['first_occurrence']:
                                pattern_data['first_occurrence'] = log_entry.timestamp
                            if not pattern_data['last_occurrence'] or log_entry.timestamp > pattern_data['last_occurrence']:
                                pattern_data['last_occurrence'] = log_entry.timestamp
                        
                        # Keep sample entries (limit to 3 per pattern)
                        if len(pattern_data['sample_entries']) < 3:
                            pattern_data['sample_entries'].append(log_entry)
            
            except Exception as e:
                pass
        
        # Convert to ErrorPattern objects and sort by frequency
        patterns = []
        for pattern, data in error_patterns.items():
            # Use the first sample entry's error_signature if available, else None
            signature = data['sample_entries'][0].error_signature if data['sample_entries'] and hasattr(data['sample_entries'][0], 'error_signature') else None
            patterns.append(ErrorPattern(
                pattern=pattern,
                count=data['count'],
                first_occurrence=data['first_occurrence'],
                last_occurrence=data['last_occurrence'],
                affected_files=data['affected_files'],
                sample_entries=data['sample_entries'],
                signature=signature
            ))
        
        return sorted(patterns, key=lambda x: x.count, reverse=True)[:10]
    
    def _normalize_error_message(self, message: str) -> str:
        """Normalize error messages to group similar errors."""
        # Remove specific values that make errors look different
        normalized = message
        
        # Replace timestamps
        normalized = re.sub(r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}', '[TIMESTAMP]', normalized)
        
        # Replace IP addresses
        normalized = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '[IP]', normalized)
        
        # Replace file paths
        normalized = re.sub(r'/[^\s:]+', '[PATH]', normalized)
        
        # Replace numbers that might be IDs, ports, etc.
        normalized = re.sub(r'\b\d{3,}\b', '[NUMBER]', normalized)
        
        # Replace UUIDs
        normalized = re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '[UUID]', normalized)
        
        return normalized.strip()

    def extract_code_paths_from_log_lines(self) -> List[dict]:
        """
        Scan all log lines for absolute source code file paths and line numbers.
        Returns a list of dicts with file_path, line_number, error_context, and confidence.
        """
        code_paths = []
        
        for log_path in self.log_paths:
            if not os.path.exists(log_path):
                continue
            try:
                with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for idx, line in enumerate(f, 1):
                        # Use the improved extraction logic
                        extracted = self._extract_code_path_from_line(line)
                        if extracted:
                            code_paths.append({
                                'file_path': extracted['file_path'],
                                'line_number': extracted['line_number'],
                                'error_context': line.strip(),
                                'log_file': log_path,
                                'log_line_number': idx,
                                'confidence': 'high'
                            })
            except Exception as e:
                pass
        return code_paths

    def _create_error_signature(self, log_entry: LogEntry, code_path: Optional[str] = None, 
                               line_number: Optional[int] = None, function_name: Optional[str] = None) -> ErrorSignature:
        """Create a unique error signature for pattern matching."""
        # Normalize the error message for better matching
        normalized_message = self._normalize_error_message(log_entry.message)
        message_hash = hashlib.md5(normalized_message.encode()).hexdigest()[:8]
        
        # Extract error type from the message
        error_type = "Unknown"
        if ":" in log_entry.message:
            error_type = log_entry.message.split(":")[0].strip()
        
        return ErrorSignature(
            error_type=error_type,
            message_hash=message_hash,
            code_path=code_path,
            line_number=line_number,
            function_name=function_name
        )
    
    def _calculate_frequency_score(self, pattern: ErrorPattern, total_errors: int) -> float:
        """Calculate a frequency score for prioritization."""
        # Base score from frequency
        frequency_score = pattern.count / max(total_errors, 1)
        
        # Recency bonus (errors in last hour get higher score)
        now = datetime.now()
        if pattern.last_occurrence:
            hours_since_last = (now - pattern.last_occurrence).total_seconds() / 3600
            recency_bonus = max(0, 1 - (hours_since_last / 24))  # Decay over 24 hours
            frequency_score *= (1 + recency_bonus)
        
        return frequency_score
    
    def smart_sample_logs(self, log_path: str) -> List[str]:
        """Smart sampling for large log files."""
        try:
            # Get file size
            file_size = os.path.getsize(log_path)
            
            # If file is small, read all lines
            if file_size < 10 * 1024 * 1024:  # 10MB
                with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.readlines()
            
            # For large files, use stratified sampling
            lines = []
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Read last N lines (most recent)
                all_lines = f.readlines()
                if len(all_lines) <= self.max_lines:
                    return all_lines
                
                # Take last 70% of lines (recent activity)
                start_idx = int(len(all_lines) * 0.3)
                recent_lines = all_lines[start_idx:]
                
                # Sample from recent lines
                if len(recent_lines) <= self.max_lines:
                    lines = recent_lines
                else:
                    # Stratified sampling: take every Nth line
                    step = len(recent_lines) // self.max_lines
                    lines = recent_lines[::step][:self.max_lines]
            
            return lines
            
        except Exception as e:
            return []
    
    def analyze_errors_intelligent(self) -> Dict[str, Any]:
        """
        Intelligent error analysis with time-based filtering and pattern recognition.
        Returns structured analysis suitable for agent consumption.
        """
        cutoff_time = datetime.now() - timedelta(hours=self.time_window_hours)
        error_patterns = defaultdict(lambda: {
            'count': 0,
            'first_occurrence': None,
            'last_occurrence': None,
            'affected_files': set(),
            'sample_entries': [],
            'signatures': set(),
            'code_paths': set()
        })
        
        all_errors = []
        latest_errors = []
        
        for log_path in self.log_paths:
            if not os.path.exists(log_path):
                continue
            
            # Smart sampling for large logs
            lines = self.smart_sample_logs(log_path)
            
            for line_num, line in enumerate(lines, 1):
                log_entry = self.parse_log_line(line, log_path, line_num)
                
                # Skip if not an error or outside time window
                if log_entry.level not in ['ERROR', 'CRITICAL', 'FATAL']:
                    continue
                
                if log_entry.timestamp and log_entry.timestamp < cutoff_time:
                    continue
                
                # Extract code path from this line
                code_path_info = self._extract_code_path_from_line(line)
                code_path = code_path_info.get('file_path') if code_path_info else None
                line_number = code_path_info.get('line_number') if code_path_info else None
                function_name = code_path_info.get('function_name') if code_path_info else None
                
                # Create error signature
                signature = self._create_error_signature(log_entry, code_path, line_number, function_name)
                log_entry.error_signature = signature
                
                # Group by signature
                pattern_key = str(signature)
                pattern_data = error_patterns[pattern_key]
                pattern_data['count'] += 1
                pattern_data['affected_files'].add(log_path)
                pattern_data['signatures'].add(signature)
                if code_path:
                    pattern_data['code_paths'].add(code_path)
                
                if log_entry.timestamp:
                    if not pattern_data['first_occurrence'] or log_entry.timestamp < pattern_data['first_occurrence']:
                        pattern_data['first_occurrence'] = log_entry.timestamp
                    if not pattern_data['last_occurrence'] or log_entry.timestamp > pattern_data['last_occurrence']:
                        pattern_data['last_occurrence'] = log_entry.timestamp
                
                # Keep sample entries (limit to 3 per pattern)
                if len(pattern_data['sample_entries']) < 3:
                    pattern_data['sample_entries'].append(log_entry)
                
                all_errors.append(log_entry)
                latest_errors.append(log_entry)
        
        # Convert to ErrorPattern objects
        patterns = []
        total_errors = len(all_errors)
        
        for pattern_key, data in error_patterns.items():
            if data['sample_entries']:
                # Use the first signature as representative
                signature = list(data['signatures'])[0]
                
                pattern = ErrorPattern(
                    pattern=data['sample_entries'][0].message,
                    count=data['count'],
                    first_occurrence=data['first_occurrence'],
                    last_occurrence=data['last_occurrence'],
                    affected_files=data['affected_files'],
                    sample_entries=data['sample_entries'],
                    signature=signature
                )
                
                # Calculate frequency score
                pattern.frequency_score = self._calculate_frequency_score(pattern, total_errors)
                patterns.append(pattern)
        
        # Sort patterns by frequency score
        patterns.sort(key=lambda p: p.frequency_score, reverse=True)
        
        # Get most recent unique errors
        latest_unique = []
        seen_signatures = set()
        for error in reversed(latest_errors):  # Start from most recent
            if error.error_signature and str(error.error_signature) not in seen_signatures:
                latest_unique.append(error)
                seen_signatures.add(str(error.error_signature))
                if len(latest_unique) >= 5:  # Limit to 5 most recent unique errors
                    break
        
        return {
            'patterns': patterns,
            'latest_unique_errors': latest_unique,
            'total_errors': total_errors,
            'time_window_hours': self.time_window_hours,
            'analysis_mode': self.mode.value
        }
    
    def _extract_code_path_from_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Extract code path, line number, and function name from a single log line."""
        # Define source code extensions (prioritize actual source code files)
        source_code_extensions = [
            '.py', '.go', '.js', '.ts', '.java', '.cpp', '.c', '.rs', '.php', '.rb', 
            '.cs', '.swift', '.kt', '.scala', '.clj', '.hs', '.ml', '.fs', '.vb', 
            '.pl', '.sh', '.sql', '.html', '.css', '.toml', '.ini', '.cfg', '.conf', '.json'
        ]
        
        # Try different patterns for different log formats
        # PRIORITY: Source code files first
        
        # 1. Go error message: HandleRequest Upload error:: upload to s3 failed: some uploads failed: /path/to/file.go
        go_error_match = re.search(r'([^:]+\.go)(?:\s*$|\s*:)', line)
        if go_error_match:
            file_path = go_error_match.group(1)
            if self._is_source_code_file(file_path):
                result = {
                    'file_path': file_path,
                    'line_number': None,
                    'function_name': None
                }
                return result
        
        # 2. Go error with specific pattern: upload to s3 failed: some uploads failed: /path/to/file.go
        go_upload_error_match = re.search(r'upload to s3 failed.*?failed:\s+([^:]+\.go)', line)
        if go_upload_error_match:
            file_path = go_upload_error_match.group(1)
            if self._is_source_code_file(file_path):
                result = {
                    'file_path': file_path,
                    'line_number': None,
                    'function_name': None
                }
                return result
        
        # 3. Python stack trace: File "/path/file.py", line 45, in function_name
        python_match = re.search(r'File\s+["\']([^"\']+)["\'],\s+line\s+(\d+),\s+in\s+(\w+)', line)
        if python_match:
            file_path = python_match.group(1)
            line_number = int(python_match.group(2))
            function_name = python_match.group(3)
            
            if self._is_source_code_file(file_path):
                result = {
                    'file_path': file_path,
                    'line_number': line_number,
                    'function_name': function_name
                }
                return result
        
        # 4. JavaScript stack trace: at functionName (/path/file.js:45:15)
        js_match = re.search(r'at\s+(\w+)\s+\(([^:]+):(\d+):\d+\)', line)
        if js_match:
            function_name = js_match.group(1)
            file_path = js_match.group(2)
            line_number = int(js_match.group(3))
            
            if self._is_source_code_file(file_path):
                result = {
                    'file_path': file_path,
                    'line_number': line_number,
                    'function_name': function_name
                }
                return result
        
        # 5. Java stack trace: at com.package.Class.method(Class.java:45)
        java_match = re.search(r'at\s+([^(]+)\.(\w+)\(([^:]+):(\d+)\)', line)
        if java_match:
            package_class = java_match.group(1)
            function_name = java_match.group(2)
            file_path = java_match.group(3)
            line_number = int(java_match.group(4))
            
            if self._is_source_code_file(file_path):
                result = {
                    'file_path': file_path,
                    'line_number': line_number,
                    'function_name': function_name
                }
                return result
        
        # 6. Ruby stack trace: /path/file.rb:45:in `function_name'
        ruby_match = re.search(r'([^:]+\.rb):(\d+):in\s+`([^`]+)\'', line)
        if ruby_match:
            file_path = ruby_match.group(1)
            line_number = int(ruby_match.group(2))
            function_name = ruby_match.group(3)
            
            if self._is_source_code_file(file_path):
                result = {
                    'file_path': file_path,
                    'line_number': line_number,
                    'function_name': function_name
                }
                return result
        
        # 7. Go error with line number: /path/file.go:45: error message
        go_match = re.search(r'([^:]+\.go):(\d+):\s+', line)
        if go_match:
            file_path = go_match.group(1)
            line_number = int(go_match.group(2))
            
            if self._is_source_code_file(file_path):
                result = {
                    'file_path': file_path,
                    'line_number': line_number,
                    'function_name': None
                }
                return result
        
        # 8. Rust panic: src/file.rs:67:5
        rust_match = re.search(r'([^:]+\.rs):(\d+):\d+', line)
        if rust_match:
            file_path = rust_match.group(1)
            line_number = int(rust_match.group(2))
            
            if self._is_source_code_file(file_path):
                result = {
                    'file_path': file_path,
                    'line_number': line_number,
                    'function_name': None
                }
                return result
        
        # 9. PHP error: in /path/file.php:123
        php_match = re.search(r'in\s+([^:]+\.php):(\d+)', line)
        if php_match:
            file_path = php_match.group(1)
            line_number = int(php_match.group(2))
            
            if self._is_source_code_file(file_path):
                result = {
                    'file_path': file_path,
                    'line_number': line_number,
                    'function_name': None
                }
                return result
        
        # 10. C++ error: in /path/file.cpp:45
        cpp_match = re.search(r'in\s+([^:]+\.cpp):(\d+)', line)
        if cpp_match:
            file_path = cpp_match.group(1)
            line_number = int(cpp_match.group(2))
            
            if self._is_source_code_file(file_path):
                result = {
                    'file_path': file_path,
                    'line_number': line_number,
                    'function_name': None
                }
                return result
        
        # 11. Generic source code file path: /path/file.ext
        # Sort extensions by length (longest first) to avoid partial matches
        # This ensures .json matches before .js
        sorted_extensions = sorted(source_code_extensions, key=len, reverse=True)
        generic_match = re.search(r'(/[^\s:]+(' + '|'.join([re.escape(ext) for ext in sorted_extensions]) + r'))(?::(\d+))?', line)
        if generic_match:
            file_path = generic_match.group(1)
            line_number = int(generic_match.group(3)) if generic_match.group(3) else None
            
            # CRITICAL: Exclude log file paths and paths that are clearly not source code
            # Check if this looks like a log file path or data file path
            file_path_lower = file_path.lower()
            
            # Exclude if it contains common log directory patterns
            log_patterns = ['/logs/', '/log/', '/var/log/', '/tmp/', '/temp/']
            if any(pattern in file_path_lower for pattern in log_patterns):
                return None
            
            # Exclude if it ends with .log (should be caught by _is_source_code_file, but double-check)
            if file_path_lower.endswith('.log'):
                return None
            
            # Only proceed if it's actually a source code file
            if self._is_source_code_file(file_path):
                result = {
                    'file_path': file_path,
                    'line_number': line_number,
                    'function_name': None
                }
                return result
        
        return None

def create_enhanced_grep_logs_tool(log_paths: List[str] = None, agent_config: Dict[str, Any] = None):
    """Create an enhanced grep logs tool."""
    @tool("grep_logs")
    def enhanced_grep_logs_tool(
        query: str,
        context_lines: int = 2,
        case_sensitive: bool = False,
        regex_mode: bool = False,
        time_range_hours: int = None
    ) -> str:
        """Enhanced search of log files with context and filtering options.
        
        Args:
            query: Pattern to search for
            context_lines: Number of context lines before/after match (default: 2)
            case_sensitive: Whether search should be case sensitive (default: False)
            regex_mode: Whether to treat query as regex (default: False)
            time_range_hours: Only show results from last N hours (optional)
            
        Returns:
            String containing the enhanced search results
        """
        # Check cache
        cache_key = f"enhanced_grep_{query}_{context_lines}_{case_sensitive}_{regex_mode}_{time_range_hours}_{str(log_paths)}"
        if cache_key in _log_analysis_cache:
            return f"[CACHED RESULT] {_log_analysis_cache[cache_key]}"
                
        if not log_paths:
            result = "❌ ERROR: No log paths configured. Cannot perform log search."
            _log_analysis_cache[cache_key] = result
            return result
        
        # Validate that at least one log path exists
        valid_log_paths = []
        for log_path in log_paths:
            if os.path.exists(log_path):
                valid_log_paths.append(log_path)
        
        if not valid_log_paths:
            result = f"❌ ERROR: No valid log files found. Checked paths: {log_paths}"
            _log_analysis_cache[cache_key] = result
            return result
        
        try:
            # Use agent config values with proper defaults
            if agent_config:
                final_mode = agent_config.get('analysis_mode') or 'frequent'
                final_time_window = agent_config.get('time_window_hours') or 24
                final_max_lines = agent_config.get('max_lines') or 10000
            else:
                final_mode = 'frequent'
                final_time_window = 24
                final_max_lines = 10000
            
            # Parse mode
            try:
                analysis_mode = AnalysisMode(final_mode.lower())
            except ValueError:
                analysis_mode = AnalysisMode.FREQUENT
            
            # Get code_path from agent_config if available
            code_path = None
            if agent_config:
                code_path = agent_config.get('code_path')
            
            analyzer = LogAnalyzer(
                log_paths,
                mode=analysis_mode,
                time_window_hours=final_time_window,
                max_lines=final_max_lines,
                code_path=code_path
            )
            
            # Set time range if specified
            time_range = None
            if time_range_hours:
                end_time = datetime.now()
                start_time = end_time - timedelta(hours=time_range_hours)
                time_range = (start_time, end_time)
            
            # Search logs
            results = analyzer.search_logs(
                query=query,
                context_lines=context_lines,
                case_sensitive=case_sensitive,
                regex_mode=regex_mode,
                time_range=time_range
            )
            
            if not results:
                result = f"No matches found for query '{query}'"
                if time_range_hours:
                    result += f" in the last {time_range_hours} hours"
                result += "."
                _log_analysis_cache[cache_key] = result
                return result
            
            # Format results
            formatted_results = [f"🔍 ENHANCED LOG SEARCH RESULTS"]
            formatted_results.append(f"Query: '{query}' | Matches: {len(results)}")
            if time_range_hours:
                formatted_results.append(f"Time Range: Last {time_range_hours} hours")
            formatted_results.append("")
            
            for i, entry in enumerate(results[:20], 1):  # Limit to 20 results
                formatted_results.append(f"📍 MATCH #{i}:")
                formatted_results.append(f"  File: {entry.file_path}:{entry.line_number}")
                if entry.timestamp:
                    formatted_results.append(f"  Time: {entry.timestamp}")
                formatted_results.append(f"  Level: {entry.level}")
                
                # Show context if available
                if entry.context and 'surrounding_lines' in entry.context:
                    context = entry.context['surrounding_lines']
                    formatted_results.append("  Context:")
                    
                    # Before lines
                    for j, before_line in enumerate(context['before']):
                        line_num = context['line_numbers'][j]
                        formatted_results.append(f"    {line_num:4d} | {before_line.rstrip()}")
                    
                    # Matched line (highlighted)
                    formatted_results.append(f"  → {entry.line_number:4d} | {entry.raw_line.rstrip()}")
                    
                    # After lines
                    after_start = len(context['before']) + 1
                    for j, after_line in enumerate(context['after']):
                        line_num = context['line_numbers'][after_start + j]
                        formatted_results.append(f"    {line_num:4d} | {after_line.rstrip()}")
                else:
                    formatted_results.append(f"  Message: {entry.message}")
                
                formatted_results.append("")
            
            if len(results) > 20:
                formatted_results.append(f"... and {len(results) - 20} more matches")
            
            result = "\n".join(formatted_results)
            _log_analysis_cache[cache_key] = result
            return result
            
        except Exception as e:
            result = f"Error in enhanced log search: {str(e)}"
            _log_analysis_cache[cache_key] = result
            return result
    
    return enhanced_grep_logs_tool

def create_enhanced_extract_stack_traces_tool(log_paths: List[str] = None, agent_config: Dict[str, Any] = None):
    """Create an enhanced extract stack traces tool."""
    @tool("extract_stack_traces")
    def enhanced_extract_stack_traces_tool(filter_term: str = None) -> str:
        """Enhanced extraction of stack traces from log files.
        
        Args:
            filter_term: Optional term to filter stack traces
            
        Returns:
            String containing detailed stack trace analysis
        """
        # Check cache
        cache_key = f"enhanced_stack_{filter_term}_{str(log_paths)}"
        if cache_key in _log_analysis_cache:
            return f"[CACHED RESULT] {_log_analysis_cache[cache_key]}"
                
        if not log_paths:
            result = "No log paths provided."
            _log_analysis_cache[cache_key] = result
            return result
        
        try:
            # Use agent config values with proper defaults
            if agent_config:
                final_mode = agent_config.get('analysis_mode') or 'frequent'
                final_time_window = agent_config.get('time_window_hours') or 24
                final_max_lines = agent_config.get('max_lines') or 10000
            else:
                final_mode = 'frequent'
                final_time_window = 24
                final_max_lines = 10000
            
            # Parse mode
            try:
                analysis_mode = AnalysisMode(final_mode.lower())
            except ValueError:
                analysis_mode = AnalysisMode.FREQUENT
            
            # Get code_path from agent_config if available
            code_path = None
            if agent_config:
                code_path = agent_config.get('code_path')
            
            analyzer = LogAnalyzer(
                log_paths,
                mode=analysis_mode,
                time_window_hours=final_time_window,
                max_lines=final_max_lines,
                code_path=code_path
            )
            stack_traces = analyzer.extract_stack_traces(filter_term)
            
            if not stack_traces:
                result = "No stack traces found."
                if filter_term:
                    result += f" (filtered by '{filter_term}')"
                _log_analysis_cache[cache_key] = result
                return result
            
            # Format results
            formatted_results = [f"🔥 STACK TRACE ANALYSIS"]
            formatted_results.append(f"Found: {len(stack_traces)} stack traces")
            if filter_term:
                formatted_results.append(f"Filter: '{filter_term}'")
            formatted_results.append("")
            
            # Group by exception type
            by_exception = defaultdict(list)
            for trace in stack_traces:
                by_exception[trace.exception_type].append(trace)
            
            for exc_type, traces in by_exception.items():
                formatted_results.append(f"🚨 EXCEPTION TYPE: {exc_type} ({len(traces)} occurrences)")
                formatted_results.append("")
                
                for i, trace in enumerate(traces[:3], 1):  # Show first 3 of each type
                    formatted_results.append(f"  📍 OCCURRENCE #{i}:")
                    formatted_results.append(f"    File: {trace.file_path}:{trace.line_number}")
                    formatted_results.append(f"    Message: {trace.message}")
                    
                    if trace.function_calls:
                        formatted_results.append(f"    Call Stack:")
                        for call in trace.function_calls[-5:]:  # Last 5 calls
                            formatted_results.append(f"      • {call}")
                    
                    if trace.files_involved:
                        formatted_results.append(f"    Files Involved: {', '.join(trace.files_involved)}")
                    
                    formatted_results.append(f"    Full Stack Trace:")
                    formatted_results.append("    ```")
                    for line in trace.full_trace.split('\n')[:10]:  # Limit lines
                        formatted_results.append(f"    {line}")
                    formatted_results.append("    ```")
                    formatted_results.append("")
                
                if len(traces) > 3:
                    formatted_results.append(f"    ... and {len(traces) - 3} more occurrences of {exc_type}")
                formatted_results.append("")
            
            result = "\n".join(formatted_results)
            _log_analysis_cache[cache_key] = result
            return result
            
        except Exception as e:
            result = f"Error extracting stack traces: {str(e)}"
            _log_analysis_cache[cache_key] = result
            return result
    
    return enhanced_extract_stack_traces_tool

def create_error_pattern_analysis_tool(log_paths: List[str] = None, agent_config: Dict[str, Any] = None):
    """Create an error pattern analysis tool."""
    @tool("analyze_error_patterns")
    def analyze_error_patterns_tool(time_window_hours: int = 24) -> str:
        """Analyze error patterns and frequencies over time.
        
        Args:
            time_window_hours: Time window to analyze (default: 24 hours)
            
        Returns:
            String containing error pattern analysis
        """
        # Check cache
        cache_key = f"error_patterns_{time_window_hours}_{str(log_paths)}"
        if cache_key in _log_analysis_cache:
            return f"[CACHED RESULT] {_log_analysis_cache[cache_key]}"
                
        if not log_paths:
            result = "No log paths provided."
            _log_analysis_cache[cache_key] = result
            return result
        
        try:
            # Use agent config values with proper defaults
            if agent_config:
                final_mode = agent_config.get('analysis_mode') or 'frequent'
                final_time_window = agent_config.get('time_window_hours') or 24
                final_max_lines = agent_config.get('max_lines') or 10000
            else:
                final_mode = 'frequent'
                final_time_window = 24
                final_max_lines = 10000
            
            # Parse mode
            try:
                analysis_mode = AnalysisMode(final_mode.lower())
            except ValueError:
                analysis_mode = AnalysisMode.FREQUENT
            
            # Get code_path from agent_config if available
            code_path = None
            if agent_config:
                code_path = agent_config.get('code_path')
            
            analyzer = LogAnalyzer(
                log_paths,
                mode=analysis_mode,
                time_window_hours=final_time_window,
                max_lines=final_max_lines,
                code_path=code_path
            )
            patterns = analyzer.analyze_error_patterns(time_window_hours)
            
            if not patterns:
                result = f"No error patterns found in the last {time_window_hours} hours."
                _log_analysis_cache[cache_key] = result
                return result
            
            # Format results
            formatted_results = [f"📊 ERROR PATTERN ANALYSIS"]
            formatted_results.append(f"Time Window: Last {time_window_hours} hours")
            formatted_results.append(f"Patterns Found: {len(patterns)}")
            formatted_results.append("")
            
            for i, pattern in enumerate(patterns, 1):
                formatted_results.append(f"🔴 PATTERN #{i}: {pattern.pattern}")
                formatted_results.append(f"  Frequency: {pattern.count} occurrences")
                formatted_results.append(f"  Affected Files: {len(pattern.affected_files)}")
                
                if pattern.first_occurrence and pattern.last_occurrence:
                    duration = pattern.last_occurrence - pattern.first_occurrence
                    formatted_results.append(f"  Duration: {duration}")
                    formatted_results.append(f"  First: {pattern.first_occurrence}")
                    formatted_results.append(f"  Latest: {pattern.last_occurrence}")
                
                formatted_results.append(f"  Sample Entries:")
                for j, entry in enumerate(pattern.sample_entries[:2], 1):
                    formatted_results.append(f"    {j}. {entry.file_path}:{entry.line_number}")
                    formatted_results.append(f"       {entry.message[:100]}...")
                
                formatted_results.append("")
            
            result = "\n".join(formatted_results)
            _log_analysis_cache[cache_key] = result
            return result
            
        except Exception as e:
            result = f"Error analyzing error patterns: {str(e)}"
            _log_analysis_cache[cache_key] = result
            return result
    
    return analyze_error_patterns_tool

def create_enhanced_filter_logs_tool(log_paths: List[str] = None, agent_config: Dict[str, Any] = None):
    """Create an enhanced filter logs tool."""
    @tool("filter_logs")
    def enhanced_filter_logs_tool(
        error_level: str = None,
        time_range_hours: int = None,
        exclude_patterns: str = None
    ) -> str:
        """Enhanced filtering of log files with multiple criteria.
        
        Args:
            error_level: Error level to filter by (ERROR, WARN, INFO, DEBUG)
            time_range_hours: Only show logs from last N hours (optional)
            exclude_patterns: Comma-separated patterns to exclude (optional)
            
        Returns:
            String containing filtered log entries with analysis
        """
        # Check cache
        cache_key = f"enhanced_filter_{error_level}_{time_range_hours}_{exclude_patterns}_{str(log_paths)}"
        if cache_key in _log_analysis_cache:
            return f"[CACHED RESULT] {_log_analysis_cache[cache_key]}"
                
        if not log_paths:
            result = "No log paths provided."
            _log_analysis_cache[cache_key] = result
            return result
        
        if not error_level:
            result = "Please provide an error level to filter by."
            _log_analysis_cache[cache_key] = result
            return result
        
        try:
            # Use agent config values with proper defaults
            if agent_config:
                final_mode = agent_config.get('analysis_mode') or 'frequent'
                final_time_window = agent_config.get('time_window_hours') or 24
                final_max_lines = agent_config.get('max_lines') or 10000
            else:
                final_mode = 'frequent'
                final_time_window = 24
                final_max_lines = 10000
            
            # Parse mode
            try:
                analysis_mode = AnalysisMode(final_mode.lower())
            except ValueError:
                analysis_mode = AnalysisMode.FREQUENT
            
            # Get code_path from agent_config if available
            code_path = None
            if agent_config:
                code_path = agent_config.get('code_path')
            
            analyzer = LogAnalyzer(
                log_paths,
                mode=analysis_mode,
                time_window_hours=final_time_window,
                max_lines=final_max_lines,
                code_path=code_path
            )
            
            # Set time range if specified
            time_range = None
            if time_range_hours:
                end_time = datetime.now()
                start_time = end_time - timedelta(hours=time_range_hours)
                time_range = (start_time, end_time)
            
            # Parse exclude patterns
            exclude_list = []
            if exclude_patterns:
                exclude_list = [p.strip() for p in exclude_patterns.split(',')]
            
            # Collect filtered entries
            filtered_entries = []
            total_processed = 0
            
            for log_path in log_paths:
                if not os.path.exists(log_path):
                    continue
                
                try:
                    # Handle compressed files
                    if log_path.endswith('.gz'):
                        opener = gzip.open
                        mode = 'rt'
                    else:
                        opener = open
                        mode = 'r'
                    
                    with opener(log_path, mode, encoding='utf-8', errors='ignore') as f:
                        for line_num, line in enumerate(f, 1):
                            total_processed += 1
                            
                            log_entry = analyzer.parse_log_line(line, log_path, line_num)
                            
                            # Apply level filter
                            if log_entry.level != error_level.upper():
                                continue
                            
                            # Apply time filter
                            if time_range and log_entry.timestamp:
                                if not (time_range[0] <= log_entry.timestamp <= time_range[1]):
                                    continue
                            
                            # Apply exclude patterns
                            if exclude_list:
                                should_exclude = any(
                                    pattern.lower() in log_entry.message.lower() 
                                    for pattern in exclude_list
                                )
                                if should_exclude:
                                    continue
                            
                            filtered_entries.append(log_entry)
                            
                            # Limit results to prevent overwhelming output
                            if len(filtered_entries) >= 50:
                                break
                
                except Exception as e:
                    print(f"[DEBUG] Error filtering {log_path}: {e}")
            
            if not filtered_entries:
                result = f"No {error_level} level entries found"
                if time_range_hours:
                    result += f" in the last {time_range_hours} hours"
                if exclude_patterns:
                    result += f" (excluding patterns: {exclude_patterns})"
                result += "."
                _log_analysis_cache[cache_key] = result
                return result
            
            # Format results with analysis
            formatted_results = [f"📊 ENHANCED LOG FILTER RESULTS"]
            formatted_results.append(f"Level: {error_level.upper()} | Found: {len(filtered_entries)} entries")
            if time_range_hours:
                formatted_results.append(f"Time Range: Last {time_range_hours} hours")
            if exclude_patterns:
                formatted_results.append(f"Excluded: {exclude_patterns}")
            formatted_results.append(f"Processed: {total_processed} total log lines")
            formatted_results.append("")
            
            # Group by file for better organization
            by_file = defaultdict(list)
            for entry in filtered_entries:
                by_file[entry.file_path].append(entry)
            
            for file_path, entries in by_file.items():
                formatted_results.append(f"📁 FILE: {file_path} ({len(entries)} entries)")
                formatted_results.append("")
                
                # Show recent entries from this file
                recent_entries = sorted(entries, key=lambda x: x.timestamp or datetime.min, reverse=True)[:10]
                
                for i, entry in enumerate(recent_entries, 1):
                    formatted_results.append(f"  📍 ENTRY #{i}:")
                    formatted_results.append(f"    Line: {entry.line_number}")
                    if entry.timestamp:
                        formatted_results.append(f"    Time: {entry.timestamp}")
                    formatted_results.append(f"    Message: {entry.message}")
                    
                    # Show JSON context if available
                    if entry.context and isinstance(entry.context, dict):
                        important_fields = ['error', 'exception', 'stack_trace', 'user_id', 'request_id']
                        for field in important_fields:
                            if field in entry.context:
                                value = str(entry.context[field])[:100]
                                formatted_results.append(f"    {field}: {value}")
                    
                    formatted_results.append("")
                
                if len(entries) > 10:
                    formatted_results.append(f"    ... and {len(entries) - 10} more entries from this file")
                formatted_results.append("")
            
            # Add summary statistics
            formatted_results.append("📈 SUMMARY STATISTICS:")
            
            # Time distribution
            if any(entry.timestamp for entry in filtered_entries):
                timestamps = [entry.timestamp for entry in filtered_entries if entry.timestamp]
                if timestamps:
                    earliest = min(timestamps)
                    latest = max(timestamps)
                    formatted_results.append(f"  Time Span: {earliest} to {latest}")
            
            # File distribution
            file_counts = Counter(entry.file_path for entry in filtered_entries)
            formatted_results.append(f"  Files Affected: {len(file_counts)}")
            for file_path, count in file_counts.most_common(5):
                formatted_results.append(f"    • {os.path.basename(file_path)}: {count} entries")
            
            # Message patterns (top error messages)
            message_patterns = Counter()
            for entry in filtered_entries:
                # Normalize message for pattern detection
                normalized = analyzer._normalize_error_message(entry.message)
                message_patterns[normalized] += 1
            
            if message_patterns:
                formatted_results.append(f"  Top Error Patterns:")
                for pattern, count in message_patterns.most_common(3):
                    formatted_results.append(f"    • {pattern[:80]}... ({count} times)")
            
            result = "\n".join(formatted_results)
            _log_analysis_cache[cache_key] = result
            return result
            
        except Exception as e:
            result = f"Error in enhanced log filtering: {str(e)}"
            _log_analysis_cache[cache_key] = result
            return result
    
    return enhanced_filter_logs_tool

def create_intelligent_error_analysis_tool(log_paths: List[str] = None, agent_config: Dict[str, Any] = None):
    """Create an intelligent error analysis tool."""
    
    @tool("analyze_errors_intelligent")
    def intelligent_error_analysis_tool() -> str:
        """
        Perform intelligent error analysis with time-based filtering and pattern recognition.
        Uses configuration values for analysis mode, time window, and max lines.
        
        Returns:
            JSON string with error patterns, code paths, and routing recommendations
        """
        try:
            # Validate log paths first
            if not log_paths:
                return json.dumps({
                    "error": "No log paths configured",
                    "routing_decision": {
                        "should_analyze_code": False,
                        "reason": "No log paths provided - cannot analyze logs"
                    }
                }, indent=2)
            
            # Check if any log files exist and have content
            valid_log_paths = []
            for log_path in log_paths:
                if os.path.exists(log_path) and os.path.getsize(log_path) > 0:
                    valid_log_paths.append(log_path)
            
            if not valid_log_paths:
                return json.dumps({
                    "error": "No valid log files found or all log files are empty",
                    "routing_decision": {
                        "should_analyze_code": False,
                        "reason": f"No valid log files found. Checked paths: {log_paths}"
                    }
                }, indent=2)
            
            # Use agent config values with proper defaults
            if agent_config:
                final_mode = agent_config.get('analysis_mode') or 'frequent'
                final_time_window = agent_config.get('time_window_hours') or 24
                final_max_lines = agent_config.get('max_lines') or 10000
            else:
                final_mode = 'frequent'
                final_time_window = 24
                final_max_lines = 10000
                       
            # Parse mode
            try:
                analysis_mode = AnalysisMode(final_mode.lower())
            except ValueError:
                analysis_mode = AnalysisMode.FREQUENT
            
            # Get code_path from agent_config if available
            code_path = None
            if agent_config:
                code_path = agent_config.get('code_path')
            
            # Create analyzer with only valid log paths
            analyzer = LogAnalyzer(
                valid_log_paths,
                mode=analysis_mode,
                time_window_hours=final_time_window,
                max_lines=final_max_lines,
                code_path=code_path
            )
            
            # Perform analysis
            analysis = analyzer.analyze_errors_intelligent()
            
            # CRITICAL: Check if any actual errors were found
            if analysis['total_errors'] == 0:
                return json.dumps({
                    "error": "No errors found in log files",
                    "routing_decision": {
                        "should_analyze_code": False,
                        "reason": f"No errors found in valid log files in the last {final_time_window} hours"
                    },
                    "log_analysis": {
                        "analysis_type": "no_errors_found",
                        "primary_evidence": f"Analyzed {len(valid_log_paths)} log files but found no errors",
                        "error_patterns": {
                            "total_patterns": 0,
                            "most_common": "None",
                            "frequency_distribution": {}
                        },
                        "supporting_evidence": f"Time window: {final_time_window}h, Log files checked: {len(valid_log_paths)}"
                    }
                }, indent=2)
            
            # Extract code paths for routing
            code_paths = []
            for pattern in analysis['patterns']:
                if pattern.signature.code_path:
                    code_paths.append({
                        "file_path": pattern.signature.code_path,
                        "line_number": pattern.signature.line_number,
                        "function_name": pattern.signature.function_name,
                        "error_context": pattern.pattern,
                        "frequency": pattern.count,
                        "frequency_score": pattern.frequency_score
                    })
            
            # Add latest unique errors
            for error in analysis['latest_unique_errors']:
                if error.error_signature and error.error_signature.code_path:
                    # Check if already included
                    existing = any(cp["file_path"] == error.error_signature.code_path for cp in code_paths)
                    if not existing:
                        code_paths.append({
                            "file_path": error.error_signature.code_path,
                            "line_number": error.error_signature.line_number,
                            "function_name": error.error_signature.function_name,
                            "error_context": error.message,
                            "frequency": 1,
                            "frequency_score": 0.1
                        })
            
            # Determine routing decision
            should_analyze_code = len(code_paths) > 0
            target_file = code_paths[0]["file_path"] if code_paths else None
            target_line = code_paths[0]["line_number"] if code_paths else None
            target_function = code_paths[0]["function_name"] if code_paths else None
            
            # Create response
            response = {
                "log_analysis": {
                    "analysis_type": f"intelligent_{analysis_mode.value}",
                    "primary_evidence": f"Found {analysis['total_errors']} errors in last {final_time_window}h, {len(analysis['patterns'])} unique patterns",
                    "error_patterns": {
                        "total_patterns": len(analysis['patterns']),
                        "most_common": analysis['patterns'][0].pattern if analysis['patterns'] else "None",
                        "frequency_distribution": {p.pattern: p.count for p in analysis['patterns'][:5]}
                    },
                                "error_timeline": {
                "first_occurrence": analysis['patterns'][0].first_occurrence.isoformat() if analysis['patterns'] and analysis['patterns'][0].first_occurrence else None,
                "pattern": "recurring" if analysis['patterns'] and analysis['patterns'][0].count > 1 else "single",
                "last_occurrence": analysis['patterns'][0].last_occurrence.isoformat() if analysis['patterns'] and analysis['patterns'][0].last_occurrence else None
            },
                    "supporting_evidence": f"Analysis mode: {analysis_mode.value}, Time window: {final_time_window}h"
                },
                "code_path_extraction": {
                    "extracted_code_paths": code_paths,
                    "most_recent_error": {
                        "file_path": target_file,
                        "line_number": target_line,
                        "function_name": target_function,
                                            "error_message": code_paths[0]["error_context"] if code_paths else None,
                    "timestamp": analysis['patterns'][0].last_occurrence.isoformat() if analysis['patterns'] and analysis['patterns'][0].last_occurrence else None
                    },
                    "extraction_quality": "high" if code_paths else "low",
                    "analysis_summary": {
                        "total_errors": analysis['total_errors'],
                        "unique_patterns": len(analysis['patterns']),
                        "latest_unique_errors": len(analysis['latest_unique_errors']),
                        "time_window_hours": analysis['time_window_hours'],
                        "analysis_mode": analysis['analysis_mode']
                    }
                },
                "routing_decision": {
                    "should_analyze_code": should_analyze_code,
                    "reason": f"Found {len(code_paths)} code paths to analyze" if should_analyze_code else "No code paths found in logs",
                    "target_file": target_file,
                    "target_line": target_line,
                    "target_function": target_function
                }
            }
            
            return json.dumps(response, indent=2, default=str)
            
        except Exception as e:
            return json.dumps({
                "error": f"Intelligent analysis failed: {str(e)}",
                "routing_decision": {
                    "should_analyze_code": False,
                    "reason": f"Analysis error: {str(e)}"
                }
            }, indent=2)
    
    return intelligent_error_analysis_tool

# Compatibility functions that maintain the original interface
def create_grep_logs_tool(log_paths: List[str] = None, agent_config: Dict[str, Any] = None):
    """Create a grep logs tool (enhanced version with backward compatibility)."""
    enhanced_tool = create_enhanced_grep_logs_tool(log_paths, agent_config)
    
    @tool("grep_logs")
    def grep_logs_tool(query: str) -> str:
        """Search log files for specific patterns using enhanced grep.
        
        Args:
            query: The pattern to search for
            
        Returns:
            String containing the grep results
        """
        # Call enhanced version with default parameters for backward compatibility
        return enhanced_tool(query=query, context_lines=1, case_sensitive=False, regex_mode=False)
    
    return grep_logs_tool

def create_filter_logs_tool(log_paths: List[str] = None, agent_config: Dict[str, Any] = None):
    """Create a filter logs tool (enhanced version with backward compatibility)."""
    enhanced_tool = create_enhanced_filter_logs_tool(log_paths, agent_config)
    
    @tool("filter_logs")
    def filter_logs_tool(error_level: str = None) -> str:
        """Filter log files by error level.
        
        Args:
            error_level: Error level to filter by (ERROR, WARN, INFO, DEBUG)
            
        Returns:
            String containing the filtered log entries
        """
        # Call enhanced version with default parameters for backward compatibility
        return enhanced_tool(error_level=error_level)
    
    return filter_logs_tool

def create_extract_stack_traces_tool(log_paths: List[str] = None, agent_config: Dict[str, Any] = None):
    """Create an extract stack traces tool (enhanced version with backward compatibility)."""
    enhanced_tool = create_enhanced_extract_stack_traces_tool(log_paths, agent_config)
    
    @tool("extract_stack_traces")
    def extract_stack_traces_tool(filter_term: str = None) -> str:
        """Extract stack traces from log files.
        
        Args:
            filter_term: Optional term to filter stack traces
            
        Returns:
            String containing the extracted stack traces
        """
        # Call enhanced version for backward compatibility
        return enhanced_tool(filter_term=filter_term)
    
    return extract_stack_traces_tool

# Legacy functions for backward compatibility
def grep_logs(query: str, log_paths: List[str] = None) -> str:
    """Legacy function - use create_enhanced_grep_logs_tool instead."""
    tool = create_enhanced_grep_logs_tool(log_paths)
    return tool(query)

def filter_logs(log_paths: List[str] = None, **kwargs) -> str:
    """Legacy function - use create_enhanced_filter_logs_tool instead."""
    error_level = kwargs.get('error_level')
    tool = create_enhanced_filter_logs_tool(log_paths)
    return tool(error_level)

def extract_stack_traces(log_paths: List[str] = None, **kwargs) -> str:
    """Legacy function - use create_enhanced_extract_stack_traces_tool instead."""
    filter_term = kwargs.get('filter_term')
    tool = create_enhanced_extract_stack_traces_tool(log_paths)
    return tool(filter_term)    
