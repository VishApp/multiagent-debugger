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
        fallback_models = {
            "openai": [
                "gpt-4",
                "gpt-4.1",
                "gpt-4.1-mini-2025-04-14",
                "gpt-4.1-nano-2025-04-14",
                "gpt-4o",
                "gpt-4o-mini",
                "o1-mini",
                "o1-preview",
            ],
            "anthropic": [
                "claude-3-5-sonnet-20240620",
                "claude-3-sonnet-20240229",
                "claude-3-opus-20240229",
                "claude-3-haiku-20240307",
            ],
            "google": [
                "gemini/gemini-1.5-flash",
                "gemini/gemini-1.5-pro",
                "gemini/gemini-2.0-flash-lite-001",
                "gemini/gemini-2.0-flash-001",
                "gemini/gemini-2.0-flash-thinking-exp-01-21",
                "gemini/gemini-2.5-flash-preview-04-17",
                "gemini/gemini-2.5-pro-exp-03-25",
                "gemini/gemini-gemma-2-9b-it",
                "gemini/gemini-gemma-2-27b-it",
                "gemini/gemma-3-1b-it",
                "gemini/gemma-3-4b-it",
                "gemini/gemma-3-12b-it",
                "gemini/gemma-3-27b-it",
            ],
            "gemini": [
                "gemini/gemini-1.5-flash",
                "gemini/gemini-1.5-pro",
                "gemini/gemini-2.0-flash-lite-001",
                "gemini/gemini-2.0-flash-001",
                "gemini/gemini-2.0-flash-thinking-exp-01-21",
                "gemini/gemini-2.5-flash-preview-04-17",
                "gemini/gemini-2.5-pro-exp-03-25",
                "gemini/gemini-gemma-2-9b-it",
                "gemini/gemini-gemma-2-27b-it",
                "gemini/gemma-3-1b-it",
                "gemini/gemma-3-4b-it",
                "gemini/gemma-3-12b-it",
                "gemini/gemini-3-27b-it",
            ],
            "nvidia_nim": [
                "nvidia_nim/nvidia/mistral-nemo-minitron-8b-8k-instruct",
                "nvidia_nim/nvidia/nemotron-4-mini-hindi-4b-instruct",
                "nvidia_nim/nvidia/llama-3.1-nemotron-70b-instruct",
                "nvidia_nim/nvidia/llama3-chatqa-1.5-8b",
                "nvidia_nim/nvidia/llama3-chatqa-1.5-70b",
                "nvidia_nim/nvidia/vila",
                "nvidia_nim/nvidia/neva-22",
                "nvidia_nim/nvidia/nemotron-mini-4b-instruct",
                "nvidia_nim/nvidia/usdcode-llama3-70b-instruct",
                "nvidia_nim/nvidia/nemotron-4-340b-instruct",
                "nvidia_nim/meta/codellama-70b",
                "nvidia_nim/meta/llama2-70b",
                "nvidia_nim/meta/llama3-8b-instruct",
                "nvidia_nim/meta/llama3-70b-instruct",
                "nvidia_nim/meta/llama-3.1-8b-instruct",
                "nvidia_nim/meta/llama-3.1-70b-instruct",
                "nvidia_nim/meta/llama-3.1-405b-instruct",
                "nvidia_nim/meta/llama-3.2-1b-instruct",
                "nvidia_nim/meta/llama-3.2-3b-instruct",
                "nvidia_nim/meta/llama-3.2-11b-vision-instruct",
                "nvidia_nim/meta/llama-3.2-90b-vision-instruct",
                "nvidia_nim/meta/llama-3.1-70b-instruct",
                "nvidia_nim/google/gemma-7b",
                "nvidia_nim/google/gemma-2b",
                "nvidia_nim/google/codegemma-7b",
                "nvidia_nim/google/codegemma-1.1-7b",
                "nvidia_nim/google/recurrentgemma-2b",
                "nvidia_nim/google/gemma-2-9b-it",
                "nvidia_nim/google/gemma-2-27b-it",
                "nvidia_nim/google/gemma-2-2b-it",
                "nvidia_nim/google/deplot",
                "nvidia_nim/google/paligemma",
                "nvidia_nim/mistralai/mistral-7b-instruct-v0.2",
                "nvidia_nim/mistralai/mixtral-8x7b-instruct-v0.1",
                "nvidia_nim/mistralai/mistral-large",
                "nvidia_nim/mistralai/mixtral-8x22b-instruct-v0.1",
                "nvidia_nim/mistralai/mistral-7b-instruct-v0.3",
                "nvidia_nim/nv-mistralai/mistral-nemo-12b-instruct",
                "nvidia_nim/mistralai/mamba-codestral-7b-v0.1",
                "nvidia_nim/microsoft/phi-3-mini-128k-instruct",
                "nvidia_nim/microsoft/phi-3-mini-4k-instruct",
                "nvidia_nim/microsoft/phi-3-small-8k-instruct",
                "nvidia_nim/microsoft/phi-3-small-128k-instruct",
                "nvidia_nim/microsoft/phi-3-medium-4k-instruct",
                "nvidia_nim/microsoft/phi-3-medium-128k-instruct",
                "nvidia_nim/microsoft/phi-3.5-mini-instruct",
                "nvidia_nim/microsoft/phi-3.5-moe-instruct",
                "nvidia_nim/microsoft/kosmos-2",
                "nvidia_nim/microsoft/phi-3-vision-128k-instruct",
                "nvidia_nim/microsoft/phi-3.5-vision-instruct",
                "nvidia_nim/databricks/dbrx-instruct",
                "nvidia_nim/snowflake/arctic",
                "nvidia_nim/aisingapore/sea-lion-7b-instruct",
                "nvidia_nim/ibm/granite-8b-code-instruct",
                "nvidia_nim/ibm/granite-34b-code-instruct",
                "nvidia_nim/ibm/granite-3.0-8b-instruct",
                "nvidia_nim/ibm/granite-3.0-3b-a800m-instruct",
                "nvidia_nim/mediatek/breeze-7b-instruct",
                "nvidia_nim/upstage/solar-10.7b-instruct",
                "nvidia_nim/writer/palmyra-med-70b-32k",
                "nvidia_nim/writer/palmyra-med-70b",
                "nvidia_nim/writer/palmyra-fin-70b-32k",
                "nvidia_nim/01-ai/yi-large",
                "nvidia_nim/deepseek-ai/deepseek-coder-6.7b-instruct",
                "nvidia_nim/rakuten/rakutenai-7b-instruct",
                "nvidia_nim/rakuten/rakutenai-7b-chat",
                "nvidia_nim/baichuan-inc/baichuan2-13b-chat",
            ],
            "groq": [
                "groq/llama-3.1-8b-instant",
                "groq/llama-3.1-70b-versatile",
                "groq/llama-3.1-405b-reasoning",
                "groq/gemma2-9b-it",
                "groq/gemma-7b-it",
            ],
            "ollama": ["ollama/llama3.1", "ollama/mixtral"],
            "watson": [
                "watsonx/meta-llama/llama-3-1-70b-instruct",
                "watsonx/meta-llama/llama-3-1-8b-instruct",
                "watsonx/meta-llama/llama-3-2-11b-vision-instruct",
                "watsonx/meta-llama/llama-3-2-1b-instruct",
                "watsonx/meta-llama/llama-3-2-90b-vision-instruct",
                "watsonx/meta-llama/llama-3-405b-instruct",
                "watsonx/mistral/mistral-large",
                "watsonx/ibm/granite-3-8b-instruct",
            ],
            "bedrock": [
                "bedrock/us.amazon.nova-pro-v1:0",
                "bedrock/us.amazon.nova-micro-v1:0",
                "bedrock/us.amazon.nova-lite-v1:0",
                "bedrock/us.anthropic.claude-3-5-sonnet-20240620-v1:0",
                "bedrock/us.anthropic.claude-3-5-haiku-20241022-v1:0",
                "bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                "bedrock/us.anthropic.claude-3-7-sonnet-20250219-v1:0",
                "bedrock/us.anthropic.claude-3-sonnet-20240229-v1:0",
                "bedrock/us.anthropic.claude-3-opus-20240229-v1:0",
                "bedrock/us.anthropic.claude-3-haiku-20240307-v1:0",
                "bedrock/us.meta.llama3-2-11b-instruct-v1:0",
                "bedrock/us.meta.llama3-2-3b-instruct-v1:0",
                "bedrock/us.meta.llama3-2-90b-instruct-v1:0",
                "bedrock/us.meta.llama3-2-1b-instruct-v1:0",
                "bedrock/us.meta.llama3-1-8b-instruct-v1:0",
                "bedrock/us.meta.llama3-1-70b-instruct-v1:0",
                "bedrock/us.meta.llama3-3-70b-instruct-v1:0",
                "bedrock/us.meta.llama3-1-405b-instruct-v1:0",
                "bedrock/eu.anthropic.claude-3-5-sonnet-20240620-v1:0",
                "bedrock/eu.anthropic.claude-3-sonnet-20240229-v1:0",
                "bedrock/eu.anthropic.claude-3-haiku-20240307-v1:0",
                "bedrock/eu.meta.llama3-2-3b-instruct-v1:0",
                "bedrock/eu.meta.llama3-2-1b-instruct-v1:0",
                "bedrock/apac.anthropic.claude-3-5-sonnet-20240620-v1:0",
                "bedrock/apac.anthropic.claude-3-5-sonnet-20241022-v2:0",
                "bedrock/apac.anthropic.claude-3-sonnet-20240229-v1:0",
                "bedrock/apac.anthropic.claude-3-haiku-20240307-v1:0",
                "bedrock/amazon.nova-pro-v1:0",
                "bedrock/amazon.nova-micro-v1:0",
                "bedrock/amazon.nova-lite-v1:0",
                "bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0",
                "bedrock/anthropic.claude-3-5-haiku-20241022-v1:0",
                "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0",
                "bedrock/anthropic.claude-3-7-sonnet-20250219-v1:0",
                "bedrock/anthropic.claude-3-sonnet-20240229-v1:0",
                "bedrock/anthropic.claude-3-opus-20240229-v1:0",
                "bedrock/anthropic.claude-3-haiku-20240307-v1:0",
                "bedrock/anthropic.claude-v2:1",
                "bedrock/anthropic.claude-v2",
                "bedrock/anthropic.claude-instant-v1",
                "bedrock/meta.llama3-1-405b-instruct-v1:0",
                "bedrock/meta.llama3-1-70b-instruct-v1:0",
                "bedrock/meta.llama3-1-8b-instruct-v1:0",
                "bedrock/meta.llama3-70b-instruct-v1:0",
                "bedrock/meta.llama3-8b-instruct-v1:0",
                "bedrock/amazon.titan-text-lite-v1",
                "bedrock/amazon.titan-text-express-v1",
                "bedrock/cohere.command-text-v14",
                "bedrock/ai21.j2-mid-v1",
                "bedrock/ai21.j2-ultra-v1",
                "bedrock/ai21.jamba-instruct-v1:0",
                "bedrock/mistral.mistral-7b-instruct-v0:2",
                "bedrock/mistral.mixtral-8x7b-instruct-v0:1",
            ],
            "huggingface": [
                "huggingface/meta-llama/Meta-Llama-3.1-8B-Instruct",
                "huggingface/mistralai/Mixtral-8x7B-Instruct-v0.1",
                "huggingface/tiiuae/falcon-180B-chat",
                "huggingface/google/gemma-7b-it",
            ],
            "sambanova": [
                "sambanova/Meta-Llama-3.3-70B-Instruct",
                "sambanova/QwQ-32B-Preview",
                "sambanova/Qwen2.5-72B-Instruct",
                "sambanova/Qwen2.5-Coder-32B-Instruct",
                "sambanova/Meta-Llama-3.1-405B-Instruct",
                "sambanova/Meta-Llama-3.1-70B-Instruct",
                "sambanova/Meta-Llama-3.1-8B-Instruct",
                "sambanova/Llama-3.2-90B-Vision-Instruct",
                "sambanova/Llama-3.2-11B-Vision-Instruct",
                "sambanova/Meta-Llama-3.2-3B-Instruct",
                "sambanova/Meta-Llama-3.2-1B-Instruct",
            ],
            "mistral": [
                "mistral-large-latest",
                "mistral-medium-latest", 
                "mistral-small-latest",
                "open-mistral-7b",
                "open-mistral-8x7b",
                "open-mistral-8x22b",
                "mistral-7b-instruct-v0.2",
                "mixtral-8x7b-instruct-v0.1",
                "mixtral-8x22b-instruct-v0.1",
            ],
            "cohere": [
                "command",
                "command-light", 
                "command-nightly",
                "command-light-nightly",
                "base",
                "base-light",
                "command-text-v14",
            ],
            "deepseek": [
                "deepseek-chat",
                "deepseek-coder",
                "deepseek-coder-33b-instruct",
                "deepseek-coder-6.7b-instruct",
            ],
            "perplexity": [
                "llama-3.1-8b-instruct",
                "llama-3.1-70b-instruct",
                "llama-3.1-405b-instruct",
                "mixtral-8x7b-instruct",
                "codellama-70b-instruct",
                "mistral-7b-instruct",
            ],
            "azure": [
                "gpt-4",
                "gpt-4-turbo",
                "gpt-4o",
                "gpt-4o-mini",
                "gpt-3.5-turbo",
                "gpt-3.5-turbo-16k",
            ],
            "meta_llama": [
                "meta-llama/Llama-2-70b-chat-hf",
                "meta-llama/Llama-2-13b-chat-hf",
                "meta-llama/Llama-2-7b-chat-hf",
                "meta-llama/Llama-3-8b-instruct",
                "meta-llama/Llama-3-70b-instruct",
                "meta-llama/Llama-3.1-8b-instruct",
                "meta-llama/Llama-3.1-70b-instruct",
                "meta-llama/Llama-3.1-405b-instruct",
            ],
            "together_ai": [
                "togethercomputer/llama-2-70b",
                "togethercomputer/llama-2-13b",
                "togethercomputer/llama-2-7b",
                "meta-llama/Llama-2-70b-chat-hf",
                "meta-llama/Llama-2-13b-chat-hf",
                "meta-llama/Llama-2-7b-chat-hf",
            ],
            "fireworks_ai": [
                "accounts/fireworks/models/llama-v2-7b-chat",
                "accounts/fireworks/models/llama-v2-13b-chat",
                "accounts/fireworks/models/llama-v2-70b-chat",
                "accounts/fireworks/models/mistral-7b-instruct",
                "accounts/fireworks/models/mixtral-8x7b-instruct",
            ],
        }
        
        # If no provider specified, return all provider names
        if not provider:
            return list(fallback_models.keys())
        
        return fallback_models.get(provider.lower(), [])
    
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
    elif provider in ["google", "gemini"]:
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
    elif provider == "mistral":
        from langchain_mistralai import ChatMistralAI
        return ChatMistralAI(
            model=model,
            temperature=temperature,
            mistral_api_key=api_key
        )
    elif provider == "deepseek":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            openai_api_key=api_key,
            openai_api_base="https://api.deepseek.com/v1"
        )
    elif provider == "perplexity":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            openai_api_key=api_key,
            openai_api_base="https://api.perplexity.ai"
        )
    elif provider == "azure":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            openai_api_key=api_key,
            openai_api_base=api_base
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