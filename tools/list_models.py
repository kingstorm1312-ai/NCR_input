import google.generativeai as genai
import toml
import os

# Load secrets
try:
    with open('.streamlit/secrets.toml', 'r') as f:
        secrets = toml.load(f)
        api_key = secrets.get('GEMINI_API_KEY')
except Exception as e:
    print(f"Error loading secrets: {e}")
    exit()

if not api_key:
    print("API Key not found.")
    exit()

genai.configure(api_key=api_key)

print("Listing available models:")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(m.name)
except Exception as e:
    print(f"Error listing models: {e}")
