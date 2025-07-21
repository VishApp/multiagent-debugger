import os
import sys
import glob
import click
from typing import Optional, List

from multiagent_debugger.config import load_config
from multiagent_debugger.crew import DebuggerCrew
from multiagent_debugger.utils import llm_config_manager
from multiagent_debugger.utils.constants import ENV_VARS, DEFAULT_API_BASES
from multiagent_debugger import __version__

def expand_log_paths(path: str) -> List[str]:
    """Expand a log path to a list of actual log files.
    
    Args:
        path: Path that could be a file, directory, or wildcard pattern
        
    Returns:
        List of resolved log file paths
    """
    expanded_paths = []
    
    # Handle wildcard patterns
    if '*' in path or '?' in path:
        try:
            matched_paths = glob.glob(path, recursive=True)
            for matched_path in matched_paths:
                if os.path.isfile(matched_path) and is_log_file(matched_path):
                    expanded_paths.append(matched_path)
        except Exception:
            pass
    else:
        # Handle single file or directory
        if os.path.isfile(path):
            # It's a file, check if it looks like a log file
            if is_log_file(path):
                expanded_paths.append(path)
        elif os.path.isdir(path):
            # It's a directory, find all log files recursively
            for root, dirs, files in os.walk(path):
                for file in files:
                    if is_log_file(file):
                        full_path = os.path.join(root, file)
                        expanded_paths.append(full_path)
        else:
            # Path doesn't exist yet, but might be valid later
            # Check if it has a log-like extension
            if is_log_file(path):
                expanded_paths.append(path)
    
    return expanded_paths

def is_log_file(filename: str) -> bool:
    """Check if a filename looks like a log file.
    
    Args:
        filename: The filename to check
        
    Returns:
        True if it appears to be a log file
    """
    log_extensions = {'.log', '.txt', '.out', '.err', '.access', '.error'}
    log_patterns = ['log', 'access', 'error', 'debug', 'trace']
    
    # Check file extension
    _, ext = os.path.splitext(filename.lower())
    if ext in log_extensions:
        return True
    
    # Check if filename contains log-related keywords
    filename_lower = filename.lower()
    return any(pattern in filename_lower for pattern in log_patterns)

def _is_phoenix_running(host: str = "localhost", port: int = 6006) -> bool:
    """Check if Phoenix is already running on the specified host and port."""
    try:
        import requests
        response = requests.get(f"http://{host}:{port}/health", timeout=3)
        return response.status_code == 200
    except Exception:
        return False

def _start_phoenix_background(host: str = "localhost", port: int = 6006):
    """Start Phoenix in background if not already running."""
    try:
        import subprocess
        import sys
        import time
        
        # Launch Phoenix in background using subprocess
        python_path = sys.executable
        script_args = [
            python_path, "-c", 
            f"""
import phoenix as px
import time
import signal
import sys

def signal_handler(sig, frame):
    print('\\nShutting down Phoenix...')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

try:
    session = px.launch_app(port={port})
    print(f'Phoenix dashboard launched at: {{session.url}}')
    print('Phoenix running in background. Use "multiagent-debugger phoenix --stop" to stop.')
    
    # Keep running
    while True:
        time.sleep(1)
except Exception as e:
    print(f'Error: {{e}}')
    sys.exit(1)
"""
        ]
        
        # Start Phoenix in background
        process = subprocess.Popen(
            script_args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setpgrp if hasattr(os, 'setpgrp') else None  # Detach from parent process
        )
        
        # Give it a moment to start
        time.sleep(3)
        
        # Check if it's running
        if _is_phoenix_running(host, port):
            click.echo(f"Phoenix started successfully. Dashboard: http://{host}:{port}")
        else:
            click.echo("Phoenix may have failed to start. Check manually if needed.")
            
    except Exception as e:
        click.echo(f"Failed to start Phoenix in background: {e}")

@click.group()
@click.version_option(version=__version__, prog_name="multiagent-debugger")
def cli():
    """Multi-agent debugger CLI."""
    pass

