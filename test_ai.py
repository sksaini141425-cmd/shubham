import google.generativeai as genai
import os

api_key = os.environ.get('GEMINI_API_KEY', 'AIzaSyDa6_XPP2Gk_iNImqHAVZ2dGRqUuLnyVqo')
genai.configure(api_key=api_key)

try:
    print("Available Models:")
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(m.name)
except Exception as e:
    import traceback
    traceback.print_exc()
