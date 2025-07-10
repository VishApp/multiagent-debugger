# Multi-Agent Debugger

A powerful Python package that uses multiple AI agents to debug API failures by analyzing logs, code, and user questions. Built with CrewAI and LangChain, it supports 59+ LLM providers including OpenAI, Anthropic, Google, Ollama, and more.

## Features

- **Multi-Agent Architecture**
  - Question Analysis Agent: Extracts key entities from natural language questions
  - Log Analysis Agent: Searches and filters logs for relevant information
  - Code Analysis Agent: Finds API handlers, dependencies, and error handling code
  - Root Cause Analysis Agent: Synthesizes findings to determine failure causes

- **Comprehensive Analysis Tools**
  - Log Analysis: Search, filter, and extract stack traces from logs
  - Code Analysis: Find API handlers, dependencies, and error handling patterns
  - Natural Language Processing: Convert user questions into structured queries

- **Multi-Provider LLM Support**
  - OpenAI (GPT-4, GPT-3.5-turbo)
  - Anthropic (Claude-3 models)
  - Google (Gemini models)
  - Ollama (Local models)
  - Azure OpenAI
  - AWS Bedrock
  - And 50+ more providers

- **Advanced Features**
  - Dynamic Model Discovery
  - Automatic Provider Configuration
  - Flexible Log Path Configuration
  - Customizable Code Path Analysis
  - Verbose Debug Mode

## Installation

```bash
# From PyPI (coming soon)
pip install multiagent-debugger

# From source
git clone https://github.com/VishApp/multiagent-debugger.git
cd multiagent-debugger
pip install -e .
```

## Quick Start

1. Set up your configuration:
```bash
python -m multiagent_debugger setup
```

2. Debug an API failure:
```bash
python -m multiagent_debugger debug "Why did my /api/users endpoint fail yesterday?"
```

## Configuration

Create a `config.yaml` file (or use the setup command):

```yaml
# Paths to log files
log_paths:
  - /var/log/myapp/app.log
  - /var/log/nginx/access.log

# Path to codebase
code_path: /path/to/your/code

# LLM configuration
llm:
  provider: openai  # or anthropic, google, ollama, etc.
  model_name: gpt-4
  temperature: 0.1
  # api_key: optional, can use environment variable
```

### Environment Variables

Set the appropriate environment variable for your chosen provider:

- OpenAI: `OPENAI_API_KEY`
- Anthropic: `ANTHROPIC_API_KEY`
- Google: `GOOGLE_API_KEY`
- Azure: `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`
- AWS: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`
- See documentation for other providers

## Advanced Usage

### List Available Providers
```bash
python -m multiagent_debugger list-providers
```

### List Models for a Provider
```bash
python -m multiagent_debugger list-models openai
```

### Debug with Custom Config
```bash
python -m multiagent_debugger debug "Question?" --config path/to/config.yaml
```

### Enable Verbose Output
```bash
python -m multiagent_debugger debug "Question?" --verbose
```

## How It Works

1. **Question Analysis**
   - Extracts key information like API routes, timestamps, and error types
   - Structures the query for other agents

2. **Log Analysis**
   - Searches through specified log files
   - Filters relevant log entries
   - Extracts stack traces and error patterns

3. **Code Analysis**
   - Locates relevant API handlers
   - Identifies dependencies and error handlers
   - Maps the code structure

4. **Root Cause Analysis**
   - Synthesizes information from other agents
   - Determines the most likely cause
   - Provides actionable insights

## Development

```bash
# Create virtual environment
python package_builder.py venv

# Install development dependencies
python package_builder.py install

# Run tests
python package_builder.py test

# Build distribution
python package_builder.py dist
```

## Requirements

- Python 3.8+
- Dependencies:
  - crewai>=0.28.0
  - langchain>=0.0.267
  - pydantic>=2.0.0
  - And others (see requirements.txt)

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

- GitHub Issues: [Report a bug](https://github.com/VishApp/multiagent-debugger/issues)
- Documentation: [Read more](https://github.com/VishApp/multiagent-debugger#readme)