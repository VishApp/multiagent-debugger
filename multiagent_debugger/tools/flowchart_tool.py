import os
import json
import base64
from typing import Dict, Any, List
from crewai.tools import tool
import requests
from pathlib import Path

# Global cache to prevent repeated tool calls
_flowchart_cache = {}

def create_error_flowchart_tool():
    """Create a tool for generating error flowcharts as images."""
    @tool("create_error_flowchart")
    def create_error_flowchart(error_type: str, error_message: str, components: str, timeline: str, severity: str) -> str:
        """Create a visual error flowchart as an image.
        
        Args:
            error_type: Type of error (e.g., "authentication", "database", "file_access")
            error_message: The specific error message
            components: Systems/components involved
            timeline: When the error occurred
            severity: Error severity level
            
        Returns:
            Path to the generated flowchart image
        """
        try:
            # Create Mermaid diagram
            mermaid_code = f"""
graph TD
    A[🚀 Initial Request] --> B[⚙️ {components}]
    B --> C[🔍 Validation Process]
    C --> D[🔴 ERROR: {error_type.upper()}]
    D --> E[📝 {error_message}]
    E --> F[⚠️ Severity: {severity}]
    F --> G[⏰ Time: {timeline}]
    
    style A fill:#e1f5fe
    style B fill:#f3e5f5
    style C fill:#fff3e0
    style D fill:#ffebee
    style E fill:#ffebee
    style F fill:#fff8e1
    style G fill:#e8f5e8
            """
            
            # Generate image using Mermaid API
            image_path = _generate_mermaid_image(mermaid_code, "error_flowchart")
            
            return f"✅ Error Flowchart generated: {image_path}\n\n📊 Mermaid Code:\n```mermaid\n{mermaid_code}\n```"
            
        except Exception as e:
            return f"❌ Error generating flowchart: {str(e)}"
    
    return create_error_flowchart

def create_system_flowchart_tool():
    """Create a tool for generating system architecture flowcharts as images."""
    @tool("create_system_flowchart")
    def create_system_flowchart(entry_point: str, functions: str, dependencies: str) -> str:
        """Create a visual system architecture flowchart as an image.
        
        Args:
            entry_point: Main entry point or API endpoint
            functions: Key functions in the system
            dependencies: External dependencies
            
        Returns:
            Path to the generated flowchart image
        """
        try:
            # Create Mermaid diagram
            mermaid_code = f"""
graph LR
    A[🌐 {entry_point}] --> B[⚙️ Core Functions]
    B --> C[🔧 {functions}]
    C --> D[🔗 External Dependencies]
    D --> E[🌍 {dependencies}]
    
    subgraph "System Components"
        B
        C
    end
    
    subgraph "External Systems"
        D
        E
    end
    
    style A fill:#e3f2fd
    style B fill:#f1f8e9
    style C fill:#fff3e0
    style D fill:#fce4ec
    style E fill:#f3e5f5
            """
            
            # Generate image using Mermaid API
            image_path = _generate_mermaid_image(mermaid_code, "system_flowchart")
            
            return f"✅ System Flowchart generated: {image_path}\n\n📊 Mermaid Code:\n```mermaid\n{mermaid_code}\n```"
            
        except Exception as e:
            return f"❌ Error generating flowchart: {str(e)}"
    
    return create_system_flowchart

def create_decision_flowchart_tool():
    """Create a tool for generating decision flowcharts as images."""
    @tool("create_decision_flowchart")
    def create_decision_flowchart(decision_point: str, options: str, outcomes: str) -> str:
        """Create a visual decision flowchart as an image.
        
        Args:
            decision_point: The main decision to be made
            options: Available options/choices
            outcomes: Possible outcomes
            
        Returns:
            Path to the generated flowchart image
        """
        try:
            # Create Mermaid diagram
            mermaid_code = f"""
graph TD
    A[🤔 {decision_point}] --> B{options}
    B --> C[✅ Success Path]
    B --> D[❌ Failure Path]
    C --> E[🎯 {outcomes}]
    D --> F[🔄 Retry/Recovery]
    
    style A fill:#fff3e0
    style B fill:#e8f5e8
    style C fill:#e1f5fe
    style D fill:#ffebee
    style E fill:#f3e5f5
    style F fill:#fff8e1
            """
            
            # Generate image using Mermaid API
            image_path = _generate_mermaid_image(mermaid_code, "decision_flowchart")
            
            return f"✅ Decision Flowchart generated: {image_path}\n\n📊 Mermaid Code:\n```mermaid\n{mermaid_code}\n```"
            
        except Exception as e:
            return f"❌ Error generating flowchart: {str(e)}"
    
    return create_decision_flowchart

