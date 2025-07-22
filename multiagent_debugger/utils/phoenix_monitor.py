"""Phoenix monitoring integration for multiagent debugger."""

import os
from typing import Optional, Dict, Any
from contextlib import contextmanager

try:
    import phoenix as px
    from phoenix.otel import register
    from opentelemetry import trace
    PHOENIX_AVAILABLE = True
    
    # Import instrumentation modules
    try:
        from openinference.instrumentation.openai import OpenAIInstrumentor
        OPENAI_INSTRUMENTATION = True
    except ImportError:
        OPENAI_INSTRUMENTATION = False
        OpenAIInstrumentor = None
    
    try:
        from openinference.instrumentation.anthropic import AnthropicInstrumentor
        ANTHROPIC_INSTRUMENTATION = True
    except ImportError:
        ANTHROPIC_INSTRUMENTATION = False
        AnthropicInstrumentor = None
    
    try:
        from openinference.instrumentation.google_genai import GoogleGenAIInstrumentor
        GOOGLE_GENAI_INSTRUMENTATION = True
    except ImportError:
        GOOGLE_GENAI_INSTRUMENTATION = False
        GoogleGenAIInstrumentor = None
    
    try:
        from openinference.instrumentation.groq import GroqInstrumentor
        GROQ_INSTRUMENTATION = True
    except ImportError:
        GROQ_INSTRUMENTATION = False
        GroqInstrumentor = None
    
    try:
        from openinference.instrumentation.mistralai import MistralAIInstrumentor
        MISTRALAI_INSTRUMENTATION = True
    except ImportError:
        MISTRALAI_INSTRUMENTATION = False
        MistralAIInstrumentor = None
        
except ImportError:
    PHOENIX_AVAILABLE = False
    px = None
    register = None
    trace = None
    OPENAI_INSTRUMENTATION = False
    ANTHROPIC_INSTRUMENTATION = False
    GOOGLE_GENAI_INSTRUMENTATION = False
    GROQ_INSTRUMENTATION = False
    MISTRALAI_INSTRUMENTATION = False
    OpenAIInstrumentor = None
    AnthropicInstrumentor = None
    GoogleGenAIInstrumentor = None
    GroqInstrumentor = None
    MistralAIInstrumentor = None



