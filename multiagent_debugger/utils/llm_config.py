import os
import json
import requests
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
from datetime import datetime, timedelta

from .constants import (
    MODEL_INFO_URL, CACHE_DIR, CACHE_FILE, CACHE_EXPIRY_HOURS,
    ENV_VARS, DEFAULT_API_BASES, CREWAI_ENV_VARS, MODELS
)

def _detect_provider_from_model(model: str) -> str:
    """Detect the provider based on the model name by searching through MODELS constant.
    
    Args:
        model: The model name to search for
        
    Returns:
        The detected provider name or "unknown" if not found
    """
    model_lower = model.lower()
    
    # First, check for exact matches
    for provider, model_list in MODELS.items():
        if model in model_list:
            return provider
    
    # Then check for partial matches (for models like claude-3.7-sonnet)
    for provider, model_list in MODELS.items():
        for provider_model in model_list:
            # Remove provider prefix for comparison (e.g., "anthropic/claude-3-5-sonnet" -> "claude-3-5-sonnet")
            clean_model = provider_model.split('/')[-1] if '/' in provider_model else provider_model
            if clean_model.lower() in model_lower or model_lower in clean_model.lower():
                return provider
    
    # Special case for Claude models not in the list
    if "claude" in model_lower:
        return "anthropic"
    elif "gpt" in model_lower or "openai" in model_lower:
        return "openai"
    elif "gemini" in model_lower:
        return "gemini"
    elif "llama" in model_lower:
        return "openai"  # Many custom endpoints serve Llama models via OpenAI API
    
    return "unknown"

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
            
            # Add fallback providers if remote data is empty or missing providers
            if not providers:
                providers = set(self._get_fallback_models(""))
            else:
                # Add any missing fallback providers
                fallback_providers = set(self._get_fallback_models(""))
                providers.update(fallback_providers)
            
            self._providers = sorted(list(providers))
        return self._providers
    
    def get_models_for_provider(self, provider: str) -> List[str]:
        """Get list of models for a specific provider."""
        model_info = self.get_model_info()
        models = []
        for model_name, model_data in model_info.items():
            if model_data.get("litellm_provider") == provider:
                models.append(model_name)
        
        # If no models found from remote data, use fallback models
        if not models:
            models = self._get_fallback_models(provider)
        
        return sorted(models)
    
    def _get_fallback_models(self, provider: str) -> List[str]:
        """Get fallback models for a provider when remote data is unavailable."""
        from .constants import MODELS
        
        # Use the comprehensive MODELS configuration
        return MODELS.get(provider.lower(), [])
    
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

def get_memory_config(config: Any) -> Dict[str, Any]:
    """Extract memory configuration from config object.
    
    Args:
        config: Configuration object or dictionary containing memory settings
        
    Returns:
        Dictionary with memory configuration (enabled, memory_key, cache)
    """
    # Handle both dict and config objects
    if hasattr(config, 'memory'):
        # Object-based config (e.g., DebuggerConfig)
        memory_config = config.memory
        if hasattr(memory_config, 'enabled'):
            memory_enabled = memory_config.enabled
        elif hasattr(memory_config, 'get'):
            memory_enabled = memory_config.get("enabled", False)
        else:
            memory_enabled = False
            
        if hasattr(memory_config, 'memory_key'):
            memory_key = memory_config.memory_key
        elif hasattr(memory_config, 'get'):
            memory_key = memory_config.get("memory_key", "multiagent_debugger_v1")
        else:
            memory_key = "multiagent_debugger_v1"
            
        if hasattr(memory_config, 'cache'):
            cache_enabled = memory_config.cache
        elif hasattr(memory_config, 'get'):
            cache_enabled = memory_config.get("cache", True)
        else:
            cache_enabled = True
    else:
        # Dictionary-based config
        memory_config = config.get("memory", {})
        memory_enabled = memory_config.get("enabled", False) if isinstance(memory_config, dict) else False
        memory_key = memory_config.get("memory_key", "multiagent_debugger_v1") if isinstance(memory_config, dict) else "multiagent_debugger_v1"
        cache_enabled = memory_config.get("cache", True) if isinstance(memory_config, dict) else True
    
    return {
        "enabled": memory_enabled,
        "memory_key": memory_key,
        "cache": cache_enabled
    }

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
        # Note: For non-OpenAI providers, we typically disable memory to avoid issues
        if provider.lower() == "openai":
            os.environ["CHROMA_OPENAI_API_KEY"] = api_key
        elif provider.lower() == "anthropic":
            # For Anthropic, we'll set the env var but typically disable memory in crew config
            os.environ["CHROMA_ANTHROPIC_API_KEY"] = api_key
        elif provider.lower() in ["google", "gemini"]:
            os.environ["CHROMA_GOOGLE_API_KEY"] = api_key
        
        # Note: CrewAI may still require OpenAI for some internal operations
        # We handle this by disabling memory for non-OpenAI providers

