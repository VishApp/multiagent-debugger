from setuptools import setup, find_packages
import os

# Read the contents of README.md
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read version from package __init__.py
with open(os.path.join("multiagent_debugger", "__init__.py"), "r", encoding="utf-8") as f:
    for line in f:
        if line.startswith("__version__"):
            version = line.split("=")[1].strip().strip('"').strip("'")
            break

setup(
    name="multiagent-debugger",
    version=version,
    author="Vishnu Prasad",
    author_email="vishnuprasadapp@gmail.com",
    description="A multi-agent system for debugging API failures",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/VishApp/multiagent-debugger",
    project_urls={
        "Bug Tracker": "https://github.com/VishApp/multiagent-debugger/issues",
        "Documentation": "https://github.com/VishApp/multiagent-debugger#readme",
        "Source Code": "https://github.com/VishApp/multiagent-debugger",
    },
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Debuggers",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    keywords="debugger, api, multi-agent, crewai, llm, openai, anthropic, debugging",
    python_requires=">=3.8",
    install_requires=[
        "crewai>=0.28.0",
        "pydantic>=2.0.0",
        "python-dotenv>=1.0.0",
        "typer[all]>=0.9.0",
        "openai>=1.0.0",
        "anthropic>=0.8.0",
        "colorlog>=6.7.0",
        "tree-sitter>=0.20.1",
        "gitpython>=3.1.31",
        "pyyaml>=6.0",
        "rich>=13.4.2",
        "requests>=2.25.0",
        "arize-phoenix",
        "arize-phoenix-otel",
        "opentelemetry-api",
        "opentelemetry-sdk",
        "opentelemetry-instrumentation",
        "opentelemetry-instrumentation-openai",
        "opentelemetry-instrumentation-requests",
        "openinference-instrumentation-openai",
        "opentelemetry-instrumentation",
        "openinference-instrumentation-anthropic",
        "openinference-instrumentation-google-genai",
        "openinference-instrumentation-groq",
        "openinference-instrumentation-mistralai",
        "psutil>=5.8.0",
    ],
    entry_points={
        "console_scripts": [
            "multiagent-debugger=multiagent_debugger.cli:cli",
        ],
    },
    include_package_data=True,
    package_data={
        "multiagent_debugger": ["config.yaml.example"],
    },
) 