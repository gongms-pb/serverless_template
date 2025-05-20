import os
import sys
import runpod
from ComfyUI.workflow import main

from runpod.serverless.utils import rp_upload
import json
import urllib.request
import urllib.parse
import time
import requests
import base64
from io import BytesIO

# Time to wait between API check attempts in milliseconds
COMFY_API_AVAILABLE_INTERVAL_MS = 50
# Maximum number of API check attempts
COMFY_API_AVAILABLE_MAX_RETRIES = 500
# Time to wait between poll attempts in milliseconds
COMFY_POLLING_INTERVAL_MS = int(os.environ.get("COMFY_POLLING_INTERVAL_MS", 250))
# Maximum number of poll attempts
COMFY_POLLING_MAX_RETRIES = int(os.environ.get("COMFY_POLLING_MAX_RETRIES", 500))
# Host where ComfyUI is running
COMFY_HOST = "127.0.0.1:8188"
# Enforce a clean state after each job is done
# see https://docs.runpod.io/docs/handler-additional-controls#refresh-worker
REFRESH_WORKER = os.environ.get("REFRESH_WORKER", "false").lower() == "true"


def validate_input(job_input):
    """
    Validates the input for the handler function.

    Expected format:
    {
      "base_image" : "image url",
      "reference_image" : "image url",
      "mask_image" : "image url",
      "use_background_remove" : boolean
    }

    Args:
        job_input (dict): The input data to validate.

    Returns:
        tuple: A tuple containing the validated data and an error message, if any.
               The structure is (validated_data, error_message).
    """
    if job_input is None:
        return None, "Please provide input"

    # If input is a string, try to parse it as JSON
    if isinstance(job_input, str):
        try:
            job_input = json.loads(job_input)
        except json.JSONDecodeError:
            return None, "Invalid JSON format in input"

    required_keys = ["base_image", "reference_image", "mask_image", "use_background_remove"]
    for key in required_keys:
        if key not in job_input:
            return None, f"Missing '{key}' in input"

    # Validate that the image URLs are non-empty strings
    for key in ["base_image", "reference_image", "mask_image"]:
        if not isinstance(job_input[key], str) or not job_input[key].strip():
            return None, f"'{key}' must be a non-empty string representing an image URL"

    # Validate that use_background_remove is a boolean
    if not isinstance(job_input["use_background_remove"], bool):
        return None, "'use_background_remove' must be a boolean"

    validated_data = {
        "base_image": job_input["base_image"],
        "reference_image": job_input["reference_image"],
        "mask_image": job_input["mask_image"],
        "use_background_remove": job_input["use_background_remove"],
    }
    return validated_data, None


def check_server(url, retries=500, delay=50):
    """
    Check if a server is reachable via HTTP GET request

    Args:
    - url (str): The URL to check
    - retries (int, optional): The number of times to attempt connecting to the server. Default is 50
    - delay (int, optional): The time in milliseconds to wait between retries. Default is 500

    Returns:
    bool: True if the server is reachable within the given number of retries, otherwise False
    """

    for i in range(retries):
        try:
            response = requests.get(url)

            # If the response status code is 200, the server is up and running
            if response.status_code == 200:
                print(f"runpod-worker-comfy - API is reachable")
                return True
        except requests.RequestException as e:
            # If an exception occurs, the server may not be ready
            pass

        # Wait for the specified delay before retrying
        time.sleep(delay / 1000)

    print(
        f"runpod-worker-comfy - Failed to connect to server at {url} after {retries} attempts."
    )
    return False

def get_history(prompt_id):
    """
    Retrieve the history of a given prompt using its ID

    Args:
        prompt_id (str): The ID of the prompt whose history is to be retrieved

    Returns:
        dict: The history of the prompt, containing all the processing steps and results
    """
    with urllib.request.urlopen(f"http://{COMFY_HOST}/history/{prompt_id}") as response:
        return json.loads(response.read())


