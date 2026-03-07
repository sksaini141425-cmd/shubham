import google.generativeai as genai
import sys

def find_best_model(key):
    try:
        genai.configure(api_key=key)
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # Priority mapping
        priority = ["models/gemini-2.0-flash-exp", "models/gemini-1.5-flash-latest", "models/gemini-1.5-flash", "models/gemini-pro"]
        
        best = None
        for p in priority:
            if p in models:
                best = p
                break
        
        if not best and models:
            best = models[0] # Just pick the first one if no priority hit
            
        if best:
            with open("best_model.txt", "w") as f:
                f.write(best)
            print(f"BEST_MODEL: {best}")
        else:
            print("ERROR: No suitable model found.")
            
    except Exception as e:
        print(f"FAILED: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        find_best_model(sys.argv[1])
    else:
        # Fallback to the one we know
        find_best_model("AIzaSyDD473_cCMhXzb9s8iX1U3IWcuz8uYKjbg")
