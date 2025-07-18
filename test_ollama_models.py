#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test script to list available Ollama models.
This script follows the same client setup pattern used in main.py.
"""

import os
import sys

try:
    import ollama
except ImportError:
    print("Error: ollama package not found")
    print("Install with: pip install ollama")
    sys.exit(1)


def test_ollama_models():
    """
    Test listing available models using the ollama Python SDK.
    Follows the same client setup pattern as in main.py.
    """
    print("Testing Ollama model listing...")
    
    # Configure Ollama client for Docker environment (same pattern as main.py lines 56-63)
    if os.getenv('DOCKER_ENV', 'false').lower() == 'true':
        ollama_host = "http://host.docker.internal:11434"
        print(f"Docker environment detected, using host: {ollama_host}")
        client = ollama.Client(host=ollama_host)
    else:
        ollama_host = "http://localhost:11434"
        print(f"Local environment detected, using host: {ollama_host}")
        client = ollama.Client()
    
    try:
        # Test connection and list models
        print(f"\nConnecting to Ollama at {ollama_host}...")
        models = client.list()
        
        print(f"\nSuccessfully connected to Ollama!")
        print(f"Found {len(models['models'])} available models:\n")
        
        # Display model information
        for i, model in enumerate(models['models'], 1):
            name = model.get('name', 'Unknown')
            size = model.get('size', 0)
            modified = model.get('modified_at', 'Unknown')
            
            # Convert size to human readable format
            if size > 0:
                # Convert bytes to GB
                size_gb = size / (1024**3)
                size_str = f"{size_gb:.2f} GB"
            else:
                size_str = "Unknown size"
            
            print(f"{i}. Model: {name}")
            print(f"   Size: {size_str}")
            print(f"   Modified: {modified}")
            print()
        
        # Return model names for programmatic use
        model_names = [model.get('name', 'Unknown') for model in models['models']]
        return model_names
        
    except Exception as e:
        print(f"Error connecting to Ollama at {ollama_host}: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure Ollama is running")
        print("2. If using Docker, ensure Ollama is accessible at the correct host")
        print("3. Try running 'ollama list' in your terminal to verify Ollama is working")
        return []


if __name__ == "__main__":
    available_models = test_ollama_models()
    
    if available_models:
        print("Available model names for programmatic use:")
        for model in available_models:
            print(f"  - {model}")
    else:
        print("No models found or connection failed.")