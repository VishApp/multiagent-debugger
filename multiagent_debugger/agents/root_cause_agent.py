from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import re

from crewai import Agent
from crewai.tools import tool
from crewai.tools import BaseTool
from typing import Dict, Any, List, Optional
import os

from multiagent_debugger.utils import get_verbose_flag, create_crewai_llm, get_agent_llm_config

class RootCauseAgent:
    """Agent that determines the root cause of API failures."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the RootCauseAgent.
        
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
        
        try:
            agent = Agent(
                role="Root Cause Analyzer",
                goal="Determine the root cause of API failures based on analysis from other agents",
                backstory="""You are an expert at determining the root cause of API failures.
                You analyze information from log analysis and code analysis to identify
                the underlying cause of failures and provide clear explanations. Be concise and actionable.""",
                verbose=verbose,
                allow_delegation=False,
                tools=tools or [],
                llm=llm,  # Pass the CrewAI LLM object
                max_iter=1,  # Reduced from 3 to 1 for efficiency
                memory=False,  # Disable individual agent memory, use crew-level memory instead
            )
            return agent
        except Exception as e:
            import traceback
            print(f"ERROR: Failed to create CrewAI Agent: {e}")
            print(traceback.format_exc())
            raise
    
    def generate_explanation(self, question: str, entities: Dict[str, Any], 
                           log_results: Dict[str, Any], code_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a root cause explanation based on the analysis results.
        
        Args:
            question: The original user question
            entities: Dictionary of entities extracted from the user's question
            log_results: Results from log analysis
            code_results: Results from code analysis
            
        Returns:
            Dict containing the root cause explanation and confidence rating
        """
        # This would be implemented as a task for the agent
        # For now, we'll provide a simple implementation
        results = {
            "explanation": "",
            "confidence": 0.0,
            "suggested_actions": []
        }
        
        # Check if we have enough information
        if not log_results.get("matching_logs") and not code_results.get("api_handlers"):
            results["explanation"] = "Insufficient information to determine the root cause. " \
                                    "No relevant logs or code handlers were found."
            results["confidence"] = 0.0
            results["suggested_actions"] = [
                "Check if the provided log paths and code path are correct.",
                "Verify that the API route and user ID in the question are accurate.",
                "Try expanding the time window for log analysis."
            ]
            return results
        
        # Synthesize findings
        explanation_parts = []
        
        # Add information from logs
        if log_results.get("error_logs"):
            explanation_parts.append(f"Found {len(log_results['error_logs'])} error logs related to the issue.")
            # Include most relevant error message
            if log_results["error_logs"]:
                explanation_parts.append(f"Most relevant error: {log_results['error_logs'][0]}")
        
        # Add information from code analysis
        if code_results.get("api_handlers"):
            explanation_parts.append(f"Found {len(code_results['api_handlers'])} API handlers that could be involved.")
            # Include most relevant handler
            if code_results["api_handlers"]:
                handler = code_results["api_handlers"][0]
                explanation_parts.append(f"Most relevant handler: {handler['name']} at line {handler['line_number']}")
        
        # Add information about dependencies
        if code_results.get("dependencies"):
            explanation_parts.append(f"The API depends on the following modules: {', '.join(code_results['dependencies'])}")
        
        # Add information about error handlers
        if code_results.get("error_handlers"):
            explanation_parts.append(f"Found {len(code_results['error_handlers'])} error handlers in the code.")
        
        # Set confidence based on available information
        if log_results.get("error_logs") and code_results.get("api_handlers"):
            confidence = 0.8  # High confidence if we have both logs and code
        elif log_results.get("error_logs"):
            confidence = 0.6  # Medium-high confidence if we have logs but no code
        elif code_results.get("api_handlers"):
            confidence = 0.4  # Medium-low confidence if we have code but no logs
        else:
            confidence = 0.2  # Low confidence if we have neither
        
        # Generate suggested actions
        suggested_actions = [
            "Review the error logs in detail to understand the exact failure point.",
            "Check if the API is correctly handling the specific user ID mentioned.",
            "Verify that all dependencies are available and functioning correctly."
        ]
        
        # If we found specific error handlers, suggest reviewing them
        if code_results.get("error_handlers"):
            suggested_actions.append("Review the error handling code to ensure it's properly catching and reporting errors.")
        
        # Combine all parts into a coherent explanation
        results["explanation"] = "\n".join(explanation_parts)
        results["confidence"] = confidence
        results["suggested_actions"] = suggested_actions
        
        return results 