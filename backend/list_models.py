import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("GEMINI_API_KEY not set")

genai.configure(api_key=api_key)

print("=== AVAILABLE GEMINI MODELS ===\n")

for model in genai.list_models():
    print(f"Model name: {model.name}")
    print(f"  Supported methods: {model.supported_generation_methods}")
    print()
