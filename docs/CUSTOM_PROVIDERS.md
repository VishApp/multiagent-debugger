# Custom Providers Guide

The multiagent-debugger supports various LLM providers including custom ones like OpenRouter. This guide explains how to configure and use custom providers.

## Supported Providers

The system supports the following providers out of the box:

- **OpenAI** - Direct OpenAI API access
- **Anthropic** - Claude models
- **Google/Gemini** - Google's Gemini models
- **OpenRouter** - Unified API for multiple providers
- **Groq** - Fast inference API
- **NVIDIA NIM** - NVIDIA's inference microservices
- **Hugging Face** - Open source models
- **Ollama** - Local model inference
- **Watson** - IBM Watson models
- **AWS Bedrock** - Amazon's managed service
- **Azure** - Microsoft Azure OpenAI
- **Cerebras** - Cerebras models
- **SambaNova** - SambaNova models
- **Custom** - Custom API endpoints


### Configuration Example

```yaml
code_path: /app/cm_auth
llm:
  provider: openrouter
  model_name: gpt-4o-mini
  temperature: 0.1
  api_key: sk-or-v1-your-api-key-here
  api_base: https://openrouter.ai/api/v1
  additional_params: {}
log_paths:
  - /app/api.log
verbose: true
```

## Custom Provider Configuration

The "custom" provider allows you to use any API endpoint that follows the OpenAI API format. This is useful for:

- Self-hosted LLM services
- Corporate AI endpoints
- Third-party providers with OpenAI-compatible APIs

### Configuration Example

```yaml
code_path: /path/to/your/code
llm:
  provider: custom
  model_name: gpt-4o
  temperature: 0.1
  api_key: your-custom-api-key
  api_base: https://api.yourprovider.com/v1
  additional_params: {}
log_paths:
  - /path/to/logs/app.log
verbose: true
```

### Requirements

- **API Base URL**: Must be provided (no default)
- **API Key**: Required for authentication
- **Model Name**: Should match what your custom provider supports
- **API Format**: Must follow OpenAI API format

## Adding Custom Providers

To add support for a new custom provider:

### 1. Update Constants

Add the provider to `multiagent_debugger/utils/constants.py`:

```python
# Add to ENV_VARS
"your_provider": [
    {
        "prompt": "Enter your API key (press Enter to skip)",
        "key_name": "YOUR_PROVIDER_API_KEY",
    },
    {
        "prompt": "Enter your API base URL (press Enter to use default)",
        "key_name": "YOUR_PROVIDER_API_BASE",
        "default": "https://api.yourprovider.com/v1",
    }
],

# Add to PROVIDERS list
PROVIDERS = [
    # ... existing providers
    "your_provider",
]

# Add to MODELS dictionary
"your_provider": [
    "model1",
    "model2",
    "model3",
],
```

### 2. Update LLM Configuration

Add environment variable handling in `multiagent_debugger/utils/llm_config.py`:

```python
elif provider.lower() == "your_provider":
    os.environ["YOUR_PROVIDER_API_KEY"] = api_key
    if api_base:
        os.environ["YOUR_PROVIDER_API_BASE"] = api_base
```

### 3. Handle Special Cases

If your provider uses a different API format, add special handling in the `create_crewai_llm` function:

```python
if provider.lower() == "your_provider":
    # Special handling for your provider
    llm = LLM(
        model=model,
        api_key=api_key,
        temperature=temperature,
        base_url=api_base or "https://api.yourprovider.com/v1"
    )
```

## Environment Variables

You can also configure providers using environment variables:

```bash
# OpenRouter
export OPENROUTER_API_KEY="sk-or-v1-your-key"
export OPENROUTER_API_BASE="https://openrouter.ai/api/v1"

# OpenAI
export OPENAI_API_KEY="sk-your-key"

# Anthropic
export ANTHROPIC_API_KEY="sk-ant-your-key"

# Custom Provider
export CUSTOM_API_KEY="your-custom-api-key"
export CUSTOM_API_BASE="https://api.yourprovider.com/v1"
```

## Testing Custom Providers

To test your custom provider configuration:

1. Create a test configuration file
2. Run the debugger with a simple query
3. Check the logs for any configuration errors

Example test:

```bash
# Test with OpenRouter
multiagent-debugger debug "what are the common errors in the log file"
```

## Troubleshooting

### Common Issues

1. **Invalid API Key**: Ensure your API key is correct and has the necessary permissions
2. **Wrong API Base URL**: Verify the API base URL is correct for your provider
3. **Model Not Found**: Check that the model name is supported by your provider
4. **Network Issues**: Ensure your system can reach the provider's API endpoints

### Debug Mode

Enable verbose mode to see detailed configuration information:

```yaml
verbose: true
```

### Provider-Specific Notes

#### OpenRouter
- Uses OpenAI API format with custom base URL
- Supports models from multiple providers
- Requires valid OpenRouter API key

#### Ollama
- Runs locally, no API key required
- Default base URL: `http://localhost:11434`
- Ensure Ollama is running locally

#### AWS Bedrock
- Requires AWS credentials (Access Key ID, Secret Access Key, Region)
- Uses AWS authentication instead of API keys

#### Custom
- Requires both API key and API base URL
- Must follow OpenAI API format
- No default API base URL (must be specified)
- Supports any model name that your custom provider offers

## Best Practices

1. **Use Environment Variables**: Store sensitive information like API keys in environment variables
2. **Test Configuration**: Always test your configuration with a simple query first
3. **Monitor Usage**: Keep track of API usage and costs
4. **Fallback Providers**: Consider having a fallback provider configured
5. **Model Selection**: Choose models appropriate for your use case and budget

## Example Configurations

### OpenRouter with Claude
```yaml
llm:
  provider: openrouter
  model_name: claude-3-5-sonnet
  temperature: 0.1
  api_key: sk-or-v1-your-key
  api_base: https://openrouter.ai/api/v1
```

### Local Ollama
```yaml
llm:
  provider: ollama
  model_name: ollama/llama3.1
  temperature: 0.1
  api_base: http://localhost:11434
```

### AWS Bedrock
```yaml
llm:
  provider: bedrock
  model_name: bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0
  temperature: 0.1
  # AWS credentials from environment variables
```

### Custom Provider
```yaml
llm:
  provider: custom
  model_name: gpt-4o
  temperature: 0.1
  api_key: <API_KEY>...
  api_base: https://<BASE_URL>
```

This guide should help you configure and use custom providers with the multiagent-debugger system. 