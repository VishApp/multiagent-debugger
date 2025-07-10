import os
from typing import Dict, Any, List, Optional

from crewai import Crew, Task, Agent, Process
from crewai.tools import tool

from multiagent_debugger.agents.question_analyzer_agent import QuestionAnalyzerAgent
from multiagent_debugger.agents.log_agent import LogAgent
from multiagent_debugger.agents.code_agent import CodeAgent
from multiagent_debugger.agents.root_cause_agent import RootCauseAgent

from multiagent_debugger.tools.log_tools import create_grep_logs_tool, create_filter_logs_tool, create_extract_stack_traces_tool
from multiagent_debugger.tools.code_tools import create_find_api_handlers_tool, create_find_dependencies_tool, create_find_error_handlers_tool
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
                print(f"DEBUG: Set {env_var_name} at crew level")
            else:
                print(f"WARNING: No environment variable found for provider {provider}")
        
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
        
        # Create CrewAI agents with retry configuration
        self.question_analyzer_agent = self.question_analyzer.create_agent()
        self.log_agent_agent = self.log_agent.create_agent(tools=self.log_tools)
        self.code_agent_agent = self.code_agent.create_agent(tools=self.code_tools)
        self.root_cause_agent_agent = self.root_cause_agent.create_agent()
        
        # Create crew
        self.crew = self._create_crew()
    
    def _create_log_tools(self) -> List:
        """Create tools for log analysis."""
        return [
            create_grep_logs_tool(self.log_paths),
            create_filter_logs_tool(self.log_paths),
            create_extract_stack_traces_tool(self.log_paths)
        ]
    
    def _create_code_tools(self) -> List:
        """Create tools for code analysis."""
        return [
            create_find_api_handlers_tool(self.code_path),
            create_find_dependencies_tool(self.code_path),
            create_find_error_handlers_tool(self.code_path)
        ]
    
    def _create_crew(self) -> Crew:
        """Create and return a CrewAI crew.
        
        Returns:
            Crew: The configured CrewAI crew
        """
        # Create crew with retry configuration
        crew = Crew(
            agents=[
                self.question_analyzer_agent,
                self.log_agent_agent,
                self.code_agent_agent,
                self.root_cause_agent_agent
            ],
            tasks=self._create_tasks(""),  # Placeholder, will be replaced in debug()
            verbose=True,
            process=Process.sequential,  # Use sequential process
            max_rpm=10,  # Maximum requests per minute
            max_iter=3,  # Maximum iterations for each task
            memory=False,  # Disable memory to avoid API key issues
            cache=False,   # Disable cache to avoid API key issues
        )
        
        return crew
    
    def debug(self, question: str) -> str:
        """Run the debugging process.
        
        Args:
            question: The debugging question to answer
            
        Returns:
            String containing the debugging result
        """
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
        
        # Handle the result correctly
        if hasattr(result, 'raw_output'):
            return result.raw_output
        elif isinstance(result, str):
            return result
        else:
            return str(result)
    
    def _create_tasks(self, question: str) -> List[Task]:
        """Create tasks for the debugging process.
        
        Args:
            question: The debugging question to answer
            
        Returns:
            List of CrewAI Task objects
        """
        # Task 1: Analyze the question
        analyze_task = Task(
            description=f"Analyze the following debugging question: '{question}'. Determine what information is needed to answer it.",
            agent=self.question_analyzer_agent,
            expected_output="A detailed analysis of the question and what information is needed to answer it.",
            max_iter=3,  # Retry up to 3 times if task fails
            async_execution=False,  # Run synchronously for better error handling
        )
        
        # Task 2: Search logs for relevant information
        log_task = Task(
            description="Search logs for information related to the question. Use the grep_logs, filter_logs, and extract_stack_traces tools as needed.",
            agent=self.log_agent_agent,
            expected_output="Relevant log entries that might help answer the question.",
            context=[analyze_task],
            max_iter=3,  # Retry up to 3 times if task fails
            async_execution=False,  # Run synchronously for better error handling
        )
        
        # Task 3: Analyze code for relevant information
        code_task = Task(
            description="Analyze the codebase for information related to the question. Use the find_api_handlers, find_dependencies, and find_error_handlers tools as needed.",
            agent=self.code_agent_agent,
            expected_output="Relevant code that might help answer the question.",
            context=[analyze_task],
            max_iter=3,  # Retry up to 3 times if task fails
            async_execution=False,  # Run synchronously for better error handling
        )
        
        # Task 4: Determine root cause
        root_cause_task = Task(
            description="Based on the analysis from previous tasks, determine the root cause of the API failure.",
            agent=self.root_cause_agent_agent,
            expected_output="A clear explanation of the root cause of the API failure.",
            context=[analyze_task, log_task, code_task],
            max_iter=3,  # Retry up to 3 times if task fails
            async_execution=False,  # Run synchronously for better error handling
        )
        
        return [analyze_task, log_task, code_task, root_cause_task] 