def create_sequence_flowchart_tool():
    """Create a tool for generating sequence flowcharts as images."""
    @tool("create_sequence_flowchart")
    def create_sequence_flowchart(actors: str, steps: str, interactions: str) -> str:
        """Create a visual sequence flowchart as an image.
        
        Args:
            actors: System actors/components
            steps: Sequence of steps
            interactions: Interactions between actors
            
        Returns:
            Path to the generated flowchart image
        """
        try:
            # Create Mermaid diagram
            mermaid_code = f"""
sequenceDiagram
    participant U as 👤 User
    participant A as ⚙️ {actors}
    participant S as 🔧 System
    
    U->>A: Request
    A->>S: Process
    S->>A: Response
    A->>U: Result
    
    Note over A,S: {steps}
    Note over U,A: {interactions}
            """
            
            # Generate image using Mermaid API
            image_path = _generate_mermaid_image(mermaid_code, "sequence_flowchart")
            
            return f"✅ Sequence Flowchart generated: {image_path}\n\n📊 Mermaid Code:\n```mermaid\n{mermaid_code}\n```"
            
        except Exception as e:
            return f"❌ Error generating flowchart: {str(e)}"
    
    return create_sequence_flowchart

def create_clean_mermaid_tool():
    """Create a tool for generating clean, uncorrected Mermaid flowcharts."""
    @tool("create_clean_mermaid")
    def create_clean_mermaid(flowchart_type: str, title: str, nodes: str, connections: str, styling: str = "") -> str:
        """Create a clean, uncorrected Mermaid flowchart that can be copied and pasted directly.
        
        Args:
            flowchart_type: Type of flowchart (graph, sequenceDiagram, etc.)
            title: Title for the flowchart
            nodes: Node definitions (A[Label], B[Label], etc.)
            connections: Connection definitions (A --> B, B --> C, etc.)
            styling: Optional styling (style A fill:#color)
            
        Returns:
            Clean Mermaid code that can be copied and pasted directly
        """
        try:
            # Create clean Mermaid diagram
            mermaid_code = f"""```mermaid
{flowchart_type}
{nodes}
{connections}
{styling}
```"""
            
            return f"📊 Clean Mermaid Flowchart for '{title}':\n\n{mermaid_code}\n\n💡 Copy the code above and paste it into any Mermaid-compatible editor!"
            
        except Exception as e:
            return f"❌ Error generating clean flowchart: {str(e)}"
    
    return create_clean_mermaid

def create_comprehensive_debugging_flowchart_tool():
    """Create a tool for generating comprehensive debugging flowcharts with multiple subgraphs."""
    @tool("create_comprehensive_debugging_flowchart")
    def create_comprehensive_debugging_flowchart(
        problem: str, 
        investigation: str, 
        solution: str,
        fix_steps: str,
        system_components: str
    ) -> str:
        """Create a comprehensive debugging flowchart with multiple subgraphs.
        
        Args:
            problem: The problem description
            investigation: Investigation steps
            solution: The solution found
            fix_steps: Steps to implement the fix
            system_components: System architecture components
            
        Returns:
            Comprehensive Mermaid flowchart with multiple subgraphs
        """
        try:
            # Create comprehensive Mermaid diagram
            mermaid_code = f"""```mermaid
graph LR
    A[🎭 Problem Discovery: {problem}] --> B[🔍 Investigation: {investigation}]
    B --> C[💡 Solution Found: {solution}]
    C --> D[✅ Problem Resolved]
    
    style A fill:#ffebee
    style B fill:#fff3e0
    style C fill:#e8f5e8
    style D fill:#e1f5fe

    subgraph fix_flow
        A2[🔧 Fix Implementation] --> B2[Implemented specific exception handling]
        B2 --> C2[Refactored error handling code]
        C2 --> D2[Enhanced logging]
        D2 --> E2[Tested with various scenarios]
        E2 --> F2[✅ Fix Verified]
    end

    subgraph system_architecture
        A3[API Endpoint] --> B3[Authorization Token]
        B3 --> C3[Token Validation]
        C3 --> D3[Error Handling]
        D3 --> E3[User Feedback]
        E3 --> F3[Logging]
    end
```"""
            
            return f"📊 Comprehensive Debugging Flowchart:\n\n{mermaid_code}\n\n💡 Copy the code above and paste it into any Mermaid-compatible editor!"
            
        except Exception as e:
            return f"❌ Error generating comprehensive flowchart: {str(e)}"
    
    return create_comprehensive_debugging_flowchart