def create_crewai_llm(provider: str, model: str, temperature: float, api_key: str = None, api_base: str = None, additional_params: Dict[str, Any] = None):
    """Create a CrewAI LLM object directly.
    
    Args:
        provider: The LLM provider (openai, anthropic, google, gemini, deepseek, etc.)
        model: The model name
        temperature: The temperature setting
        api_key: The API key for the provider
        api_base: The API base URL (if needed)
        additional_params: Additional parameters to pass to the LLM constructor
        
    Returns:
        A CrewAI LLM object
    """
    from crewai import LLM
    import os
    
    # Set default for additional_params
    if additional_params is None:
        additional_params = {}
    
    # Set the API key in environment if provided
    if api_key:
        if provider.lower() in ["openai", "gpt"]:
            os.environ["OPENAI_API_KEY"] = api_key
        elif provider.lower() in ["anthropic", "claude"]:
            os.environ["ANTHROPIC_API_KEY"] = api_key
        elif provider.lower() in ["google", "gemini"]:
            os.environ["GOOGLE_API_KEY"] = api_key
        elif provider.lower() == "deepseek":
            os.environ["DEEPSEEK_API_KEY"] = api_key
        elif provider.lower() == "nvidia_nim":
            os.environ["NVIDIA_NIM_API_KEY"] = api_key
        elif provider.lower() == "groq":
            os.environ["GROQ_API_KEY"] = api_key
        elif provider.lower() == "watson":
            os.environ["WATSONX_APIKEY"] = api_key
        elif provider.lower() == "bedrock":
            # Bedrock uses AWS credentials, not a single API key
            pass
        elif provider.lower() == "azure":
            os.environ["AZURE_API_KEY"] = api_key
        elif provider.lower() == "cerebras":
            os.environ["CEREBRAS_API_KEY"] = api_key
        elif provider.lower() == "huggingface":
            os.environ["HF_TOKEN"] = api_key
        elif provider.lower() == "sambanova":
            os.environ["SAMBANOVA_API_KEY"] = api_key
        elif provider.lower() == "openrouter":
            os.environ["OPENROUTER_API_KEY"] = api_key
            if api_base:
                os.environ["OPENROUTER_API_BASE"] = api_base
        elif provider.lower() == "ollama":
            # Ollama doesn't need API key, but we can set base URL
            if api_base:
                os.environ["OLLAMA_BASE_URL"] = api_base
        elif provider.lower() == "custom":
            # For custom providers, detect the actual provider based on model name
            detected_provider = _detect_provider_from_model(model)
            print(f"DEBUG: Detected provider '{detected_provider}' for model '{model}'")
            
            if detected_provider == "anthropic":
                os.environ["ANTHROPIC_API_KEY"] = api_key
            elif detected_provider == "openai":
                os.environ["OPENAI_API_KEY"] = api_key
            elif detected_provider == "gemini":
                os.environ["GOOGLE_API_KEY"] = api_key
            elif detected_provider == "groq":
                os.environ["GROQ_API_KEY"] = api_key
            elif detected_provider == "nvidia_nim":
                os.environ["NVIDIA_NIM_API_KEY"] = api_key
            elif detected_provider == "watson":
                os.environ["WATSONX_APIKEY"] = api_key
            elif detected_provider == "bedrock":
                # Bedrock uses AWS credentials, not a single API key
                pass
            elif detected_provider == "huggingface":
                os.environ["HF_TOKEN"] = api_key
            elif detected_provider == "sambanova":
                os.environ["SAMBANOVA_API_KEY"] = api_key
            elif detected_provider == "openrouter":
                os.environ["OPENROUTER_API_KEY"] = api_key
            else:
                # Default to OpenAI-compatible for unknown models
                print(f"DEBUG: Unknown model '{model}', defaulting to OpenAI-compatible")
                os.environ["OPENAI_API_KEY"] = api_key
    
    try:
        # Build base configuration
        llm_config = {
            "model": model,
            "temperature": temperature,
            **additional_params  # Include additional parameters
        }
        
        # Add API key and base URL if provided
        if api_key:
            llm_config["api_key"] = api_key
        if api_base:
            llm_config["base_url"] = api_base
        llm = LLM(**llm_config)
        
        return llm
        
    except Exception as e:
        print(f"ERROR: Failed to instantiate {provider} LLM: {e}")
        print(f"DEBUG: Model: {model}, API Key: {'Set' if api_key else 'None'}")
        import traceback
        print(traceback.format_exc())
        raise

# Keep the old function for backward compatibility but mark it as deprecated
def create_langchain_llm(provider: str, model: str, temperature: float, api_key: str = None, api_base: str = None):
    """DEPRECATED: Use create_crewai_llm instead.
    
    This function is kept for backward compatibility but will be removed in a future version.
    """
    import warnings
    warnings.warn(
        "create_langchain_llm is deprecated. Use create_crewai_llm instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return create_crewai_llm(provider, model, temperature, api_key, api_base)

def get_agent_llm_config(llm_config: Any) -> tuple:
    """Extract LLM configuration parameters from config object.
    
    Args:
        llm_config: LLMConfig object or dictionary containing LLM settings
        
    Returns:
        Tuple of (provider, model, temperature, api_key, api_base, additional_params)
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
    
    if hasattr(llm_config, 'additional_params'):
        additional_params = llm_config.additional_params
    else:
        additional_params = llm_config.get("additional_params", {})
    
    return provider, model, temperature, api_key, api_base, additional_params

# Global instance of the config manager
llm_config_manager = LLMConfigManager() 