import os
import requests
import json
import time
import uuid
import logging
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import google.generativeai as genai # NEW: Import Gemini library

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

# Define the base directory for saving generated images
GENERATED_IMAGES_DIR = os.path.join(app.static_folder, 'generated_designs')
os.makedirs(GENERATED_IMAGES_DIR, exist_ok=True)

app.logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
app.logger.addHandler(console_handler)

# --- Configuration for Leonardo.ai ---
LEONARDO_API_KEY = os.getenv("LEONARDO_API_KEY")
LEONARDO_API_BASE_URL = "https://cloud.leonardo.ai/api/rest/v1"
LEONARDO_DEFAULT_MODEL = "5c232a9e-9061-4777-980a-ddc8e65647c6" # Phoenix Basic Model

# --- Configuration for Together.ai ---
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
TOGETHER_API_BASE_URL = "https://api.together.ai/v1"
TOGETHER_FLUX1_MODEL = "black-forest-labs/FLUX.1-dev" # Verify this model string for image generation

# --- Configuration for Google Gemini ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") # NEW
if GEMINI_API_KEY: # Configure Gemini only if API key is present
    genai.configure(api_key=GEMINI_API_KEY)
    GEMINI_MODEL = genai.GenerativeModel('gemini-1.5-flash') # Use Gemini 1.5 Flash
else:
    app.logger.warning("GEMINI_API_KEY environment variable not set. Prompt enhancement with Gemini will not be available.")
    GEMINI_MODEL = None


# Verify API keys
if not LEONARDO_API_KEY:
    app.logger.critical("LEONARDO_API_KEY environment variable not set.")
    raise ValueError("LEONARDO_API_KEY environment variable not set.")

if not TOGETHER_API_KEY:
    app.logger.warning("TOGETHER_API_KEY environment variable not set. Together.ai integration will not work.")


# --- Helper Function to Save Images ---
def save_images_locally(image_urls, full_prompt):
    local_image_paths = []
    folder_uuid = str(uuid.uuid4())
    save_dir = os.path.join(GENERATED_IMAGES_DIR, folder_uuid)
    os.makedirs(save_dir, exist_ok=True)
    app.logger.info(f"Created local folder: {save_dir}")

    prompt_file_path = os.path.join(save_dir, 'prompt.txt')
    with open(prompt_file_path, 'w', encoding='utf-8') as f:
        f.write(full_prompt)
    app.logger.info(f"Saved prompt to {prompt_file_path}")

    for i, img_url in enumerate(image_urls):
        try:
            img_data = requests.get(img_url).content
            img_filename = f"image_{i+1}.png"
            img_path = os.path.join(save_dir, img_filename)
            with open(img_path, 'wb') as handler:
                handler.write(img_data)
            local_image_paths.append(f"/static/generated_designs/{folder_uuid}/{img_filename}")
            app.logger.info(f"Saved image {img_filename} to {save_dir}")
        except Exception as img_save_err:
            app.logger.error(f"Failed to save image from {img_url}: {img_save_err}")
    return local_image_paths

# --- NEW: Function to enhance prompt using Gemini ---
def enhance_prompt_with_gemini(user_prompt):
    app.logger.info(f"Enhancing prompt with Gemini Input Prompt: '{user_prompt}'")
    if not GEMINI_MODEL:
        app.logger.warning("Gemini API not configured. Skipping prompt enhancement.")
        return user_prompt # Return original prompt if Gemini is not available

    try:
        app.logger.info(f"Attempting to enhance prompt with Gemini: '{user_prompt}'")
        # Construct the message for Gemini
        chat_history = [
            {
                "role": "user",
                "parts": [
                    {
                        "text": f"You are an expert jewelry designer and prompt engineer for AI image generation. Take the following user description for a piece of jewelry and expand it into a highly detailed, photorealistic prompt suitable for an what is asked realistic low resolution text-to-image model like Stable Diffusion XL. Focus on adding details about: \n- Material textures (e.g., polished, brushed, matte, sparkling)\n- Lighting (e.g., studio lighting, soft ambient light, dramatic spotlight, reflections)\n- Background (e.g., minimalist white, dark velvet, natural wood, blurred bokeh)\n- Camera angle/shot (e.g., close-up macro, eye-level, slightly elevated)\n- Refinements to the jewelry's design (e.g., intricate filigree, smooth curves, sharp edges, specific stone cuts).\n- Overall mood or aesthetic (e.g., luxurious, modern, vintage, delicate, bold). Make sure user's prompt should give preferance.\n\nOriginal user description: '{user_prompt}'\n\nReturn ONLY the enhanced prompt string, nothing else. Do not include any conversational text, introductions, or conclusions. Just the prompt."
                    }
                ]
            }
        ]

        response = GEMINI_MODEL.generate_content(chat_history)
        enhanced_text = response.candidates[0].content.parts[0].text.strip()
        app.logger.info(f"Gemini enhanced prompt: '{enhanced_text}'")
        return enhanced_text
    except Exception as e:
        app.logger.error(f"Error enhancing prompt with Gemini: {e}", exc_info=True)
        return user_prompt # Fallback to original prompt on error

