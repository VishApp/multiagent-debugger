import os
import json
import requests
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
from datetime import datetime, timedelta

from .constants import (
    MODEL_INFO_URL, CACHE_DIR, CACHE_FILE, CACHE_EXPIRY_HOURS,
    ENV_VARS, DEFAULT_API_BASES, CREWAI_ENV_VARS
)

class LLMConfigManager:
    """Manager for LLM configuration and model information."""
    
    def __init__(self):
        """Initialize the LLM config manager."""
        self._model_info = None
        self._providers = None
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information from the JSON URL, with caching."""
        if self._model_info is not None:
            return self._model_info
        # Try to load from cache
        model_info = self._load_cache()
        if model_info is not None:
            self._model_info = model_info
            return self._model_info
        # Fetch from remote if cache is missing or expired
        try:
            response = requests.get(MODEL_INFO_URL, timeout=10)
            response.raise_for_status()
            model_info = response.json()
            self._save_cache(model_info)
            self._model_info = model_info
        except Exception as e:
            print(f"Warning: Could not fetch model info from {MODEL_INFO_URL}: {e}")
            # Try to use stale cache if available
            model_info = self._load_cache(ignore_expiry=True)
            if model_info is not None:
                print("Using stale cached model info.")
                self._model_info = model_info
            else:
                self._model_info = {}
        return self._model_info

    def _load_cache(self, ignore_expiry: bool = False) -> Optional[Dict[str, Any]]:
        cache_path = os.path.expanduser(os.path.join(CACHE_DIR, CACHE_FILE))
        if not os.path.exists(cache_path):
            return None
        try:
            with open(cache_path, "r") as f:
                cache = json.load(f)
            timestamp = cache.get("_timestamp")
            if not timestamp:
                return None
            cache_time = datetime.fromisoformat(timestamp)
            if not ignore_expiry:
                if datetime.now() - cache_time > timedelta(hours=CACHE_EXPIRY_HOURS):
                    return None
            return cache.get("model_info")
        except Exception:
            return None

    def _save_cache(self, model_info: Dict[str, Any]):
        cache_dir = os.path.expanduser(CACHE_DIR)
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, CACHE_FILE)
        cache = {
            "_timestamp": datetime.now().isoformat(),
            "model_info": model_info
        }
        try:
            with open(cache_path, "w") as f:
                json.dump(cache, f)
        except Exception as e:
            print(f"Warning: Could not write model info cache: {e}")

    def get_providers(self) -> List[str]:
        """Get list of available providers."""
        if self._providers is None:
            model_info = self.get_model_info()
            providers = set()
            for model_data in model_info.values():
                if "litellm_provider" in model_data:
                    providers.add(model_data["litellm_provider"])
            self._providers = sorted(list(providers))
        return self._providers
    
    def get_models_for_provider(self, provider: str) -> List[str]:
        """Get list of models for a specific provider."""
        model_info = self.get_model_info()
        models = []
        for model_name, model_data in model_info.items():
            if model_data.get("litellm_provider") == provider:
                models.append(model_name)
        return sorted(models)
    
    def get_model_details(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Get details for a specific model."""
        model_info = self.get_model_info()
        return model_info.get(model_name)
    
    def validate_model(self, provider: str, model_name: str) -> bool:
        """Validate if a model exists for a provider."""
        model_info = self.get_model_info()
        if model_name in model_info:
            return model_info[model_name].get("litellm_provider") == provider
        return False

def get_env_var_name_for_provider(provider: str, var_type: str = "api_key") -> Optional[str]:
    """Get environment variable name for a specific provider.
    
    Args:
        provider: The provider name
        var_type: Type of variable ("api_key", "api_base", etc.)
        
    Returns:
        Environment variable name (e.g., "ANTHROPIC_API_KEY") or None if not found
    """
    provider_vars = ENV_VARS.get(provider.lower(), [])
    
    if var_type == "api_key":
        # Look for API key variables
        for var in provider_vars:
            if "API_KEY" in var:
                return var
    elif var_type == "api_base":
        # Look for API base variables
        for var in provider_vars:
            if "API_BASE" in var or "ENDPOINT" in var:
                return var
    
    return None

def get_env_var_for_provider(provider: str, var_type: str = "api_key") -> Optional[str]:
    """Get environment variable value for a specific provider.
    
    Args:
        provider: The provider name
        var_type: Type of variable ("api_key", "api_base", etc.)
        
    Returns:
        Environment variable value or None if not found
    """
    env_var_name = get_env_var_name_for_provider(provider, var_type)
    if env_var_name:
        return os.getenv(env_var_name)
    return None

