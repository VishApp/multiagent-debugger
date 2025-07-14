#!/usr/bin/env python3
"""
Generate architecture images from Mermaid files.
"""

import os
import base64
import requests
from pathlib import Path

def generate_mermaid_image(mermaid_code: str, filename: str, output_dir: Path = None) -> str:
    """Generate an image from Mermaid code using the Mermaid API."""
    
    if output_dir is None:
        output_dir = Path("docs/assets")
    
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Mermaid API endpoint
    mermaid_api_url = "https://mermaid.ink/img/"
    
    # Encode the Mermaid code
    encoded_code = base64.urlsafe_b64encode(mermaid_code.encode()).decode()
    
    # Create the full URL
    image_url = f"{mermaid_api_url}{encoded_code}"
    
    # Download the image
    try:
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        
        # Save the image
        image_path = output_dir / f"{filename}.png"
        with open(image_path, 'wb') as f:
            f.write(response.content)
        
        print(f"✅ Generated: {image_path}")
        return str(image_path)
        
    except Exception as e:
        print(f"❌ Error generating image: {e}")
        return None

def read_mermaid_file(file_path: str) -> str:
    """Read Mermaid code from a file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"❌ Error reading file {file_path}: {e}")
        return None

def main():
    """Generate architecture images."""
    print("🏗️ Generating Architecture Images")
    print("=" * 50)
    
    # Define the Mermaid files and their output names
    mermaid_files = [
        ("docs/architecture_simple.mmd", "architecture_simple"),
        ("docs/architecture.mmd", "architecture_detailed")
    ]
    
    for mermaid_file, output_name in mermaid_files:
        print(f"\n📄 Processing: {mermaid_file}")
        
        # Read the Mermaid code
        mermaid_code = read_mermaid_file(mermaid_file)
        if mermaid_code is None:
            continue
        
        # Generate the image
        image_path = generate_mermaid_image(mermaid_code, output_name)
        
        if image_path:
            print(f"📊 Image saved: {image_path}")
        else:
            print(f"❌ Failed to generate image for {mermaid_file}")
    
    print("\n🎉 Architecture image generation completed!")
    print("\n📁 Generated files:")
    print("- docs/assets/architecture_simple.png")
    print("- docs/assets/architecture_detailed.png")
    print("\n📋 You can now use these images in your documentation!")

if __name__ == "__main__":
    main() 