import os
import requests
import json
import time
import uuid # NEW: For generating unique folder names
import logging
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)  # Enable CORS for all routes
# Define the base directory for saving generated images
# This will be 'jewelry_designer/static/generated_designs'
GENERATED_IMAGES_DIR = os.path.join(app.static_folder, 'generated_designs')
os.makedirs(GENERATED_IMAGES_DIR, exist_ok=True) # Ensure the directory exists

app.logger.setLevel(logging.INFO)

# Create a handler for console output
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
app.logger.addHandler(console_handler)

# --- Configuration ---
LEONARDO_API_KEY = os.getenv("LEONARDO_API_KEY")
LEONARDO_API_BASE_URL = "https://cloud.leonardo.ai/api/rest/v1"

if not LEONARDO_API_KEY:
    app.logger.critical("LEONARDO_API_KEY environment variable not set. Please set it in your .env file.")
    raise ValueError("LEONARDO_API_KEY environment variable not set.")

# --- Routes ---

@app.route('/')
def index():
    app.logger.info("Serving index.html page.")
    return render_template('index.html')

@app.route('/generate-jewelry', methods=['POST'])
def generate_jewelry():
    data = request.json
    app.logger.info(f"Received data from frontend: {data}")

    # Extract data
    jewelry_type = data.get('jewelry_type')
    metal_type = data.get('metal_type')
    stone_type = data.get('stone_type')
    gender = data.get('gender')
    description = data.get('description', '')
    model = data.get('model', '5c232a9e-9061-4777-980a-ddc8e65647c6') # Default model
    num_images = data.get('numImages', 1)

    # Ensure num_images is an integer and within valid range
    try:
        num_images = int(num_images)
        if not (1 <= num_images <= 8):
            app.logger.warning(f"Invalid num_images received: {num_images}. Defaulting to 4.")
            num_images = 4
    except (ValueError, TypeError):
        app.logger.warning(f"Non-integer num_images received: {num_images}. Defaulting to 4.")
        num_images = 4

    # Construct prompt
    prompt_parts = []
    if gender:
        prompt_parts.append(f"{gender}'s")
    if metal_type:
        prompt_parts.append(metal_type)
    if jewelry_type:
        prompt_parts.append(jewelry_type)
    if stone_type:
        prompt_parts.append(f"with {stone_type}")
    if description:
        prompt_parts.append(f"details: {description}")

    # Adjusted base_prompt for desired image quality
    base_prompt = "Generate low-pixel, photorealistic product images for a jewelry designer. "
    full_prompt = f"{base_prompt} {' '.join(prompt_parts)}. The images should be realistic, detailed, and suitable for a jewelry catalog."

    app.logger.info(f"Generated prompt: {full_prompt}")

    headers = {
        "Authorization": f"Bearer {LEONARDO_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "prompt": full_prompt,
        "modelId": model,
        "num_images": num_images,
        "width": 1024, # Ensure width and height are 1024
        "height": 1024,
        "guidance_scale": 7,
        "negative_prompt": "blurry, low quality, deformed, malformed, text, watermark, ugly, poor lighting",
        "public": False
    }

    try:
        generate_response = requests.post(
            f"{LEONARDO_API_BASE_URL}/generations",
            headers=headers,
            json=payload
        )
        generate_response.raise_for_status()
        generation_data = generate_response.json()

        generation_id = generation_data['sdGenerationJob']['generationId']
        app.logger.info(f"Generation job started with ID: {generation_id}")

        leonardo_image_urls = [] # Store URLs from Leonardo.ai temporarily
        for _ in range(30):
            status_response = requests.get(
                f"{LEONARDO_API_BASE_URL}/generations/{generation_id}",
                headers=headers
            )
            status_response.raise_for_status()
            status_data = status_response.json()

            gen_info = status_data.get('generations_by_pk')
            if gen_info and gen_info.get('status') == 'COMPLETE':
                app.logger.info("Generation complete!")
                for image in gen_info.get('generated_images', []):
                    leonardo_image_urls.append(image['url'])
                break
            elif gen_info and gen_info.get('status') == 'FAILED':
                app.logger.error("Generation failed!")
                return jsonify({"error": "Image generation failed."}), 500

            time.sleep(1)

        if not leonardo_image_urls:
            app.logger.error("Image generation timed out or no images returned from Leonardo.ai.")
            return jsonify({"error": "Image generation timed out or no images returned."}), 500

        # --- NEW: Save images locally and store prompt ---
        local_image_paths = []
        folder_uuid = str(uuid.uuid4()) # Generate a unique UUID for the folder
        save_dir = os.path.join(GENERATED_IMAGES_DIR, folder_uuid)
        os.makedirs(save_dir, exist_ok=True)
        app.logger.info(f"Created local folder: {save_dir}")

        # Save prompt to prompt.txt
        prompt_file_path = os.path.join(save_dir, 'prompt.txt')
        with open(prompt_file_path, 'w', encoding='utf-8') as f:
            f.write(full_prompt)
        app.logger.info(f"Saved prompt to {prompt_file_path}")

        for i, img_url in enumerate(leonardo_image_urls):
            try:
                img_data = requests.get(img_url).content
                img_filename = f"image_{i+1}.png" # Assuming PNG for simplicity
                img_path = os.path.join(save_dir, img_filename)
                with open(img_path, 'wb') as handler:
                    handler.write(img_data)
                local_image_paths.append(f"/static/generated_designs/{folder_uuid}/{img_filename}")
                app.logger.info(f"Saved image {img_filename} to {save_dir}")
            except Exception as img_save_err:
                app.logger.error(f"Failed to save image from {img_url}: {img_save_err}")
                # Continue even if one image fails to save

        if not local_image_paths:
            app.logger.error("No images were successfully saved locally.")
            return jsonify({"error": "No images were successfully saved locally."}), 500

        app.logger.info(f"Generated and saved local image URLs: {local_image_paths}")
        return jsonify({"images": local_image_paths}) # Return local paths
        # --- END NEW: Save images locally ---

    except requests.exceptions.HTTPError as http_err:
        app.logger.error(f"HTTP error occurred: {http_err}")
        app.logger.error(f"Response content: {http_err.response.text}")
        return jsonify({"error": f"API error: {http_err.response.text}"}), http_err.response.status_code
    except requests.exceptions.RequestException as req_err:
        app.logger.error(f"Request error occurred: {req_err}")
        return jsonify({"error": "Network or API connection error."}), 500
    except Exception as e:
        app.logger.critical(f"An unexpected error occurred: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred."}), 500