@cli.command()
@click.argument('question')
@click.option('--config', '-c', help='Path to config file')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.option('--mode', type=click.Choice(['frequent', 'latest', 'all']), default=None, help='Log analysis mode')
@click.option('--time-window-hours', type=int, default=None, help='Time window in hours for analysis')
@click.option('--max-lines', type=int, default=None, help='Maximum log lines to analyze')
@click.option('--code-path', type=str, default=None, help='Path to source code directory or file for analysis')
@click.option('--phoenix', is_flag=True, help='Enable Phoenix monitoring for this session')
@click.option('--no-phoenix', is_flag=True, help='Disable Phoenix monitoring for this session')
@click.help_option('--help', '-h')
def debug(question: str, config: Optional[str] = None, verbose: bool = False, mode: Optional[str] = None, time_window_hours: Optional[int] = None, max_lines: Optional[int] = None, code_path: Optional[str] = None, phoenix: bool = False, no_phoenix: bool = False):
    """Debug an API failure or error scenario with multi-agent assistance."""
    # Load config
    click.echo("Initializing Multi-Agent Debugger...")
    config_obj = load_config(config)
    
    # Set verbose flag
    if verbose:
        config_obj.verbose = True
    
    # Set log analysis options from CLI if provided
    if mode:
        config_obj.analysis_mode = mode
    if time_window_hours:
        config_obj.time_window_hours = time_window_hours
    if max_lines:
        config_obj.max_lines = max_lines
    if code_path:
        config_obj.code_path = code_path
    
    # Override Phoenix configuration from CLI flags
    if phoenix:
        config_obj.phoenix.enabled = True
        config_obj.phoenix.launch_phoenix = False  # Don't launch new session when using --phoenix flag
    elif no_phoenix:
        config_obj.phoenix.enabled = False
    
    # Print LLM info
    click.echo(f"Using LLM Provider: {config_obj.llm.provider}")
    click.echo(f"Using Model: {config_obj.llm.model_name}")
    
    # Check if API key is available
    if not config_obj.llm.api_key:
        click.echo("Warning: No API key found in config. Please set the appropriate environment variable.")
        provider_vars = ENV_VARS.get(config_obj.llm.provider.lower(), [])
        if provider_vars:
            click.echo(f"Required environment variables for {config_obj.llm.provider}:")
            for var in provider_vars:
                click.echo(f"  - {var}")
    
    # Initialize Phoenix monitoring if enabled
    phoenix_monitor = None
    if config_obj.phoenix.enabled:
        # Auto-start Phoenix if it's not running
        if not _is_phoenix_running(config_obj.phoenix.host, config_obj.phoenix.port):
            click.echo("Phoenix not running. Starting Phoenix in background...")
            _start_phoenix_background(config_obj.phoenix.host, config_obj.phoenix.port)
            
        try:
            from multiagent_debugger.utils.phoenix_monitor import initialize_phoenix
            phoenix_monitor = initialize_phoenix(config_obj.phoenix.model_dump())
            if phoenix_monitor.enabled:
                dashboard_url = phoenix_monitor.get_dashboard_url()
                click.echo(f"Phoenix monitoring enabled. Dashboard: {dashboard_url}")
            else:
                click.echo("Phoenix monitoring disabled (dependencies not available)")
        except ImportError:
            click.echo("Phoenix monitoring unavailable (install with: pip install arize-phoenix)")
        except Exception as e:
            click.echo(f"Phoenix monitoring initialization failed: {e}")
    
    # Run debugger
    click.echo(f"Analyzing: {question}")
    click.echo("This may take a few minutes...")
    
    try:
        crew = DebuggerCrew(config_obj)
        result = crew.debug(question)
        
        # Print result
        click.echo("\nRoot Cause Analysis Complete!")
        click.echo(result)
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        if verbose:
            import traceback
            click.echo(traceback.format_exc(), err=True)
        sys.exit(1)
    finally:
        # Shutdown Phoenix monitoring
        if phoenix_monitor:
            try:
                from multiagent_debugger.utils.phoenix_monitor import shutdown_phoenix
                shutdown_phoenix()
            except Exception as e:
                if verbose:
                    click.echo(f"Phoenix shutdown error: {e}")

