#!/usr/bin/env python3
"""
StepFun Image API Client

Generate or edit images using the StepFun API.

Usage:
    # Generate an image
    python stepfun_image.py generate --prompt "A serene alpine lake" --output lake.png
    
    # Edit an image
    python stepfun_image.py edit --prompt "Make it look older" --input photo.png --output edited.png
    
    # Generate with custom parameters
    python stepfun_image.py generate --prompt "A cat wearing a hat" --size 768x1360 --steps 12 --seed 42 --output cat.png

Environment:
    STEP_FUN_API_KEY - Required. Your StepFun API key.
"""

import argparse
import base64
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime


API_URL = "https://api.stepfun.ai/step_plan/v1"
API_KEY = os.environ.get("STEP_FUN_API_KEY", "")


def get_output_dir():
    """Get OUTPUT_DIR from environment or use default."""
    return os.environ.get("OUTPUT_DIR", os.path.expanduser("~/.zeroclaw/workspace/output"))


def get_output_path(operation, prompt=None, extension="png"):
    """Generate a default output path in $OUTPUT_DIR."""
    output_dir = get_output_dir()
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if prompt:
        # Create a short slug from prompt (first 30 chars, alphanumeric only)
        slug = "".join(c if c.isalnum() else "_" for c in prompt[:30]).strip("_")
        filename = f"{operation}_{slug}_{timestamp}.{extension}"
    else:
        filename = f"{operation}_{timestamp}.{extension}"
    return os.path.join(output_dir, filename)


API_URL = "https://api.stepfun.ai/step_plan/v1"
API_KEY = os.environ.get("STEP_FUN_API_KEY", "")


