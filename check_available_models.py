import google.generativeai as genai
import os
import sys

def get_api_key():
    """Try to read API key from .streamlit/secrets.toml"""
    secrets_path = os.path.join(".streamlit", "secrets.toml")
    api_key = None
    
    if os.path.exists(secrets_path):
        try:
            with open(secrets_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # Basic parse for GEMINI_API_KEY = "..." or api_key = "..." inside [gemini]
                    # This is a simple parser, might need adjustment for complex TOML
                    if line.startswith("GEMINI_API_KEY"):
                        parts = line.split("=", 1)
                        if len(parts) == 2:
                            api_key = parts[1].strip().strip('"').strip("'")
                            break
                    elif line.startswith("api_key"): # In case it's under [gemini] block but indentation might vary
                         parts = line.split("=", 1)
                         if len(parts) == 2:
                            # Verify if we are likely in a block context if needed, but for now just grab it
                            possible_key = parts[1].strip().strip('"').strip("'")
                            if len(possible_key) > 20: # API keys are usually long
                                api_key = possible_key
                                break
        except Exception as e:
            print(f"Error reading secrets.toml: {e}")

    # Fallback to environment variable
    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY")
        
    return api_key

def list_models():
    api_key = get_api_key()
    if not api_key:
        print("Error: Could not find GEMINI_API_KEY in .streamlit/secrets.toml or environment variables.")
        return

    print(f"Found API Key: {api_key[:5]}...{api_key[-5:]}")
    
    try:
        genai.configure(api_key=api_key)
        print("\nFetching available models...")
        models = genai.list_models()
        
        found = False
        print("\nAvailable Models (supporting generateContent):")
        for m in models:
            if 'generateContent' in m.supported_generation_methods:
                print(f"   - {m.name}")
                found = True
        
        if not found:
            print("   (No models found matching 'generateContent')")
            
    except Exception as e:
        print(f"\nError listing models: {e}")

if __name__ == "__main__":
    list_models()