@cli.command()
@click.option('--output', '-o', help='Path to output config file')
def setup(output: Optional[str] = None):
    """Set up the multi-agent debugger configuration."""
    from multiagent_debugger.config import DebuggerConfig, LLMConfig
    import yaml
    
    click.echo("Setting up Multi-Agent Debugger...")
    
    # Get LLM provider
    click.echo("\nAvailable providers:")
    for provider in ENV_VARS.keys():
        click.echo(f"  - {provider}")
    
    provider = click.prompt(
        "Enter provider name",
        type=str,
        default="openai"
    )
    
    # Check if provider is supported
    if provider.lower() not in ENV_VARS:
        click.echo(f"Warning: {provider} not in supported providers. Using openai.")
        provider = "openai"
    
    click.echo(f"Selected provider: {provider}")
    
    # Get model name
    model_name = click.prompt(
        f"Enter {provider.capitalize()} model name",
        type=str,
        default="gpt-4"
    )
    
    click.echo(f"Selected model: {model_name}")
    
    # Show environment variable information
    provider_vars = ENV_VARS.get(provider.lower(), [])
    if provider_vars:
        click.echo(f"\nRequired environment variables for {provider}:")
        for var_config in provider_vars:
            if isinstance(var_config, dict) and "key_name" in var_config:
                var_name = var_config["key_name"]
                current_value = os.environ.get(var_name, "Not set")
                # Mask API keys for security
                if "API_KEY" in var_name and current_value != "Not set":
                    masked_value = f"{current_value[:8]}...{current_value[-4:]}" if len(current_value) > 12 else "***"
                    click.echo(f"  {var_name}: {masked_value}")
                else:
                    click.echo(f"  {var_name}: {current_value}")
            elif isinstance(var_config, str):
                # Handle legacy string format for backward compatibility
                current_value = os.environ.get(var_config, "Not set")
                if "API_KEY" in var_config and current_value != "Not set":
                    masked_value = f"{current_value[:8]}...{current_value[-4:]}" if len(current_value) > 12 else "***"
                    click.echo(f"  {var_config}: {masked_value}")
                else:
                    click.echo(f"  {var_config}: {current_value}")
    
    # Get API key (optional, can use environment variable)
    api_key = click.prompt(
        f"Enter {provider.capitalize()} API key (or press Enter to use environment variable)",
        default="",
        show_default=False,
        hide_input=True  # Hide the input so it's not displayed in the console
    )
    
    # If user provided an API key, export it in the current process and print export command
    if api_key and provider_vars:
        for var_config in provider_vars:
            if isinstance(var_config, dict) and "key_name" in var_config:
                var_name = var_config["key_name"]
                if "API_KEY" in var_name:
                    os.environ[var_name] = api_key
                    click.echo(f"\nExported {var_name} for this session.")
                    click.echo(f"To use this API key in your shell, run:")
                    # Mask the API key in the export command for security
                    masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
                    click.echo(f"  export {var_name}={masked_key}")
            elif isinstance(var_config, str) and "API_KEY" in var_config:
                # Handle legacy string format
                os.environ[var_config] = api_key
                click.echo(f"\nExported {var_config} for this session.")
                click.echo(f"To use this API key in your shell, run:")
                masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
                click.echo(f"  export {var_config}={masked_key}")
    
    # Get API base (optional)
    default_api_base = DEFAULT_API_BASES.get(provider.lower())
    api_base = click.prompt(
        f"Enter {provider.capitalize()} API base URL (or press Enter for default)",
        default=default_api_base or "",
        show_default=False
    )
    
    # Get additional parameters (optional)
    additional_params = {}
    click.echo("\nAdditional parameters (optional):")
    click.echo("You can specify additional provider-specific parameters as key=value pairs.")
    click.echo("Examples: max_tokens=1000, top_p=0.9, frequency_penalty=0.1")
    click.echo("Press Enter when done or to skip:")
    
    while True:
        param_input = click.prompt(
            f"Additional parameter {len(additional_params) + 1} (key=value or Enter to finish)",
            default="",
            show_default=False
        )
        if not param_input:
            break
        
        # Parse key=value format
        if "=" in param_input:
            key, value = param_input.split("=", 1)
            key = key.strip()
            value = value.strip()
            
            # Try to convert value to appropriate type
            try:
                # Try as float first
                if "." in value:
                    value = float(value)
                else:
                    # Try as int
                    value = int(value)
            except ValueError:
                # Keep as string if conversion fails
                pass
            
            additional_params[key] = value
            click.echo(f"  Added: {key} = {value}")
        else:
            click.echo(f"  Invalid format. Use key=value format.")
    
    # Prompt for log analysis options
    click.echo("\nLog analysis options:")
    analysis_mode = click.prompt(
        "Log analysis mode",
        type=click.Choice(['frequent', 'latest', 'all']),
        default="frequent"
    )
    time_window_hours = click.prompt(
        "Time window (in hours) for log analysis",
        type=int,
        default=24
    )
    max_lines = click.prompt(
        "Maximum number of log lines to analyze (for large logs)",
        type=int,
        default=10000
    )

    # Get log paths (files or directories)
    log_paths = []
    click.echo("\nEnter log file paths or log directories (press Enter when done):")
    click.echo("You can specify:")
    click.echo("  - Individual log files: /path/to/file.log")
    click.echo("  - Log directories: /path/to/logs/ (will find all .log files)")
    click.echo("  - Wildcard patterns: /path/to/logs/*.log")
    
    while True:
        log_path = click.prompt(
            f"Log file/directory {len(log_paths) + 1}",
            default="",
            show_default=False
        )
        if not log_path:
            break
        
        # Expand the path to handle wildcards and resolve to actual files
        expanded_paths = expand_log_paths(log_path)
        if expanded_paths:
            log_paths.extend(expanded_paths)
            click.echo(f"  Added {len(expanded_paths)} log file(s):")
            for path in expanded_paths:
                click.echo(f"    - {path}")
        else:
            click.echo(f"  Warning: No log files found at {log_path}")
            # Still add the path in case it's a valid path that will exist later
            log_paths.append(log_path)
    
    # Get code path (optional)
    click.echo("\nSource code analysis options:")
    code_path = click.prompt(
        "Enter path to source code directory or file (press Enter to skip code path restriction)",
        default="",
        show_default=False
    )
    if code_path:
        click.echo(f"  Code analysis will be restricted to: {code_path}")
    else:
        click.echo("  Code analysis will not be restricted to a specific path")
        code_path = None
    
    # Get verbose setting
    verbose = click.confirm(
        "Enable verbose logging?",
        default=False
    )
    
    # Get Phoenix monitoring settings
    click.echo("\nPhoenix monitoring options:")
    phoenix_enabled = click.confirm(
        "Enable Phoenix monitoring for agent and LLM call tracing?",
        default=True
    )
    
    phoenix_config = {
        "enabled": phoenix_enabled,
        "host": "localhost",
        "port": 6006,
        "endpoint": "http://localhost:6006/v1/traces",
        "launch_phoenix": True,
        "headers": {}
    }
    
    if phoenix_enabled:
        # Ask for advanced Phoenix settings
        if click.confirm("Configure advanced Phoenix settings?", default=False):
            phoenix_config["host"] = click.prompt("Phoenix host", default="localhost")
            phoenix_config["port"] = click.prompt("Phoenix port", default=6006, type=int)
            phoenix_config["endpoint"] = click.prompt(
                "OTLP endpoint", 
                default=f"http://{phoenix_config['host']}:{phoenix_config['port']}/v1/traces"
            )
            phoenix_config["launch_phoenix"] = click.confirm(
                "Launch Phoenix app locally?", 
                default=True
            )
    
    # Create config
    config = DebuggerConfig(
        log_paths=log_paths,
        code_path=code_path,
        llm=LLMConfig(
            provider=provider,
            model_name=model_name,
            api_key=api_key if api_key else None,
            api_base=api_base if api_base else None,
            additional_params=additional_params
        ),
        phoenix=phoenix_config,
        verbose=verbose,
        analysis_mode=analysis_mode,
        time_window_hours=time_window_hours,
        max_lines=max_lines
    )
    
    # Convert to dict
    config_dict = config.model_dump()
    
    # Write config to file
    if not output:
        output = click.prompt(
            "Enter path to output config file",
            default=os.path.expanduser("~/.config/multiagent-debugger/config.yaml")
        )
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(output), exist_ok=True)
    
    # Write config to file
    with open(output, 'w') as f:
        yaml.dump(config_dict, f)
    
    click.echo(f"\nConfiguration saved to {output}")
    
    # Show environment variable setup instructions
    if not api_key and provider_vars:
        click.echo(f"\nTo use environment variables instead of hardcoded API keys:")
        for var_config in provider_vars:
            if isinstance(var_config, dict) and "key_name" in var_config:
                var_name = var_config["key_name"]
                if "API_KEY" in var_name:
                    click.echo(f"  export {var_name}=your_api_key_here")
            elif isinstance(var_config, str) and "API_KEY" in var_config:
                # Handle legacy string format
                click.echo(f"  export {var_config}=your_api_key_here")
    
    click.echo("\nSetup complete! You can now run:")
    click.echo(f"multiagent-debugger debug 'your question here' --config {output}")

