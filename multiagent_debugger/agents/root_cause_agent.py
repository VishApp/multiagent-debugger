from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import re

from crewai import Agent
from langchain.tools import BaseTool

from multiagent_debugger.utils import get_verbose_flag, create_langchain_llm, get_agent_llm_config

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
        
        # Create the appropriate LangChain LLM based on provider
        llm = create_langchain_llm(provider, model, temperature, api_key, api_base)
        
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
                llm=llm,  # Pass the LangChain LLM object
                max_iter=1,  # Reduced from 3 to 1 for efficiency
                memory=True,  # Enable memory for better context retention
            )
            return agent
        except Exception as e:
            import traceback
            print(f"ERROR: Failed to create CrewAI Agent: {e}")
            print(traceback.format_exc())
            raise
    
    def _create_langchain_llm(self, provider: str, model: str, temperature: float, api_key: str = None, api_base: str = None):
        """Create the appropriate LangChain LLM based on provider."""
        if provider == "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model,
                temperature=temperature,
                openai_api_key=api_key,
                openai_api_base=api_base
            )
        elif provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=model,
                temperature=temperature,
                anthropic_api_key=api_key
            )
        elif provider == "google":
            from langchain_google_vertexai import ChatVertexAI
            return ChatVertexAI(
                model_name=model,
                temperature=temperature
            )
        elif provider == "mistral":
            from langchain_mistralai import ChatMistralAI
            return ChatMistralAI(
                model=model,
                temperature=temperature,
                mistral_api_key=api_key
            )
        elif provider == "cohere":
            from langchain_cohere import ChatCohere
            return ChatCohere(
                model=model,
                temperature=temperature,
                cohere_api_key=api_key
            )
        else:
            # Fallback to OpenAI
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model,
                temperature=temperature,
                openai_api_key=api_key,
                openai_api_base=api_base
            )
    
    def _get_llm_config(self) -> Dict[str, Any]:
        """Get the LLM configuration based on the provider."""
        # Handle both dict and LLMConfig objects
        if hasattr(self.llm_config, 'provider'):
            provider = self.llm_config.provider.lower()
        else:
            provider = self.llm_config.get("provider", "openai").lower()
            
        if hasattr(self.llm_config, 'model_name'):
            model = self.llm_config.model_name
        else:
            model = self.llm_config.get("model_name", "gpt-4")
            
        if hasattr(self.llm_config, 'temperature'):
            temperature = self.llm_config.temperature
        else:
            temperature = self.llm_config.get("temperature", 0.1)
            
        if hasattr(self.llm_config, 'api_key'):
            api_key = self.llm_config.api_key
        else:
            api_key = self.llm_config.get("api_key")
            
        if hasattr(self.llm_config, 'api_base'):
            api_base = self.llm_config.api_base
        else:
            api_base = self.llm_config.get("api_base")
        
        # Default config for OpenAI
        if provider == "openai":
            config = {
                "config_list": [{"model": model, "api_key": api_key}],
                "temperature": temperature,
            }
            if api_base:
                config["config_list"][0]["api_base"] = api_base
        # Add provider-specific configurations
        elif provider == "anthropic":
            config = {
                "config_list": [{"model": model}],
                "temperature": temperature,
                "api_key": api_key,
                "anthropic_api_key": api_key,
                "anthropic_api_url": api_base,
            }
        elif provider == "google":
            config = {
                "config_list": [{"model": model}],
                "temperature": temperature,
                "api_key": api_key,
                "google_api_key": api_key,
            }
        elif provider == "ollama":
            config = {
                "config_list": [{"model": model}],
                "temperature": temperature,
                "api_base_url": api_base or "http://localhost:11434",
            }
        else:
            # Default to OpenAI if provider is not recognized
            config = {
                "config_list": [{"model": model, "api_key": api_key}],
                "temperature": temperature,
            }
            if api_base:
                config["config_list"][0]["api_base"] = api_base
        
        return config
    
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
        
        # Add information from stack traces
        if log_results.get("stack_traces"):
            explanation_parts.append(f"Found {len(log_results['stack_traces'])} stack traces.")
            # Include most relevant stack trace
            if log_results["stack_traces"]:
                explanation_parts.append(f"Most relevant stack trace: {log_results['stack_traces'][0]}")
        
        # Add information from code analysis
        if code_results.get("api_handlers"):
            explanation_parts.append(f"Found {len(code_results['api_handlers'])} API handlers for the route.")
            # Include most relevant handler
            if code_results["api_handlers"]:
                handler = code_results["api_handlers"][0]
                explanation_parts.append(f"API is handled by function '{handler['name']}' in file '{handler['file_path']}'.")
        
        # Add information about error handlers
        if code_results.get("error_handlers"):
            explanation_parts.append(f"Found {len(code_results['error_handlers'])} error handlers in the code.")
        
        # Add information about dependencies
        if code_results.get("dependencies"):
            explanation_parts.append(f"The API depends on {len(code_results['dependencies'])} modules/services: " +
                                    f"{', '.join(code_results['dependencies'][:5])}" +
                                    f"{' and others' if len(code_results['dependencies']) > 5 else ''}.")
        
        # Determine confidence based on available information
        confidence = 0.0
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