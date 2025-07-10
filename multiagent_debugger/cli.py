import os
import sys
import click
from typing import Optional

from multiagent_debugger.config import load_config
from multiagent_debugger.crew import DebuggerCrew
from multiagent_debugger.utils import llm_config_manager
from multiagent_debugger.utils.constants import ENV_VARS, DEFAULT_API_BASES

@click.group()
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
        for var in provider_vars:
            current_value = os.environ.get(var, "Not set")
            click.echo(f"  {var}: {current_value}")
    
    # Get API key (optional, can use environment variable)
    api_key = click.prompt(
        f"Enter {provider.capitalize()} API key (or press Enter to use environment variable)",
        default="",
        show_default=False
    )
    
    # If user provided an API key, export it in the current process and print export command
    if api_key and provider_vars:
        for var in provider_vars:
            if "API_KEY" in var:
                os.environ[var] = api_key
                click.echo(f"\nExported {var} for this session.")
                click.echo(f"To use this API key in your shell, run:")
                click.echo(f"  export {var}={api_key}")
    
    # Get API base (optional)
    default_api_base = DEFAULT_API_BASES.get(provider.lower())
    api_base = click.prompt(
        f"Enter {provider.capitalize()} API base URL (or press Enter for default)",
        default=default_api_base or "",
        show_default=False
    )
    
    # Get log paths
    log_paths = []
    click.echo("\nEnter log file paths (press Enter when done):")
    while True:
        log_path = click.prompt(
            f"Log file {len(log_paths) + 1}",
            default="",
            show_default=False
        )
        if not log_path:
            break
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
        for var in provider_vars:
            if "API_KEY" in var:
                click.echo(f"  export {var}=your_api_key_here")
    
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