def base64_encode(img_path):
    """
    Returns base64 encoded image.

    Args:
        img_path (str): The path to the image

    Returns:
        str: The base64 encoded image
    """
    with open(img_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
        return f"{encoded_string}"


def process_output_images(outputs, job_id):
    """
    This function takes the "outputs" from image generation and the job ID,
    then determines the correct way to return the image, either as a direct URL
    to an AWS S3 bucket or as a base64 encoded string, depending on the
    environment configuration.

    Args:
        outputs (dict): A dictionary containing the outputs from image generation,
                        typically includes node IDs and their respective output data.
        job_id (str): The unique identifier for the job.

    Returns:
        dict: A dictionary with the status ('success' or 'error') and the message,
              which is either the URL to the image in the AWS S3 bucket or a base64
              encoded string of the image. In case of error, the message details the issue.

    The function works as follows:
    - It first determines the output path for the images from an environment variable,
      defaulting to "/comfyui/output" if not set.
    - It then iterates through the outputs to find the filenames of the generated images.
    - After confirming the existence of the image in the output folder, it checks if the
      AWS S3 bucket is configured via the BUCKET_ENDPOINT_URL environment variable.
    - If AWS S3 is configured, it uploads the image to the bucket and returns the URL.
    - If AWS S3 is not configured, it encodes the image in base64 and returns the string.
    - If the image file does not exist in the output folder, it returns an error status
      with a message indicating the missing image file.
    """

    # The path where ComfyUI stores the generated images
    COMFY_OUTPUT_PATH = os.environ.get("COMFY_OUTPUT_PATH", "./ComfyUI/output")

    output_images = {}

    for node_id, node_output in outputs.items():
        if "images" in node_output:
            for image in node_output["images"]:
                output_images = os.path.join(image["subfolder"], image["filename"])

    print(f"runpod-worker-comfy - image generation is done")

    # expected image output folder
    local_image_path = f"{COMFY_OUTPUT_PATH}/{output_images}"

    print(f"runpod-worker-comfy - {local_image_path}")

    # The image is in the output folder
    if os.path.exists(local_image_path):
        if os.environ.get("BUCKET_ENDPOINT_URL", False):
            # URL to image in AWS S3
            image = rp_upload.upload_image(job_id, local_image_path)
            print(
                "runpod-worker-comfy - the image was generated and uploaded to AWS S3"
            )
        else:
            # base64 image
            image = base64_encode(local_image_path)
            print(
                "runpod-worker-comfy - the image was generated and converted to base64"
            )

        return {
            "status": "success",
            "message": image,
        }
    else:
        print("runpod-worker-comfy - the image does not exist in the output folder")
        return {
            "status": "error",
            "message": f"the image does not exist in the specified output folder: {local_image_path}",
        }


def process_input_images(job_input):
    """
    Save images from URLs provided in job_input to the specified input path,
    and update the input by replacing the image URL with the local file path.

    Args:
        job_input (dict): A dictionary containing 'base_image', 'reference_image',
                          and 'mask_image' as image URLs, and optionally other keys,
                          e.g. 'use_background_remove'.

    Returns:
        tuple: A tuple of (upload_result, updated_input) where:
            - upload_result (dict): Contains the status and details of the save operation.
            - updated_input (dict): The original input, but with the image keys updated to the local file paths.
    """
    if not job_input:
        return (
            {"status": "success", "message": "No images to save", "details": []},
            job_input,
        )

    COMFY_INPUT_PATH = os.environ.get("COMFY_INPUT_PATH", "./ComfyUI/input")
    saved_files = []
    errors = []

    # Copy the input to update it later
    updated_input = job_input.copy()

    # Ensure the input directory exists
    os.makedirs(COMFY_INPUT_PATH, exist_ok=True)

    for key in ["base_image", "reference_image", "mask_image"]:
        try:
            image_url = job_input[key]
            # Get a filename from the URL, or use a default like "<key>.png"
            parsed = urllib.parse.urlparse(image_url)
            filename = os.path.basename(parsed.path) or f"{key}.png"
            file_path = os.path.join(COMFY_INPUT_PATH, filename)

            response = requests.get(image_url)
            response.raise_for_status()

            with open(file_path, "wb") as img_file:
                img_file.write(response.content)

            saved_files.append({"key": key, "name": filename, "path": file_path})
            # Replace the image URL with the local file path
            updated_input[key] = filename
            print(f"Saved {file_path} for key {key}")
        except Exception as e:
            errors.append({"key": key, "error": str(e)})
            print(f"Error saving image for key {key}: {e}")

    if errors:
        upload_result = {
            "status": "error",
            "message": "Some images failed to save",
            "details": {"saved": saved_files, "errors": errors},
        }
    else:
        upload_result = {
            "status": "success",
            "message": "All images saved successfully",
            "details": saved_files,
        }
    return upload_result, updated_input


def handler(job):
    """
    The main function that handles a job of generating an image.
    """
    job_input = job["input"]

    # Validate input
    validated_data, error_message = validate_input(job_input)
    if error_message:
        return {"error": error_message}

    # Process input images: download images and update input with their local file paths.
    upload_result, updated_input = process_input_images(validated_data)

    if upload_result["status"] == "error":
        return upload_result

    # Pass updated_input to main for workflow processing.
    output = main(updated_input)
    images_result = process_output_images(output, None)

    result = {**images_result, "refresh_worker": REFRESH_WORKER}
    return result


# Start the handler only if this script is run directly
if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})