class PhoenixMonitor:
    """Phoenix monitoring integration for tracking agent execution and LLM calls."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize Phoenix monitoring.
        
        Args:
            config: Configuration dictionary with Phoenix settings
        """
        self.config = config or {}
        self.enabled = PHOENIX_AVAILABLE and self.config.get('enabled', True)
        self.session = None
        self.tracer = None
        
        if not PHOENIX_AVAILABLE:
            print("Phoenix not available. Install with: pip install arize-phoenix")
            return
            
        self._setup_phoenix()
    
    def _setup_phoenix(self):
        """Set up Phoenix monitoring and OpenTelemetry tracing."""
        if not PHOENIX_AVAILABLE:
            return
            
        try:
            # Configure Phoenix
            phoenix_host = self.config.get('host', 'localhost')
            phoenix_port = self.config.get('port', 6006)
            
            # Set environment variables for Phoenix
            os.environ.setdefault('PHOENIX_HOST', phoenix_host)
            os.environ.setdefault('PHOENIX_PORT', str(phoenix_port))
            # Check if Phoenix is already running
            existing_session = px.active_session()
            if existing_session:
                print(f"Using existing Phoenix session at: {existing_session.url}")
                self.session = existing_session
            elif self.config.get('launch_phoenix', True):
                try:
                    # Use a different GRPC port to avoid conflicts
                    import socket
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.bind(('', 0))
                        grpc_port = s.getsockname()[1]
                    
                    # Set GRPC port to avoid conflicts
                    os.environ['PHOENIX_GRPC_PORT'] = str(grpc_port)
                    
                    self.session = px.launch_app(port=phoenix_port)
                    print(f"Phoenix launched at: {self.session.url}")
                except Exception as e:
                    print(f"Could not launch Phoenix session: {e}")
                    # Try to connect to existing Phoenix instance if launch fails
                    try:
                        import requests
                        test_url = f"http://{phoenix_host}:{phoenix_port}"
                        response = requests.get(test_url, timeout=2)
                        if response.status_code == 200:
                            print(f"Found existing Phoenix instance at {test_url}")
                            # Create a mock session object
                            class MockSession:
                                def __init__(self, url):
                                    self.url = url
                            self.session = MockSession(test_url)
                        else:
                            self.session = None
                    except:
                        self.session = None
            
            # Register Phoenix OTEL tracer with auto-instrumentation per official docs
            try:
                tracer_provider = register(
                    project_name="multiagent-debugger",
                    endpoint=f"http://{phoenix_host}:{phoenix_port}/v1/traces",
                    auto_instrument=True,  # Auto-instrument as per Phoenix docs
                    set_global_tracer_provider=False
                )
                print(f"Phoenix OTEL registered successfully: {tracer_provider}")
                
                # Explicit instrumentation for better control
                if OPENAI_INSTRUMENTATION and OpenAIInstrumentor:
                    try:
                        OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)
                        print("OpenAI instrumentation enabled")
                    except Exception as e:
                        print(f"Failed to instrument OpenAI: {e}")
                
                if ANTHROPIC_INSTRUMENTATION and AnthropicInstrumentor:
                    try:
                        AnthropicInstrumentor().instrument(tracer_provider=tracer_provider)
                        print("Anthropic instrumentation enabled")
                    except Exception as e:
                        print(f"Failed to instrument Anthropic: {e}")
                
                if GOOGLE_GENAI_INSTRUMENTATION and GoogleGenAIInstrumentor:
                    try:
                        GoogleGenAIInstrumentor().instrument(tracer_provider=tracer_provider)
                        print("Google GenAI instrumentation enabled")
                    except Exception as e:
                        print(f"Failed to instrument Google GenAI: {e}")
                
                if GROQ_INSTRUMENTATION and GroqInstrumentor:
                    try:
                        GroqInstrumentor().instrument(tracer_provider=tracer_provider)
                        print("Groq instrumentation enabled")
                    except Exception as e:
                        print(f"Failed to instrument Groq: {e}")
                
                if MISTRALAI_INSTRUMENTATION and MistralAIInstrumentor:
                    try:
                        MistralAIInstrumentor().instrument(tracer_provider=tracer_provider)
                        print("MistralAI instrumentation enabled")
                    except Exception as e:
                        print(f"Failed to instrument MistralAI: {e}")
                        
            except Exception as e:
                print(f"Phoenix OTEL already registered or registration failed: {e}")
                
            # Get tracer for this application
            self.tracer = trace.get_tracer("multiagent-debugger")
            
            # Test trace creation to ensure connection works
            try:
                with self.tracer.start_as_current_span("phoenix_initialization_test") as span:
                    span.set_attribute("test.initialization", "success")
                    span.set_attribute("phoenix.endpoint", f"http://{phoenix_host}:{phoenix_port}")
                # Force flush to ensure trace is sent
                if hasattr(trace.get_tracer_provider(), 'force_flush'):
                    trace.get_tracer_provider().force_flush(timeout_millis=1000)
                print("Test trace created and flushed")
            except Exception as e:
                print(f"Failed to create test trace: {e}")

            print("Phoenix monitoring initialized successfully")

        except Exception as e:
            print(f"Failed to initialize Phoenix monitoring: {e}")
            self.enabled = False
    
    
    @contextmanager
    def trace_agent_execution(self, agent_name: str, task: str, **kwargs):
        """Context manager for tracing agent execution.
        
        Args:
            agent_name: Name of the agent being executed
            task: Description of the task being performed
            **kwargs: Additional metadata to include in the trace
        """
        if not self.enabled or not self.tracer:
            yield
            return
        
        with self.tracer.start_as_current_span(f"agent_execution_{agent_name}") as span:
            # Add attributes to the span
            span.set_attribute("agent.name", agent_name)
            span.set_attribute("agent.task", task)
            
            # Add any additional metadata
            for key, value in kwargs.items():
                if isinstance(value, (str, int, float, bool)):
                    span.set_attribute(f"agent.{key}", value)
            
            try:
                yield span
            except Exception as e:
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                raise
    
    @contextmanager
    def trace_crew_execution(self, crew_name: str, question: str, **kwargs):
        """Context manager for tracing entire crew execution.
        
        Args:
            crew_name: Name of the crew being executed
            question: The question/problem being debugged
            **kwargs: Additional metadata to include in the trace
        """
        if not self.enabled or not self.tracer:
            yield
            return
        
        with self.tracer.start_as_current_span(f"crew_execution_{crew_name}") as span:
            # Add attributes to the span
            span.set_attribute("crew.name", crew_name)
            span.set_attribute("crew.question", question)
            
            # Add any additional metadata
            for key, value in kwargs.items():
                if isinstance(value, (str, int, float, bool)):
                    span.set_attribute(f"crew.{key}", value)
            
            try:
                yield span
            except Exception as e:
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                raise
            finally:
                # Force flush traces to ensure they're sent to Phoenix
                try:
                    if hasattr(trace.get_tracer_provider(), 'force_flush'):
                        trace.get_tracer_provider().force_flush(timeout_millis=2000)
                        print("Crew execution trace flushed to Phoenix")
                except Exception as e:
                    print(f"Failed to flush crew traces: {e}")
    
    def add_agent_metadata(self, span, agent_result: Any):
        """Add agent execution results as metadata to the current span.
        
        Args:
            span: The current OpenTelemetry span
            agent_result: The result from agent execution
        """
        if not self.enabled or not span:
            return
        
        try:
            # Add result metadata
            if hasattr(agent_result, 'raw'):
                span.set_attribute("agent.result.raw", str(agent_result.raw)[:1000])  # Truncate long results
            
            if hasattr(agent_result, 'output'):
                span.set_attribute("agent.result.output", str(agent_result.output)[:1000])
            
            # Add token usage if available
            if hasattr(agent_result, 'token_usage'):
                token_usage = agent_result.token_usage
                if isinstance(token_usage, dict):
                    for key, value in token_usage.items():
                        span.set_attribute(f"agent.tokens.{key}", value)
        
        except Exception as e:
            print(f"Failed to add agent metadata: {e}")
    
    def add_custom_metrics(self, span, metrics: Dict[str, Any]):
        """Add custom metrics to the current span.
        
        Args:
            span: The current OpenTelemetry span
            metrics: Dictionary of custom metrics to add
        """
        if not self.enabled or not span:
            return
        
        try:
            for key, value in metrics.items():
                if isinstance(value, (str, int, float, bool)):
                    span.set_attribute(f"custom.{key}", value)
                elif isinstance(value, dict):
                    # Flatten nested dictionaries
                    for nested_key, nested_value in value.items():
                        if isinstance(nested_value, (str, int, float, bool)):
                            span.set_attribute(f"custom.{key}.{nested_key}", nested_value)
        except Exception as e:
            print(f"Failed to add custom metrics: {e}")
    
    def track_tool_usage(self, tool_name: str, execution_time: float, success: bool, **kwargs):
        """Track tool usage metrics.
        
        Args:
            tool_name: Name of the tool being used
            execution_time: Time taken to execute the tool
            success: Whether the tool execution was successful
            **kwargs: Additional metadata about tool usage
        """
        if not self.enabled or not self.tracer:
            return
        
        with self.tracer.start_as_current_span(f"tool_execution_{tool_name}") as span:
            span.set_attribute("tool.name", tool_name)
            span.set_attribute("tool.execution_time", execution_time)
            span.set_attribute("tool.success", success)
            
            # Add additional metadata
            for key, value in kwargs.items():
                if isinstance(value, (str, int, float, bool)):
                    span.set_attribute(f"tool.{key}", value)
    
    def track_llm_metrics(self, model: str, prompt_tokens: int, completion_tokens: int, 
                         total_tokens: int, cost: float = None, **kwargs):
        """Track LLM usage metrics.
        
        Args:
            model: Model name used
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            total_tokens: Total tokens used
            cost: Estimated cost of the request
            **kwargs: Additional LLM metadata
        """
        if not self.enabled or not self.tracer:
            return
        
        with self.tracer.start_as_current_span(f"llm_call_{model}") as span:
            span.set_attribute("llm.model", model)
            span.set_attribute("llm.prompt_tokens", prompt_tokens)
            span.set_attribute("llm.completion_tokens", completion_tokens)
            span.set_attribute("llm.total_tokens", total_tokens)
            
            if cost is not None:
                span.set_attribute("llm.estimated_cost", cost)
            
            # Add additional metadata
            for key, value in kwargs.items():
                if isinstance(value, (str, int, float, bool)):
                    span.set_attribute(f"llm.{key}", value)
    
    def create_custom_span(self, name: str, attributes: Dict[str, Any] = None):
        """Create a custom span for detailed tracking.
        
        Args:
            name: Name of the span
            attributes: Optional attributes to add to the span
            
        Returns:
            Context manager for the span
        """
        if not self.enabled or not self.tracer:
            from contextlib import nullcontext
            return nullcontext()
        
        span = self.tracer.start_as_current_span(name)
        
        if attributes:
            for key, value in attributes.items():
                if isinstance(value, (str, int, float, bool)):
                    span.set_attribute(key, value)
        
        return span
    
    def shutdown(self):
        """Shutdown Phoenix monitoring and cleanup resources."""
        if not self.enabled:
            return
        
        try:
            # Force flush any pending traces
            if hasattr(trace.get_tracer_provider(), 'force_flush'):
                trace.get_tracer_provider().force_flush()
            
            # Close Phoenix session if we launched it
            if self.session:
                try:
                    self.session.close()
                except AttributeError:
                    # Some versions of Phoenix don't have a close method
                    print("Phoenix session cleanup not needed")
                print("Phoenix session closed")
                
        except Exception as e:
            print(f"Error during Phoenix shutdown: {e}")
    
    def get_dashboard_url(self) -> Optional[str]:
        """Get the URL to the Phoenix dashboard.
        
        Returns:
            URL to Phoenix dashboard if available
        """
        if self.session:
            return self.session.url
        
        # Return default URL if Phoenix is running locally
        host = self.config.get('host', 'localhost')
        port = self.config.get('port', 6006)
        return f"http://{host}:{port}"


# Global Phoenix monitor instance
_phoenix_monitor: Optional[PhoenixMonitor] = None


def initialize_phoenix(config: Optional[Dict[str, Any]] = None) -> PhoenixMonitor:
    """Initialize global Phoenix monitor instance.
    
    Args:
        config: Configuration dictionary for Phoenix
        
    Returns:
        PhoenixMonitor instance
    """
    global _phoenix_monitor
    
    if _phoenix_monitor is None:
        _phoenix_monitor = PhoenixMonitor(config)
    
    return _phoenix_monitor


def get_phoenix_monitor() -> Optional[PhoenixMonitor]:
    """Get the global Phoenix monitor instance.
    
    Returns:
        PhoenixMonitor instance if initialized, None otherwise
    """
    return _phoenix_monitor


def shutdown_phoenix():
    """Shutdown the global Phoenix monitor instance."""
    global _phoenix_monitor
    
    if _phoenix_monitor:
        _phoenix_monitor.shutdown()
        _phoenix_monitor = None