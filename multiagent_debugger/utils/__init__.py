"""
Utility modules for the multiagent debugger.
"""

from .constants import (
    ENV_VARS,
    DEFAULT_API_BASES,
    CREWAI_ENV_VARS,
    CACHE_DIR,
    CACHE_FILE,
    CACHE_EXPIRY_HOURS,
    MODEL_INFO_URL
)

from .llm_config import (
    LLMConfigManager,
    get_env_var_name_for_provider,
    get_env_var_for_provider,
    get_llm_config,
    get_verbose_flag,
    get_memory_config,
    set_crewai_env_vars,
    create_crewai_llm,
    # create_langchain_llm,  # Deprecated - use create_crewai_llm instead
    get_agent_llm_config,
    llm_config_manager
)

__all__ = [
    'ENV_VARS',
    'DEFAULT_API_BASES', 
    'CREWAI_ENV_VARS',
    'CACHE_DIR',
    'CACHE_FILE',
    'CACHE_EXPIRY_HOURS',
    'MODEL_INFO_URL',
    'LLMConfigManager',
    'get_env_var_name_for_provider',
    'get_env_var_for_provider',
    'get_llm_config',
    'get_verbose_flag',
    'get_memory_config',
    'set_crewai_env_vars',
    'create_crewai_llm',
    'get_agent_llm_config',
    'llm_config_manager'
] 