# --- NEW API Endpoint to get saved designs ---
@app.route('/get-saved-designs', methods=['GET'])
def get_saved_designs():
    app.logger.info("Fetching saved designs.")
    saved_designs_data = []
    # List directories in GENERATED_IMAGES_DIR (each is a UUID folder)
    for folder_name in os.listdir(GENERATED_IMAGES_DIR):
        folder_path = os.path.join(GENERATED_IMAGES_DIR, folder_name)
        if os.path.isdir(folder_path):
            prompt_file = os.path.join(folder_path, 'prompt.txt')
            prompt_text = "No prompt available."
            if os.path.exists(prompt_file):
                try:
                    with open(prompt_file, 'r', encoding='utf-8') as f:
                        prompt_text = f.read()
                except Exception as e:
                    app.logger.error(f"Error reading prompt.txt in {folder_name}: {e}")

            images_in_folder = []
            for filename in os.listdir(folder_path):
                if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                    images_in_folder.append(f"/static/generated_designs/{folder_name}/{filename}")

            if images_in_folder: # Only add if there are images
                saved_designs_data.append({
                    "folder_id": folder_name,
                    "prompt": prompt_text,
                    "images": sorted(images_in_folder) # Sort for consistent order
                })
    # Sort designs by folder_id (UUIDs are not chronologically sortable, but this provides consistent order)
    # You might want to store a timestamp in prompt.txt if chronological order is important.
    saved_designs_data.sort(key=lambda x: x['folder_id'], reverse=True) # Show newest first

    app.logger.info(f"Found {len(saved_designs_data)} saved design folders.")
    return jsonify(saved_designs_data)
# --- END NEW API Endpoint ---

if __name__ == '__main__':
    # Define the base directory for saving generated images
    # This needs to be done before app.run() if app.static_folder is used in the global scope
    # For clarity, moved it to the top.
    app.run(debug=True, port=5000, host='0.0.0.0')