#!/usr/bin/env python3
"""Build script for the multiagent-debugger package."""
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

# Define the virtual environment directory
VENV_DIR = Path(".venv")

def create_venv():
    """Create a virtual environment if it doesn't exist."""
    if not VENV_DIR.exists():
        print(f"Creating virtual environment in {VENV_DIR}...")
        venv.create(VENV_DIR, with_pip=True)
        print("Virtual environment created.")
    else:
        print(f"Virtual environment already exists in {VENV_DIR}.")

def get_venv_python():
    """Get the path to the Python executable in the virtual environment."""
    if os.name == 'nt':  # Windows
        return str(VENV_DIR / "Scripts" / "python.exe")
    else:  # Unix/Linux/Mac
        return str(VENV_DIR / "bin" / "python")

def run_in_venv(cmd):
    """Run a command in the virtual environment."""
    python = get_venv_python()
    if cmd[0] == sys.executable:
        cmd[0] = python
    return subprocess.check_call(cmd)

def clean():
    """Clean build artifacts."""
    print("Cleaning build artifacts...")
    dirs_to_clean = ["build", "dist", "multiagent_debugger.egg-info"]
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
    print("Cleaned.")

def build():
    """Build the package."""
    create_venv()
    print("Building package...")
    # Install the build module
    run_in_venv([get_venv_python(), "-m", "pip", "install", "--upgrade", "build"])
    # Build the package
    run_in_venv([get_venv_python(), "-m", "build"])
    print("Build complete.")

def install():
    """Install the package in development mode."""
    create_venv()
    print("Installing package in development mode...")
    run_in_venv([get_venv_python(), "-m", "pip", "install", "-e", "."])
    print("Installation complete.")

def test():
    """Run tests."""
    create_venv()
    print("Installing test dependencies...")
    run_in_venv([get_venv_python(), "-m", "pip", "install", "pytest"])
    print("Running tests...")
    run_in_venv([get_venv_python(), "-m", "pytest", "-xvs"])
    print("Tests complete.")

def dist():
    """Build source and wheel distributions."""
    clean()
    build()
    print("Distribution files created in ./dist/")

def upload_test():
    """Upload to TestPyPI."""
    dist()
    print("Uploading to TestPyPI...")
    run_in_venv([get_venv_python(), "-m", "pip", "install", "--upgrade", "twine"])
    run_in_venv([
        get_venv_python(), "-m", "twine", "upload", 
        "--repository-url", "https://test.pypi.org/legacy/", 
        "dist/*"
    ])
    print("Upload to TestPyPI complete.")

def upload():
    """Upload to PyPI."""
    dist()
    print("Uploading to PyPI...")
    run_in_venv([get_venv_python(), "-m", "pip", "install", "--upgrade", "twine"])
    run_in_venv([get_venv_python(), "-m", "twine", "upload", "dist/*"])
    print("Upload to PyPI complete.")

def activate_help():
    """Print help for activating the virtual environment."""
    print("\nTo activate the virtual environment:")
    if os.name == 'nt':  # Windows
        print(f"    {VENV_DIR}\\Scripts\\activate.bat")
    else:  # Unix/Linux/Mac
        print(f"    source {VENV_DIR}/bin/activate")
    print()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python package_builder.py [venv|clean|build|install|test|dist|upload_test|upload]")
        sys.exit(1)
    
    command = sys.argv[1]
    if command == "venv":
        create_venv()
        activate_help()
    elif command == "clean":
        clean()
    elif command == "build":
        build()
    elif command == "install":
        install()
        activate_help()
    elif command == "test":
        test()
    elif command == "dist":
        dist()
    elif command == "upload_test":
        upload_test()
    elif command == "upload":
        upload()
    else:
        print(f"Unknown command: {command}")
        print("Usage: python package_builder.py [venv|clean|build|install|test|dist|upload_test|upload]")
        sys.exit(1) 