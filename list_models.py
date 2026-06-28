import google.generativeai as genai
import sys

# 1. Configure the AI with your API Key
genai.configure(api_key="AIzaSyAgWhY-dOsDuBQnY_RiYqnvU7h5Ny-miU8") 

try:
    print("Available Models for generateContent:")
    for m in genai.list_models():
        if "generateContent" in m.supported_generation_methods:
            print(f"- {m.name}")
except Exception as e:
    print(f"Failed to list models: {e}")
