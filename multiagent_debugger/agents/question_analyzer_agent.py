from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import re
import os

from crewai import Agent
from langchain.tools import BaseTool

from multiagent_debugger.utils import get_verbose_flag, create_langchain_llm, get_agent_llm_config

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
        
        # Create the appropriate LangChain LLM based on provider
        llm = create_langchain_llm(provider, model, temperature, api_key, api_base)
        
        # Debug: Print LLM info
        print(f"DEBUG: Using {provider} LLM: {model} with temperature {temperature}")
        
        try:
            agent = Agent(
                role="Question Analyzer",
                goal="Extract key entities and parameters from user questions about API failures",
                backstory="""You are an expert at understanding user questions about API and service failures.
                Your job is to extract key information like API routes, user IDs, timestamps, and error types
                from natural language questions.""",
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