def call_api(endpoint, data=None, files=None):
    """Make an API call to StepFun."""
    if not API_KEY:
        print("Error: STEP_FUN_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    url = f"{API_URL}/{endpoint}"
    headers = {"Authorization": f"Bearer {API_KEY}"}

    if files:
        # Multipart form data for image upload
        import mimetypes
        boundary = "----FormBoundary7MA4YWxkTrZu0gW"
        
        body = b""
        for key, value in data.items():
            body += f"--{boundary}\r\n".encode()
            body += f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode()
            body += f"{value}\r\n".encode()
        
        for file_key, file_path in files.items():
            filename = os.path.basename(file_path)
            mime_type = mimetypes.guess_type(filename)[0] or "image/png"
            with open(file_path, "rb") as f:
                file_data = f.read()
            body += f"--{boundary}\r\n".encode()
            body += f'Content-Disposition: form-data; name="{file_key}"; filename="{filename}"\r\n'.encode()
            body += f"Content-Type: {mime_type}\r\n\r\n".encode()
            body += file_data + b"\r\n"
        
        body += f"--{boundary}--\r\n".encode()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    else:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        try:
            error_data = json.loads(error_body)
            error_msg = error_data.get("error", error_body)
        except json.JSONDecodeError:
            error_msg = error_body
        print(f"API Error ({e.code}): {error_msg}", file=sys.stderr)
        sys.exit(1)


def generate_image(args):
    """Generate a new image from a text prompt."""
    args.output = get_output_path("generate", args.prompt)
    
    data = {
        "model": args.model,
        "prompt": args.prompt,
        "response_format": "b64_json",
        "cfg_scale": args.cfg_scale,
        "steps": args.steps,
        "text_mode": args.text_mode,
    }
    
    if args.size:
        data["size"] = args.size
    if args.seed is not None:
        data["seed"] = args.seed
    if args.negative_prompt:
        data["negative_prompt"] = args.negative_prompt

    response = call_api("images/generations", data=data)
    
    if "error" in response:
        print(f"Error: {response['error']}", file=sys.stderr)
        sys.exit(1)

    if "data" not in response or not response["data"]:
        print("Error: No image data in response", file=sys.stderr)
        sys.exit(1)

    image_data = response["data"][0]
    
    if "b64_json" not in image_data:
        print("Error: Expected b64_json in response", file=sys.stderr)
        sys.exit(1)

    image_bytes = base64.b64decode(image_data["b64_json"])
    with open(args.output, "wb") as f:
        f.write(image_bytes)
    
    print(f"Image generated: {args.output}")
    if args.verbose and "seed" in image_data:
        print(f"Seed: {image_data['seed']}", file=sys.stderr)


def edit_image(args):
    """Edit an existing image using a text prompt."""
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' does not exist.", file=sys.stderr)
        sys.exit(1)

    args.output = get_output_path("edit", args.prompt)
    
    data = {
        "model": args.model,
        "prompt": args.prompt,
        "size": args.size,
        "steps": args.steps,
        "cfg_scale": args.cfg_scale,
        "text_mode": args.text_mode,
    }
    
    if args.seed is not None:
        data["seed"] = args.seed
    if args.negative_prompt:
        data["negative_prompt"] = args.negative_prompt

    response = call_api("images/edits", data=data, files={"image": args.input})
    
    if "error" in response:
        print(f"Error: {response['error']}", file=sys.stderr)
        sys.exit(1)

    if "data" not in response or not response["data"]:
        print("Error: No image data in response", file=sys.stderr)
        sys.exit(1)

    image_info = response["data"][0]
    
    if "url" not in image_info:
        print("Error: Expected URL in response (edit endpoint returns URLs, not base64)", file=sys.stderr)
        sys.exit(1)

    # Download the edited image from the returned URL
    try:
        urllib.request.urlretrieve(image_info["url"], args.output)
        print(f"Image edited: {args.output}")
        if args.verbose and "seed" in image_info:
            print(f"Seed: {image_info['seed']}", file=sys.stderr)
    except Exception as e:
        print(f"Error downloading edited image: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="StepFun Image API Client")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Generate subcommand
    gen_parser = subparsers.add_parser("generate", help="Generate a new image")
    gen_parser.add_argument("--prompt", required=True, help="Text prompt (1-512 characters)")
    gen_parser.add_argument("--model", default="step-image-edit-2", help="Model name")
    gen_parser.add_argument("--size", default="1024x1024", help="Output size")
    gen_parser.add_argument("--steps", type=int, default=8, help="Number of inference steps")
    gen_parser.add_argument("--cfg-scale", type=float, default=1.0, help="CFG scale")
    gen_parser.add_argument("--seed", type=int, default=None, help="Random seed")
    gen_parser.add_argument("--text-mode", action="store_true", help="Enable text rendering")
    gen_parser.add_argument("--negative-prompt", default="", help="Negative prompt")
    gen_parser.add_argument("--verbose", action="store_true", help="Print metadata to stderr")

    # Edit subcommand
    edit_parser = subparsers.add_parser("edit", help="Edit an existing image")
    edit_parser.add_argument("--prompt", required=True, help="Edit description (1-512 characters)")
    edit_parser.add_argument("--input", required=True, help="Input image file")
    edit_parser.add_argument("--model", default="step-image-edit-2", help="Model name")
    edit_parser.add_argument("--size", default="1024x1024", help="Output size")
    edit_parser.add_argument("--steps", type=int, default=8, help="Number of inference steps")
    edit_parser.add_argument("--cfg-scale", type=float, default=1.0, help="CFG scale")
    edit_parser.add_argument("--seed", type=int, default=None, help="Random seed")
    edit_parser.add_argument("--text-mode", action="store_true", help="Enable text rendering")
    edit_parser.add_argument("--negative-prompt", default="", help="Negative prompt")
    edit_parser.add_argument("--verbose", action="store_true", help="Print metadata to stderr")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Validate prompt length
    if len(args.prompt) < 1 or len(args.prompt) > 512:
        print(f"Error: Prompt must be 1-512 characters (got {len(args.prompt)})", file=sys.stderr)
        sys.exit(1)

    if args.command == "generate":
        generate_image(args)
    elif args.command == "edit":
        edit_image(args)


if __name__ == "__main__":
    main()
