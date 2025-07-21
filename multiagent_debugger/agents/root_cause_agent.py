from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import re

from crewai import Agent
from crewai.tools import tool
from crewai.tools import BaseTool
from typing import Dict, Any, List, Optional
import os

from multiagent_debugger.utils import get_verbose_flag, create_crewai_llm, get_agent_llm_config

def create_clean_error_flow_tool():
    """Create a tool for generating clean, copyable error flow charts."""
    @tool("create_clean_error_flow")
    def create_clean_error_flow(error_type: str, error_message: str, components: str, timeline: str, severity: str) -> str:
        """Create a clean, copyable error flow chart in Mermaid format.
        
        Args:
            error_type: Type of error (e.g., "authentication", "database", "file_access")
            error_message: The specific error message
            components: Systems/components involved
            timeline: When the error occurred
            severity: Error severity level
            
        Returns:
            Clean Mermaid code for the error flow chart
        """
        try:
            # Create a cleaner, more concise Mermaid diagram
            mermaid_code = f"""graph LR
    A[🚨 {error_type.title()} Error] --> B[🔍 {error_message}]
    B --> C[💡 {components}]
    C --> D[✅ Resolved]
    
    style A fill:#ffebee,stroke:#f44336,stroke-width:2px
    style B fill:#fff3e0,stroke:#ff9800,stroke-width:2px
    style C fill:#e8f5e8,stroke:#4caf50,stroke-width:2px
    style D fill:#e3f2fd,stroke:#2196f3,stroke-width:2px"""
            
            return f"✅ Clean Error Flow Chart Generated:\n\n```mermaid\n{mermaid_code}\n```\n\n📋 Copy the code above and paste it into any Mermaid-compatible editor!"
            
        except Exception as e:
            return f"❌ Error generating clean flowchart: {str(e)}"
    
    return create_clean_error_flow

def create_minimal_error_flow_tool():
    """Create a tool for generating ultra-clean, minimal error flow charts."""
    @tool("create_minimal_error_flow")
    def create_minimal_error_flow(error_type: str, error_message: str, components: str, timeline: str, severity: str) -> str:
        """Create an ultra-clean, minimal error flow chart in Mermaid format.
        
        Args:
            error_type: Type of error (e.g., "authentication", "database", "file_access")
            error_message: The specific error message
            components: Systems/components involved
            timeline: When the error occurred
            severity: Error severity level
            
        Returns:
            Minimal Mermaid code for the error flow chart
        """
        try:
            # Create an ultra-clean, minimal Mermaid diagram
            mermaid_code = f"""graph LR
    A[Error: {error_type.title()}] --> B[Issue: {error_message}]
    B --> C[Fix: {components}]
    C --> D[✅ Done]
    
    style A fill:#ffebee
    style B fill:#fff3e0
    style C fill:#e8f5e8
    style D fill:#e3f2fd"""
            
            return f"✅ Minimal Error Flow Chart Generated:\n\n```mermaid\n{mermaid_code}\n```\n\n📋 Copy the code above and paste it into any Mermaid-compatible editor!"
            
        except Exception as e:
            return f"❌ Error generating minimal flowchart: {str(e)}"
    
    return create_minimal_error_flow

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
        provider, model, temperature, api_key, api_base, additional_params = get_agent_llm_config(self.llm_config)
        verbose = get_verbose_flag(self.config)
        
        # Create LLM
        llm = create_crewai_llm(provider, model, temperature, api_key, api_base, additional_params)
        
        # Add the clean error flow tool to the tools list
        if tools is None:
            tools = []
        tools.append(create_clean_error_flow_tool())
        tools.append(create_minimal_error_flow_tool())
        
        try:
            agent = Agent(
                role="Root Cause Analyst",
                goal="Synthesize findings from all agents to identify root causes and provide actionable solutions",
                backstory="You are a root cause analyst who combines log analysis, code analysis, and error patterns to determine the definitive cause of issues.",
                verbose=verbose,
                allow_delegation=False,
                tools=tools or [],
                llm=llm,
                max_iter=1,
                memory=False,
                instructions="""
                Synthesize findings from all agents to identify root causes and provide solutions:
                
                1. Combine log analysis, code analysis, and error patterns
                2. Identify the definitive root cause of the issue
                3. Provide actionable fixes with specific steps
                4. Generate visual flowcharts to illustrate the problem and solution
                
                OUTPUT FORMAT (JSON):
                {
                  "root_cause_analysis": {
                    "primary_cause": "[definitive technical explanation]",
                    "confidence_level": "[high|medium|low]",
                    "contributing_factors": ["list of contributing factors"],
                    "error_chain": ["sequence of events"]
                  },
                  "solution_roadmap": {
                    "immediate_fixes": [
                      {
                        "action": "[specific action]",
                        "file": "[file:line reference]",
                        "description": "[what to change]",
                        "impact": "[what this will solve]"
                      }
                    ],
                    "long_term_improvements": ["list of improvements"],
                    "testing_steps": ["how to verify the fix"]
                  },
                  "flowchart_data": {
                    "error_flow": "[mermaid code from create_clean_error_flow or create_minimal_error_flow tool]",
                    "flowchart_style": "[clean|minimal]"
                  },
                  "synthesis_summary": {
                    "classification": "[Error type]",
                    "evidence_quality": "[Strong/Medium/Weak]",
                    "fix_complexity": "[simple|moderate|complex]"
                  }
                }
                
                FLOWCHART GENERATION:
                - Use create_clean_error_flow for detailed flowcharts
                - Use create_minimal_error_flow for simple flowcharts
                - Keep flowchart text concise
                - Show error propagation path and solution steps
                
                RULES:
                - CRITICAL: Only use exact information from previous agents
                - NEVER fabricate or hallucinate root cause analysis
                - If no real errors found in logs, return error: "No errors found in log files"
                - If no code files analyzed, return error: "No code files available for analysis"
                - Only generate flowcharts when real data exists
                - Be concise and developer-friendly
                - Provide actionable next steps only when real data supports them
                - If insufficient data, say "Insufficient data for root cause analysis"
                """
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