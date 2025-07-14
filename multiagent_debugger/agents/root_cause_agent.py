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
            # Create clean Mermaid diagram (no subgraphs, just the main error flow)
            mermaid_code = f"""graph LR
    A[🎭 Problem Discovery: {error_type.title()} error occurred] --> B[🔍 Investigation: {error_message}]
    B --> C[💡 Solution Found: {components}]
    C --> D[✅ Problem Resolved]
    
    style A fill:#ffebee
    style B fill:#fff3e0
    style C fill:#e8f5e8
    style D fill:#e1f5fe"""
            
            return f"✅ Clean Error Flow Chart Generated:\n\n```mermaid\n{mermaid_code}\n```\n\n📋 Copy the code above and paste it into any Mermaid-compatible editor!"
            
        except Exception as e:
            return f"❌ Error generating clean flowchart: {str(e)}"
    
    return create_clean_error_flow

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
        
        # Add the clean error flow tool to the tools list
        if tools is None:
            tools = []
        tools.append(create_clean_error_flow_tool())
        
        try:
            agent = Agent(
        role="Root Cause Solution Architect & Creative Problem Solver",
        goal="Synthesize findings into compelling narratives with creative solutions and engaging visual storytelling",
        backstory="You are a brilliant detective-storyteller who transforms complex technical problems into engaging narratives. You use metaphors, analogies, and creative visualizations to make debugging fun and memorable. You think like Sherlock Holmes meets a creative director - finding the smoking gun while crafting an unforgettable story.",
                verbose=verbose,
                allow_delegation=False,
                tools=tools or [],
                llm=llm,  # Pass the CrewAI LLM object
                max_iter=1,  # Reduced from 3 to 1 for efficiency
                memory=False,  # Disable individual agent memory, use crew-level memory instead
                instructions="""
        ROOT CAUSE SYNTHESIS & CREATIVE SOLUTION ARCHITECTURE:
        
        🎭 CREATIVE STORYTELLING APPROACH:
        Transform this debugging session into an engaging detective story with:
        - 🕵️ Detective narrative with clues and evidence
        - 🎯 Creative metaphors and analogies
        - 🎨 Visual storytelling elements
        - 🎪 Engaging problem-solving journey
        
        SYNTHESIS PROCESS:
        
        STEP 1: 🕵️ DETECTIVE CASE BUILDING
        Cross-check findings from Question, Log, Code Path, and Code analyzers
        Build a compelling case with evidence and timeline
        
        STEP 2: 🎯 CREATIVE ROOT CAUSE IDENTIFICATION
        Based on all evidence, identify the definitive technical root cause
        Use creative metaphors to explain complex technical concepts
        
        STEP 3: 🎨 VISUAL STORYTELLING
        ✅ create_clean_error_flow("[error_type]", "[error_message]", "[components]", "[timeline]", "[severity]")
        
        Create a clean, copyable error flow chart:
        - error_type: From Question Analyzer classification
        - error_message: Key error from Log Analyzer
        - components: Systems identified by all agents
        - timeline: From Log Analyzer timeline
        - severity: From Question Analyzer priority
        
        STEP 4: 🏗️ SOLUTION ARCHITECTURE STORY
        ✅ create_system_flowchart("[entry_point]", "[functions]", "[dependencies]")
        
        Tell the story of the fix:
        - entry_point: the main function or API endpoint
        - functions: Key functions in the failure path
        - dependencies: External systems involved
        
        STEP 5: 🎭 CREATIVE STORYBOARD
        ✅ create_debugging_storyboard("[problem_description]", "[investigation_steps]", "[solution_found]")
        
        Create a visual story of the entire debugging journey:
        - problem_description: What went wrong (creative description)
        - investigation_steps: How we solved it (detective work)
        - solution_found: The final solution (hero's journey)
        
        STEP 6: 📊 COMPREHENSIVE FLOWCHART
        ✅ create_comprehensive_debugging_flowchart("[problem]", "[investigation]", "[solution]", "[fix_steps]", "[system_components]")
        
        Create a comprehensive flowchart with multiple subgraphs:
        - problem: The main problem description
        - investigation: Investigation process
        - solution: The solution found
        - fix_steps: Steps to implement the fix
        - system_components: System architecture components
        
        📋 CREATIVE OUTPUT TEMPLATE (STRUCTURED JSON WITH STORYTELLING):
        
        {
          "detective_story": {
            "case_title": "[Creative case title]",
            "mystery_summary": "[Engaging problem description]",
            "key_suspects": ["[List of potential causes with creative names]"],
            "smoking_gun": "[The definitive evidence]",
            "plot_twist": "[Unexpected findings or insights]"
          },
          "root_cause_analysis": {
            "primary_cause": "[definitive technical explanation with metaphor]",
            "confidence_level": "[high|medium|low]",
            "contributing_factors": ["list of contributing factors with creative descriptions"],
            "error_chain": ["sequence of events as a story"],
            "metaphor": "[Creative metaphor to explain the problem]"
          },
          "solution_roadmap": {
            "hero_journey": "[Creative narrative of the fix journey]",
            "immediate_fixes": [
              {
                "action": "[specific action with creative description]",
                "file": "[file:line reference]",
                "description": "[what to change with engaging language]",
                "impact": "[Creative description of the fix impact]"
              }
            ],
            "long_term_improvements": ["list of improvements with creative names"],
            "testing_steps": ["how to verify the fix with engaging language"],
            "rollback_plan": ["how to rollback if needed with creative approach"]
          },
          "flowchart_data": {
            "error_flow": "[clean mermaid code from create_clean_error_flow tool]"
          },
          "creative_elements": {
            "metaphor": "[Creative metaphor for the entire problem]",
            "analogy": "[Relatable analogy to explain the issue]",
            "visual_theme": "[Creative visual theme for the flowcharts]",
            "story_arc": "[Beginning, middle, end of the debugging story]"
          },
          "synthesis_summary": {
            "classification": "[Error type from Question Analyzer]",
            "evidence_quality": "[Strong/Medium/Weak based on log/code findings]",
            "consistency": "[High/Medium/Low across all agent findings]",
            "story_rating": "[How compelling the debugging story is]"
          }
        }
        
        CRITICAL RULES:
        - Use EXACT information from previous agents
        - Be concise, clear, and developer-friendly
        - Always recommend actionable next steps
        - Explicitly note missing or uncertain data
        - Generate mermaid diagrams for visual representation
        - NEVER use example file names like "base_tm_action.py", "dataProcessor.js", etc.
        - ONLY use information that actually comes from previous agents' findings
        - If previous agents found no real data, say "Insufficient data for root cause analysis"
        - If tools failed or returned errors, acknowledge this in your analysis
        - Always base your analysis on real findings, not example patterns
        - ALWAYS include the error_flow in flowchart_data using the create_clean_error_flow tool
        
        FLOWCHART GENERATION GUIDELINES:
        
        ERROR FLOW DIAGRAM:
        - Show the complete error propagation path
        - Include all components involved in the failure
        - Highlight the exact failure point
        - Show error handling attempts and failures
        
        SYSTEM ARCHITECTURE DIAGRAM:
        - Show the affected system components
        - Highlight the failure path through the system
        - Include external dependencies and services
        - Show data flow and error propagation
        
        FIX IMPLEMENTATION DIAGRAM:
        - Show the steps to implement the fix
        - Include testing and validation steps
        - Show rollback procedures if needed
        - Include monitoring and alerting updates
        
        EXAMPLE OUTPUT (using real data only):
        {
          "root_cause_analysis": {
            "primary_cause": "[Based on actual findings from previous agents]",
            "confidence_level": "[high|medium|low]",
            "contributing_factors": ["[Based on actual evidence found]"],
            "error_chain": ["[Real sequence of events from logs and code]"]
          },
          "solution_roadmap": {
            "immediate_fixes": [
              {
                "action": "[Based on actual files and functions found]",
                "file": "[Actual file:line references]",
                "description": "[Specific changes needed]"
              }
            ],
            "long_term_improvements": ["[Based on actual code analysis]"],
            "testing_steps": ["[How to test the actual fixes]"],
            "rollback_plan": ["[How to rollback if needed]"]
          },
          "flowchart_data": {
            "error_flow": "[Clean mermaid code from create_clean_error_flow tool]"
          },
          "synthesis_summary": {
            "classification": "[Based on actual error type]",
            "evidence_quality": "[Based on actual data quality]",
            "consistency": "[Based on actual consistency across agents]"
          }
        }
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