# --- Routes ---

@app.route('/')
def index():
    app.logger.info("Serving index.html page.")
    return render_template('index.html')

@app.route('/design')
def design():
    app.logger.info("Serving design.html page.")
    return render_template('design.html')


@app.route('/generate-jewelry', methods=['POST'])
def generate_jewelry():
    data = request.json
    app.logger.info(f"Received data from frontend: {data}")

    jewelry_type = data.get('jewelry_type')
    jewelry_option = data.get('jewelry_option')
    metal_type = data.get('metal_type')
    center_stone_type = data.get('center_stone_type')
    side_stone_type = data.get('side_stone_type')
    center_stone_shape = data.get('center_stone_shape')
    side_stone_shape = data.get('side_stone_shape')
    center_stone_cut = data.get('center_stone_cut')
    side_stone_cut = data.get('side_stone_cut')
    gender = data.get('gender')
    description = data.get('description', '')
    product_style = data.get('product_style', '')  # NEW: Get product style
    setting_type = data.get('setting_type', '')  # NEW: Get setting type
    selected_model_id = data.get('model', 'together-flux1.dev') # Default model is Together-black-forest-labs/FLUX.1-dev
    num_images = data.get('numImages', 1)
    enhance_prompt = data.get('enhancePrompt', False) # NEW: Get checkbox state
    challenge_input = data.get('challenge', '') # NEW: Get challenge passphrase

    # Block if challenge_input is NOT provided OR it's NOT "i love lp" (case-insensitive)
    if not challenge_input or challenge_input.lower() != "i love lp":
        app.logger.warning(f"Unauthorized access attempt detected with challenge: '{challenge_input}'")
        return jsonify({"error": "You are not authorized to use this, please contact info@livepointsolutions.com."}), 403 # 403 Forbidden
    # --- END CORRECTED ---
    # Construct initial prompt
    if jewelry_type == 'ring':
        initial_prompt_for_gemini = f"A high-resolution, ultra-detailed, sharp focus, hyper-realistic jewelry for {gender} rendering of a {jewelry_option} ring, crafted from {metal_type}, featuring a {center_stone_cut} {center_stone_shape} {center_stone_type} center stone, in a {setting_type} setting, with a {side_stone_cut} {side_stone_shape} {side_stone_type} side stones, in a {product_style or '[Product Style]'} style. Photographed in top-down, macro close-up, 3/4 perspective, and side profile displayed on mirrored surface, under softbox studio light, featuring {description or '[Comments]'} --ar 1:1 --v 6 --style raw."

    elif jewelry_type == 'earring':
        initial_prompt_for_gemini = f"A high-resolution, ultra-detailed, sharp focus, hyper-realistic jewelry for {gender} rendering of a {jewelry_option} pair of earrings, crafted from {metal_type}, featuring a mix of {center_stone_cut} {center_stone_shape} {center_stone_type} and {side_stone_cut} {side_stone_shape} {side_stone_type}, in a {setting_type} setting, in a {product_style or '[Product Style]'} style. Photographed in top-down, macro close-up, 3/4 perspective, and side profile displayed on mirrored surface, under softbox studio light, featuring {description or '[Comments]'} --ar 1:1 --v 6 --style raw."

    elif jewelry_type == 'pendant':
        initial_prompt_for_gemini = f"A high-resolution, ultra-detailed, sharp focus, hyper-realistic jewelry for {gender} rendering of a {jewelry_option} pendant, crafted from {metal_type}, featuring a mix of {center_stone_cut} {center_stone_shape} {center_stone_type} and {side_stone_cut} {side_stone_shape} {side_stone_type}, in a {setting_type} setting, in a {product_style or '[Product Style]'} style. Photographed in top-down, macro close-up, 3/4 perspective, and side profile displayed on mirrored surface, under softbox studio light, featuring {description or '[Comments]'} --ar 1:1 --v 6 --style raw."

    elif jewelry_type == 'necklace':
        initial_prompt_for_gemini = f"A high-resolution, ultra-detailed, sharp focus, hyper-realistic jewelry for {gender} rendering of a {jewelry_option} necklace, crafted from {metal_type}, featuring a mix of {center_stone_cut} {center_stone_shape} {center_stone_type} and {side_stone_cut} {side_stone_shape} {side_stone_type}, in a {setting_type} setting, in a {product_style or '[Product Style]'} style. Photographed in top-down, macro close-up, 3/4 perspective, and side profile displayed on mirrored surface, under softbox studio light, featuring {description or '[Comments]'} --ar 1:1 --v 6 --style raw."

    elif jewelry_type == 'bracelet':
        initial_prompt_for_gemini = f"A high-resolution, ultra-detailed, sharp focus, hyper-realistic jewelry for {gender} rendering of a {jewelry_option} bracelet, crafted from {metal_type}, featuring a mix of {center_stone_cut} {center_stone_shape} {center_stone_type} and {side_stone_cut} {side_stone_shape} {side_stone_type}, in a {setting_type} setting, in a {product_style or '[Product Style]'} style. Photographed in top-down, macro close-up, 3/4 perspective, and side profile displayed on mirrored surface, under softbox studio light, featuring {description or '[Comments]'} --ar 1:1 --v 6 --style raw."

    else:
        initial_prompt_for_gemini = "The images should be realistic, detailed, and suitable for a jewelry catalog."

    # Enhance prompt with Gemini if enabled
    if enhance_prompt:  # Only enhance if checkbox is checked
        final_prompt_for_image_gen = enhance_prompt_with_gemini(initial_prompt_for_gemini)
    else:
        final_prompt_for_image_gen = initial_prompt_for_gemini  # Use original prompt

    app.logger.info(f"Final prompt for image generation (enhanced: {enhance_prompt}): {final_prompt_for_image_gen}")
    # --- END Conditional Prompt Enhancement ---

    leonardo_image_urls = []
    together_image_urls = []

    # --- Conditional API Call Logic ---
    if selected_model_id == "together-flux1.dev":
        if not TOGETHER_API_KEY:
            app.logger.error("Together.ai API key is not set. Cannot use Together.ai model.")
            return jsonify({"error": "Together.ai API key not configured."}), 500

        if num_images > 4:
            app.logger.warning(f"Together.ai only supports up to 4 images per request. Reducing num_images from {num_images} to 4.")
            num_images = 4

        model_name_for_together = TOGETHER_FLUX1_MODEL

        headers = {
            "Authorization": f"Bearer {TOGETHER_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "prompt": final_prompt_for_image_gen, # Use enhanced prompt
            "model": model_name_for_together,
            "n": num_images,
            "width": 1024, # Set to 1024x1024 as per earlier requirement
            "height": 1024,
            "negative_prompt": "blurry, low quality, deformed, malformed, text, watermark, ugly, poor lighting",
            "output_format": "jpeg" # Request URLs directly
        }

        try:
            app.logger.info(f"Calling Together.ai API with model: {model_name_for_together}")
            together_response = requests.post(
                f"{TOGETHER_API_BASE_URL}/images/generations",
                headers=headers,
                json=payload
            )
            together_response.raise_for_status()
            together_data = together_response.json()

            if together_data.get('data'): # Together.ai API returns 'data' key for image URLs
                for item in together_data['data']:
                    if item.get('url'):
                        together_image_urls.append(item['url'])
            else:
                app.logger.error(f"Together.ai response missing 'data' or 'url': {together_data}")
                return jsonify({"error": "Together.ai did not return expected image data."}), 500


            app.logger.info(f"Received {len(together_image_urls)} images from Together.ai.")
            local_image_paths = save_images_locally(together_image_urls, final_prompt_for_image_gen) # Save enhanced prompt
            if not local_image_paths:
                return jsonify({"error": "No images were successfully saved locally from Together.ai."}), 500
            return jsonify({"images": local_image_paths})

        except requests.exceptions.HTTPError as http_err:
            app.logger.error(f"Together.ai HTTP error occurred: {http_err}")
            app.logger.error(f"Together.ai Response content: {http_err.response.text}")
            return jsonify({"error": f"Together.ai API error: {http_err.response.text}"}), http_err.response.status_code
        except requests.exceptions.RequestException as req_err:
            app.logger.error(f"Together.ai Request error occurred: {req_err}")
            return jsonify({"error": "Together.ai network or API connection error."}), 500
        except Exception as e:
            app.logger.critical(f"An unexpected error occurred during Together.ai call: {e}", exc_info=True)
            return jsonify({"error": "An internal server error occurred during Together.ai call."}), 500

    else: # Leonardo.ai
        if selected_model_id == '5c232a9e-9061-4777-980a-ddc8e65647c6':
            return jsonify({"error": "The Leonardo base model is no longer available. Please select another model."}), 400

        if not (1 <= num_images <= 8):
            app.logger.warning(f"Invalid num_images received for Leonardo.ai: {num_images}. Defaulting to 4.")
            num_images = 4

        headers = {
            "authorization": f"Bearer {LEONARDO_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "prompt": final_prompt_for_image_gen, # Use enhanced prompt
            "modelId": selected_model_id if selected_model_id else LEONARDO_DEFAULT_MODEL,
            "num_images": num_images,
            "width": 1024, # Ensure width and height are 1024
            "height": 1024,
            "guidance_scale": 7,
            "negative_prompt": "blurry, low quality, deformed, malformed, text, watermark, ugly, poor lighting",
            "public": False
        }

        try:
            app.logger.info(f"Calling Leonardo.ai API with model: {payload['modelId']}")
            generate_response = requests.post(
                f"{LEONARDO_API_BASE_URL}/generations",
                headers=headers,
                json=payload
            )
            generate_response.raise_for_status()
            generation_data = generate_response.json()

            generation_id = generation_data['sdGenerationJob']['generationId']
            app.logger.info(f"Generation job started with ID: {generation_id}")

            for _ in range(30):
                status_response = requests.get(
                    f"{LEONARDO_API_BASE_URL}/generations/{generation_id}",
                    headers=headers
                )
                status_response.raise_for_status()
                status_data = status_response.json()

                gen_info = status_data.get('generations_by_pk')
                if gen_info and gen_info.get('status') == 'COMPLETE':
                    app.logger.info("Leonardo.ai Generation complete!")
                    for image in gen_info.get('generated_images', []):
                        leonardo_image_urls.append(image['url'])
                    break
                elif gen_info and gen_info.get('status') == 'FAILED':
                    app.logger.error("Leonardo.ai Generation failed!")
                    return jsonify({"error": "Leonardo.ai image generation failed."}), 500

                time.sleep(1)

            if not leonardo_image_urls:
                app.logger.error("Leonardo.ai image generation timed out or no images returned.")
                return jsonify({"error": "Leonardo.ai image generation timed out or no images returned."}), 500

            app.logger.info(f"Received {len(leonardo_image_urls)} images from Leonardo.ai.")
            local_image_paths = save_images_locally(leonardo_image_urls, final_prompt_for_image_gen + f"(Model: {selected_model_id})") # Save enhanced prompt
            if not local_image_paths:
                return jsonify({"error": "No images were successfully saved locally from Leonardo.ai."}), 500
            return jsonify({"images": local_image_paths})

        except requests.exceptions.HTTPError as http_err:
            app.logger.error(f"Leonardo.ai HTTP error occurred: {http_err}")
            app.logger.error(f"Leonardo.ai Response content: {http_err.response.text}")
            return jsonify({"error": f"Leonardo.ai API error: {http_err.response.text}"}), http_err.response.status_code
        except requests.exceptions.RequestException as req_err:
            app.logger.error(f"Leonardo.ai Request error occurred: {req_err}")
            return jsonify({"error": "Leonardo.ai network or API connection error."}), 500
        except Exception as e:
            app.logger.critical(f"An unexpected error occurred during Leonardo.ai call: {e}", exc_info=True)
            return jsonify({"error": "An internal server error occurred during Leonardo.ai call."}), 500


@app.route('/get-saved-designs', methods=['GET'])
def get_saved_designs():
    app.logger.info("Fetching saved designs.")
    saved_designs_data = []
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

            if images_in_folder:
                saved_designs_data.append({
                    "folder_id": folder_name,
                    "prompt": prompt_text,
                    "images": sorted(images_in_folder)
                })
    saved_designs_data.sort(
        key=lambda x: os.path.getmtime(os.path.join(GENERATED_IMAGES_DIR, x['folder_id'])),
        reverse=True
    )    

    app.logger.info(f"Found {len(saved_designs_data)} saved design folders.")
    return jsonify(saved_designs_data)

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')