import os
from typing import List, Optional, Dict, Any, Union
from pathlib import Path

import yaml
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from multiagent_debugger.utils.constants import ENV_VARS, DEFAULT_API_BASES

# Load environment variables from .env file
load_dotenv()

class LLMConfig(BaseModel):
    """Configuration for the LLM provider."""
    provider: str = Field("openai", description="LLM provider (openai, anthropic, google, ollama, etc.)")
    model_name: str = Field("gpt-4", description="Model name for the provider")
    api_key: Optional[str] = Field(None, description="API key for the provider")
    api_base: Optional[str] = Field(None, description="Base URL for the API (for custom endpoints)")
    temperature: float = Field(0.1, description="Temperature for LLM generation")
    additional_params: Dict[str, Any] = Field(default_factory=dict, description="Additional provider-specific parameters")

class DebuggerConfig(BaseModel):
    """Configuration for the multiagent debugger."""
    log_paths: List[str] = Field(default_factory=list, description="Paths to log files")
    code_path: Optional[str] = Field(None, description="Path to codebase or Git URL")
    llm: LLMConfig = Field(default_factory=LLMConfig, description="LLM configuration")
    verbose: bool = Field(False, description="Enable verbose logging")

def find_config_file() -> Optional[str]:
    """
    Look for a config file in common locations.
    Returns the path to the first config file found, or None if no config file is found.
    """
    # Common locations to check for config files
    locations = [
        "config.yaml",
        os.path.expanduser("~/.config/multiagent-debugger/config.yaml"),
        "/etc/multiagent-debugger/config.yaml",
    ]
    
    # Check if any environment variable points to a config file
    if os.environ.get("MULTIAGENT_DEBUGGER_CONFIG"):
        locations.insert(0, os.environ.get("MULTIAGENT_DEBUGGER_CONFIG"))
    
    # Return the first config file found
    for location in locations:
        if os.path.exists(location):
            return location
    
    return None

def get_env_api_key(provider: str) -> Optional[str]:
    """Get API key from environment variables for a specific provider."""
    provider_vars = ENV_VARS.get(provider.lower(), [])
    for var in provider_vars:
        if "API_KEY" in var:
            return os.getenv(var)
    return None

def get_env_api_base(provider: str) -> Optional[str]:
    """Get API base from environment variables for a specific provider."""
    provider_vars = ENV_VARS.get(provider.lower(), [])
    for var in provider_vars:
        if "API_BASE" in var or "ENDPOINT" in var:
            return os.getenv(var)
    return None

def load_config(config_path: str = None) -> DebuggerConfig:
    """Load configuration from file and environment variables."""
    # If no config path is provided, try to find one
    if config_path is None:
        config_path = find_config_file()
        
    config_data = {}
    
    # Load from config file if provided
    if config_path and os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f) or {}
    
    # Fix None values in additional_params
    if "llm" in config_data and config_data["llm"] is not None:
        if config_data["llm"].get("additional_params") is None:
            config_data["llm"]["additional_params"] = {}
    
    # Override with environment variables
    llm_config = config_data.get("llm", {})
    provider = llm_config.get("provider", "openai").lower()
    
    # Get API key from environment if not in config
    if not llm_config.get("api_key"):
        env_api_key = get_env_api_key(provider)
        if env_api_key:
            if "llm" not in config_data:
                config_data["llm"] = {}
            config_data["llm"]["api_key"] = env_api_key
    
    # Get API base from environment if not in config
    if not llm_config.get("api_base"):
        env_api_base = get_env_api_base(provider)
        if env_api_base:
            if "llm" not in config_data:
                config_data["llm"] = {}
            config_data["llm"]["api_base"] = env_api_base
        elif DEFAULT_API_BASES.get(provider):
            # Use default API base if available
            if "llm" not in config_data:
                config_data["llm"] = {}
            config_data["llm"]["api_base"] = DEFAULT_API_BASES[provider]
    
    # Create config object
    config_obj = DebuggerConfig(**config_data)
    return config_obj 