@cli.command()
@click.option('--config', '-c', help='Path to config file')
def phoenix(config: Optional[str] = None):
    """Show Phoenix monitoring configuration and status."""
    from multiagent_debugger.config import load_config
    
    # Load config to get Phoenix settings
    config_obj = load_config(config)
    
    # Show Phoenix status
    try:
        from multiagent_debugger.utils.phoenix_monitor import PHOENIX_AVAILABLE
        
        click.echo("Phoenix Configuration:")
        click.echo(f"  Enabled: {config_obj.phoenix.enabled}")
        click.echo(f"  Host: {config_obj.phoenix.host}")
        click.echo(f"  Port: {config_obj.phoenix.port}")
        click.echo(f"  Endpoint: {config_obj.phoenix.endpoint}")
        click.echo(f"  Launch Phoenix: {config_obj.phoenix.launch_phoenix}")
        
        # Check if Phoenix dependencies are available
        click.echo(f"  Dependencies Available: {PHOENIX_AVAILABLE}")
        
        if PHOENIX_AVAILABLE:
            click.echo(f"\nNote: Phoenix monitoring will automatically start when you run 'debug' command.")
            click.echo(f"Dashboard will be available at: http://{config_obj.phoenix.host}:{config_obj.phoenix.port}")
            click.echo(f"\nTo access dashboard from local browser when running on remote server:")
            click.echo(f"  ssh -L {config_obj.phoenix.port}:localhost:{config_obj.phoenix.port} user@your-server")
            click.echo(f"  then visit http://localhost:{config_obj.phoenix.port} in your local browser")
        
    except Exception as e:
        click.echo(f"Error checking Phoenix status: {e}")

@cli.command()
def list_providers():
    """List available LLM providers."""
    try:
        providers = llm_config_manager.get_providers()
        click.echo("Available providers:")
        for provider in providers:
            click.echo(f"  - {provider}")
    except Exception as e:
        click.echo(f"Error fetching providers: {e}")

@cli.command()
@click.argument('provider')
def list_models(provider: str):
    """List available models for a specific provider."""
    try:
        models = llm_config_manager.get_models_for_provider(provider)
        if models:
            click.echo(f"Available models for {provider}:")
            # Check if we're using fallback models (no remote data available)
            remote_models = llm_config_manager.get_model_info()
            if not remote_models:
                click.echo("(Using fallback models - remote model data unavailable)")
            for model in models:
                details = llm_config_manager.get_model_details(model)
                if details:
                    max_tokens = details.get("max_tokens", "Unknown")
                    click.echo(f"  - {model} (max tokens: {max_tokens})")
                else:
                    click.echo(f"  - {model}")
        else:
            click.echo(f"No models found for provider: {provider}")
    except Exception as e:
        click.echo(f"Error fetching models: {e}")

if __name__ == '__main__':
    cli() 