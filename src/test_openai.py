import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load your project .env file
ENV_PATH = r"C:\Users\91870\OneDrive\Desktop\Agentic\noc_auto\config\.env"
load_dotenv(ENV_PATH)

api_key = os.getenv("GEMINI_API_KEY")
model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-2.0-flash")

print("Loaded ENV from:", ENV_PATH)
print("GEMINI_API_KEY present:", bool(api_key))
print("GEMINI_API_KEY last 6 chars:", api_key[-6:] if api_key else None)
print("GEMINI_MODEL_NAME:", model_name)

# Configure Gemini
try:
    genai.configure(api_key=api_key)
except Exception as e:
    print("Error configuring Gemini:", e)

# Create model instance
try:
    model = genai.GenerativeModel(model_name)
except Exception as e:
    print("Model creation ERROR:", e)
    raise SystemExit

# Try an actual AI request
print("\nTesting Gemini response...\n")
try:
    response = model.generate_content(
        "Write a short professional NOC outage notification email."
    )
    print("Gemini Response:\n")
    print(response.text)
except Exception as e:
    print("Gemini ERROR:", e)
