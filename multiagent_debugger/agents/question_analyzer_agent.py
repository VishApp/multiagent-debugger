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
        provider, model, temperature, api_key, api_base, additional_params = get_agent_llm_config(self.llm_config)
        verbose = get_verbose_flag(self.config)
        # Create LLM
        try:
            llm = create_crewai_llm(provider, model, temperature, api_key, api_base, additional_params)
            # Debug: Print LLM info
            print(f"INFO: Using {provider} LLM: {model} with temperature {temperature}")
        except Exception as e:
            print(f"ERROR: Failed to create LLM in QuestionAnalyzerAgent: {e}")
            import traceback
            print("Full traceback:")
            print(traceback.format_exc())
            raise
        
        try:
            agent = Agent(
                role="Error Pattern Detective",
                goal="Extract error classification and analysis tasks from user questions",
                backstory="You are a detective who analyzes user questions to identify error types, severity, and investigation requirements.",
                verbose=verbose,
                allow_delegation=False,
                tools=tools or [],
                llm=llm,
                max_iter=1,
                memory=False,
                instructions="""
                Extract key information from user questions for debugging:
                
                1. Error classification (type, severity, description)
                2. Log analysis tasks (search terms, time window, focus areas)
                3. Code analysis tasks (files, functions, patterns)
                4. Investigation roadmap (priority, next steps)
                
                OUTPUT FORMAT (JSON):
                {
                  "error_classification": {
                    "type": "[API|Database|File|Network|Script|OS|Memory|Auth|Config]",
                    "severity": "[P0-Critical|P1-Urgent|P2-High|P3-Medium]",
                    "description": "[Brief error description]"
                  },
                  "log_analysis_tasks": {
                    "search_terms": ["primary_term", "secondary_term"],
                    "time_window": "[if specified]",
                    "focus_areas": ["error_patterns", "stack_traces"]
                  },
                  "code_analysis_tasks": {
                    "files": ["specific_files_if_mentioned"],
                    "functions": ["specific_functions_if_mentioned"],
                    "patterns": ["error_patterns_to_look_for"]
                  },
                  "investigation_roadmap": {
                    "priority": "[high|medium|low]",
                    "next_steps": ["step1", "step2", "step3"]
                  }
                }
                
                RULES:
                - Only extract information EXPLICITLY mentioned in the user's question
                - Never invent file names, function names, or paths
                - If no specific details mentioned, mark as "not_specified"
                - Be concise and developer-friendly
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