def get_llm_config(llm_config: Any) -> Dict[str, Any]:
    """Get the LLM configuration based on the provider.
    
    Args:
        llm_config: LLMConfig object or dictionary containing LLM settings
        
    Returns:
        Dictionary containing the LLM configuration for CrewAI
    """
    # Handle both dict and LLMConfig objects
    if hasattr(llm_config, 'provider'):
        provider = llm_config.provider.lower()
    else:
        provider = llm_config.get("provider", "openai").lower()
        
    if hasattr(llm_config, 'model_name'):
        model = llm_config.model_name
    else:
        model = llm_config.get("model_name", "gpt-4")
        
    if hasattr(llm_config, 'temperature'):
        temperature = llm_config.temperature
    else:
        temperature = llm_config.get("temperature", 0.1)
        
    # Get API key from config or environment
    api_key = None
    if hasattr(llm_config, 'api_key') and llm_config.api_key:
        api_key = llm_config.api_key
    elif isinstance(llm_config, dict) and llm_config.get("api_key"):
        api_key = llm_config["api_key"]
    else:
        # Try to get from environment
        api_key = get_env_var_for_provider(provider, "api_key")
        
    # Get API base from config or environment
    api_base = None
    if hasattr(llm_config, 'api_base') and llm_config.api_base:
        api_base = llm_config.api_base
    elif isinstance(llm_config, dict) and llm_config.get("api_base"):
        api_base = llm_config["api_base"]
    else:
        # Try to get from environment, fallback to default
        api_base = get_env_var_for_provider(provider, "api_base")
        if not api_base:
            api_base = DEFAULT_API_BASES.get(provider)
    
    # Build flat configuration for CrewAI
    config = {
        "model": model,
        "temperature": temperature,
    }
    if api_key:
        config["api_key"] = api_key
    if api_base:
        config["api_base"] = api_base
    
    return config

def get_verbose_flag(config: Any) -> bool:
    """Get the verbose flag from config.
    
    Args:
        config: DebuggerConfig object or dictionary containing configuration
        
    Returns:
        Boolean indicating if verbose mode is enabled
    """
    verbose = False
    if hasattr(config, 'verbose'):
        verbose = config.verbose
    elif isinstance(config, dict) and "verbose" in config:
        verbose = config["verbose"]
    return verbose

def set_crewai_env_vars(provider: str, api_key: str = None):
    """Set CrewAI-specific environment variables.
    
    Args:
        provider: The provider name
        api_key: The API key to set
    """
    if not api_key:
        api_key = get_env_var_for_provider(provider, "api_key")
    
    if api_key:
        # Set CrewAI memory environment variable based on provider
        if provider.lower() == "openai":
            os.environ["CHROMA_OPENAI_API_KEY"] = api_key
        elif provider.lower() == "anthropic":
            os.environ["CHROMA_ANTHROPIC_API_KEY"] = api_key
        elif provider.lower() == "google":
            os.environ["CHROMA_GOOGLE_API_KEY"] = api_key

def create_langchain_llm(provider: str, model: str, temperature: float, api_key: str = None, api_base: str = None):
    """Create the appropriate LangChain LLM based on provider.
    
    Args:
        provider: The LLM provider (openai, anthropic, google, mistral, cohere)
        model: The model name
        temperature: The temperature setting
        api_key: The API key for the provider
        api_base: The API base URL (if needed)
        
    Returns:
        A LangChain LLM object
    """
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

def get_agent_llm_config(llm_config: Any) -> tuple:
    """Extract LLM configuration parameters from config object.
    
    Args:
        llm_config: LLMConfig object or dictionary containing LLM settings
        
    Returns:
        Tuple of (provider, model, temperature, api_key, api_base)
    """
    # Handle both dict and LLMConfig objects
    if hasattr(llm_config, 'provider'):
        provider = llm_config.provider.lower()
    else:
        provider = llm_config.get("provider", "openai").lower()
        
    if hasattr(llm_config, 'model_name'):
        model = llm_config.model_name
    else:
        model = llm_config.get("model_name", "gpt-4")
        
    if hasattr(llm_config, 'temperature'):
        temperature = llm_config.temperature
    else:
        temperature = llm_config.get("temperature", 0.1)
        
    if hasattr(llm_config, 'api_key'):
        api_key = llm_config.api_key
    else:
        api_key = llm_config.get("api_key")
        
    if hasattr(llm_config, 'api_base'):
        api_base = llm_config.api_base
    else:
        api_base = llm_config.get("api_base")
    
    return provider, model, temperature, api_key, api_base

# Global instance of the config manager
llm_config_manager = LLMConfigManager() 