"""
Constants for the multiagent debugger.
"""

# Environment variable mappings for different providers
ENV_VARS = {
    "openai": [
        "OPENAI_API_KEY",
        "OPENAI_API_BASE"
    ],
    "anthropic": [
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_API_BASE"
    ],
    "google": [
        "GOOGLE_API_KEY",
        "GOOGLE_API_BASE"
    ],
    "ollama": [
        "OLLAMA_API_BASE"
    ],
    "azure": [
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT"
    ],
    "bedrock": [
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_REGION"
    ],
    "cohere": [
        "COHERE_API_KEY"
    ],
    "mistral": [
        "MISTRAL_API_KEY"
    ],
    "groq": [
        "GROQ_API_KEY"
    ],
    "perplexity": [
        "PERPLEXITY_API_KEY"
    ],
    "together": [
        "TOGETHER_API_KEY"
    ],
    "fireworks": [
        "FIREWORKS_API_KEY"
    ],
    "deepseek": [
        "DEEPSEEK_API_KEY"
    ],
    "claude": [
        "CLAUDE_API_KEY"
    ],
    "gemini": [
        "GOOGLE_API_KEY",
        "GOOGLE_API_BASE"
    ],
    "nvidia_nim": [
        "NVIDIA_NIM_API_KEY",
        "NVIDIA_NIM_API_BASE"
    ],
    "watson": [
        "WATSON_API_KEY",
        "WATSON_API_BASE"
    ],
    "huggingface": [
        "HUGGINGFACE_API_KEY",
        "HUGGINGFACE_API_BASE"
    ],
    "sambanova": [
        "SAMBANOVA_API_KEY",
        "SAMBANOVA_API_BASE"
    ],
    "mistral": [
        "MISTRAL_API_KEY"
    ],
    "cohere": [
        "COHERE_API_KEY"
    ],
    "deepseek": [
        "DEEPSEEK_API_KEY"
    ],
    "perplexity": [
        "PERPLEXITY_API_KEY"
    ],
    "azure": [
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT"
    ],
    "meta_llama": [
        "META_LLAMA_API_KEY"
    ],
    "together_ai": [
        "TOGETHER_API_KEY"
    ],
    "fireworks_ai": [
        "FIREWORKS_API_KEY"
    ]
}

# Default API base URLs
DEFAULT_API_BASES = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com",
    "google": "https://generativelanguage.googleapis.com",
    "ollama": "http://localhost:11434",
    "azure": None,  # Must be provided by user
    "bedrock": None,  # Uses AWS SDK
    "cohere": "https://api.cohere.ai",
    "mistral": "https://api.mistral.ai",
    "groq": "https://api.groq.com",
    "perplexity": "https://api.perplexity.ai",
    "together": "https://api.together.xyz",
    "fireworks": "https://api.fireworks.ai",
    "deepseek": "https://api.deepseek.com",
    "claude": "https://api.anthropic.com",
    "gemini": "https://generativelanguage.googleapis.com",
    "nvidia_nim": "https://api.nvcf.nvidia.com",
    "watson": "https://us-south.ml.cloud.ibm.com",
    "huggingface": "https://api-inference.huggingface.co",
    "sambanova": "https://api.sambanova.ai",
    "mistral": "https://api.mistral.ai",
    "cohere": "https://api.cohere.ai",
    "deepseek": "https://api.deepseek.com",
    "perplexity": "https://api.perplexity.ai",
    "azure": None,  # Must be provided by user
    "meta_llama": "https://api.llama.meta.com",
    "together_ai": "https://api.together.xyz",
    "fireworks_ai": "https://api.fireworks.ai"
}

# CrewAI specific environment variables
CREWAI_ENV_VARS = {
    "CHROMA_OPENAI_API_KEY",  # For CrewAI memory
    "CHROMA_ANTHROPIC_API_KEY",  # For CrewAI memory with Anthropic
    "CHROMA_GOOGLE_API_KEY",  # For CrewAI memory with Google
}

# Cache settings
CACHE_DIR = "~/.cache/multiagent-debugger"
CACHE_FILE = "model_info.json"
CACHE_EXPIRY_HOURS = 24

# Model information URL
MODEL_INFO_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