def _generate_mermaid_image(mermaid_code: str, filename: str) -> str:
    """Generate an image from Mermaid code using the Mermaid API."""
    try:
        # Create output directory
        output_dir = Path("flowcharts")
        output_dir.mkdir(exist_ok=True)
        
        # Encode the Mermaid code
        encoded_code = base64.b64encode(mermaid_code.encode()).decode()
        
        # Use Mermaid API to generate image
        url = f"https://mermaid.ink/img/{encoded_code}?type=png"
        
        # Download the image
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            image_path = output_dir / f"{filename}.png"
            with open(image_path, 'wb') as f:
                f.write(response.content)
            return str(image_path)
        else:
            # Fallback: create HTML file
            return _create_fallback_image(mermaid_code, filename, output_dir)
            
    except Exception as e:
        # Fallback: create HTML file
        output_dir = Path("flowcharts")
        output_dir.mkdir(exist_ok=True)
        return _create_fallback_image(mermaid_code, filename, output_dir)

def _create_fallback_image(mermaid_code: str, filename: str, output_dir: Path) -> str:
    """Create a fallback HTML file when image generation fails."""
    try:
        # Create an HTML file with the Mermaid diagram
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{filename.replace('_', ' ').title()}</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <style>
        body {{ 
            font-family: Arial, sans-serif; 
            margin: 20px; 
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .mermaid {{ 
            text-align: center; 
            margin: 20px 0;
            padding: 20px;
            background: #fafafa;
            border-radius: 8px;
        }}
        .download-info {{ 
            background: #e3f2fd; 
            padding: 15px; 
            border-radius: 5px; 
            margin: 20px 0; 
            border-left: 4px solid #2196f3;
        }}
        .code-block {{
            background: #f5f5f5;
            padding: 15px;
            border-radius: 5px;
            font-family: 'Courier New', monospace;
            white-space: pre-wrap;
            margin: 20px 0;
            border: 1px solid #ddd;
        }}
        h1 {{
            color: #333;
            border-bottom: 2px solid #2196f3;
            padding-bottom: 10px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 {filename.replace('_', ' ').title()}</h1>
        <div class="download-info">
            💡 <strong>Tip:</strong> Right-click on the diagram below and select "Save image as..." to download it.
        </div>
        <div class="mermaid">
{mermaid_code}
        </div>
        <div class="code-block">
<strong>Mermaid Code:</strong>
{mermaid_code}
        </div>
    </div>
    <script>
        mermaid.initialize({{ 
            startOnLoad: true,
            theme: 'default',
            flowchart: {{
                useMaxWidth: true,
                htmlLabels: true
            }}
        }});
    </script>
</body>
</html>
        """
        
        html_path = output_dir / f"{filename}.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return f"HTML flowchart created: {html_path} (open in browser to view)"
        
    except Exception as e:
        return f"Could not create flowchart: {str(e)}"

def create_debugging_storyboard_tool():
    """Create a tool for generating debugging storyboards as images."""
    @tool("create_debugging_storyboard")
    def create_debugging_storyboard(problem: str, investigation: str, solution: str) -> str:
        """Create a visual debugging storyboard as an image.
        
        Args:
            problem: The problem description
            investigation: Investigation steps
            solution: The solution found
            
        Returns:
            Path to the generated storyboard image
        """
        try:
            # Create Mermaid diagram
            mermaid_code = f"""
graph LR
    A[🎭 Problem Discovery<br/>{problem}] --> B[🔍 Investigation<br/>{investigation}]
    B --> C[💡 Solution Found<br/>{solution}]
    C --> D[✅ Problem Resolved]
    
    style A fill:#ffebee
    style B fill:#fff3e0
    style C fill:#e8f5e8
    style D fill:#e1f5fe
            """
            
            # Generate image using Mermaid API
            image_path = _generate_mermaid_image(mermaid_code, "debugging_storyboard")
            
            return f"✅ Debugging Storyboard generated: {image_path}\n\n📊 Mermaid Code:\n```mermaid\n{mermaid_code}\n```"
            
        except Exception as e:
            return f"❌ Error generating storyboard: {str(e)}"
    
    return create_debugging_storyboard

# Legacy functions for backward compatibility
def create_error_flowchart(error_type: str, error_message: str, components: str, **kwargs) -> str:
    """Legacy function - use create_error_flowchart_tool instead."""
    tool = create_error_flowchart_tool()
    return tool(error_type, error_message, components, kwargs.get('timeline', ''), kwargs.get('severity', 'HIGH'))

def create_system_flowchart(entry_point: str, functions: str, **kwargs) -> str:
    """Legacy function - use create_system_flowchart_tool instead."""
    tool = create_system_flowchart_tool()
    return tool(entry_point, functions, kwargs.get('dependencies', ''))