import ollama

# 1. Setup path and prompts
image_path = '/home/hkuangab/Desktop/UROP 1100R/test_images/hk.jpeg'
visual_query = 'Describe any landmarks, unique buildings, or text on signs in this image.'
inference_query = 'Based on these visual clues, what is the most likely name of this city? Provide the name and a brief reason. What is the name of this city?'

try:
    # --- Step 1: Use moondream to extract visual clues ---
    print("Step 1: Extracting visual clues using moondream...")
    vlm_response = ollama.chat(
        model='moondream',
        messages=[{'role': 'user', 'content': visual_query, 'images': [image_path]}]
    )
    clues = vlm_response['message']['content']
    print(f"Visual Clues: {clues}\n")

    # --- Step 2: Use deepseek to infer the city name ---
    print("Step 2: Inferring city name using deepseek...")
    # Make sure you have pulled deepseek-r1 (e.g., ollama pull deepseek-r1:7b)
    llm_response = ollama.chat(
        model='deepseek-r1:1.5b',
        messages=[{'role': 'user', 'content': f"Visual clues from image: {clues}. {inference_query}"}]
    )

    print("Final Result:")
    print(llm_response['message']['content'])

except Exception as e:
    print(f"Error occurred: {e}")
