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

@click.group()
@click.version_option(version=__version__, prog_name="multiagent-debugger")
def cli():
    """Multi-agent debugger CLI."""
    pass

@cli.command()
@click.argument('question')
@click.option('--config', '-c', help='Path to config file')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
def debug(question: str, config: Optional[str] = None, verbose: bool = False):
    """Debug an API failure with multi-agent assistance."""
    # Load config
    click.echo("Initializing Multi-Agent Debugger...")
    config_obj = load_config(config)
    
    # Set verbose flag
    if verbose:
        config_obj.verbose = True
    
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
        
    # Get code path
    code_path = click.prompt(
        "Enter path to codebase",
        default="."
    )
    
    # Create config
    config = DebuggerConfig(
        log_paths=log_paths,
        code_path=code_path,
        llm=LLMConfig(
            provider=provider,
            model_name=model_name,
            api_key=api_key if api_key else None,
            api_base=api_base if api_base else None
        ),
        verbose=True
    )
    
    # Convert to dict
    config_dict = config.dict()
    
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