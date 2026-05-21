#!/usr/bin/env python3
"""
StepFun Image API Client

Generate or edit images using the StepFun API.

Usage:
    # Generate an image
    python stepfun_image.py generate --prompt "A serene alpine lake"
    
    # Edit an image
    python stepfun_image.py edit --prompt "Make it look older" --input photo.png
    
    # Generate with custom parameters
    python stepfun_image.py generate --prompt "A cat wearing a hat" --size 768x1360 --steps 12 --seed 42

Environment:
    STEP_FUN_API_KEY - Required. Your StepFun API key.
"""

import argparse
import base64
import json
import os
import re
import sys
import tempfile
import urllib.request
import urllib.error
from datetime import datetime


ALLOWED_SCHEMES = {"https"}
ALLOWED_HOSTS = {"api.stepfun.ai"}
ALLOWED_HOST_SUFFIXES = {".aliyuncs.com"}  # Alibaba Cloud OSS (StepFun image hosting)
ALLOWED_SIZES = {"1024x1024", "768x1360", "896x1184", "1360x768", "1184x896"}
MAX_RESPONSE_SIZE = 50 * 1024 * 1024  # 50 MB
SIZE_RE = re.compile(r'^\d+x\d+$')
HTTP_TIMEOUT = 60

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
        slug = "".join(c if c.isalnum() else "_" for c in prompt[:30]).strip("_")
        filename = f"{operation}_{slug}_{timestamp}.{extension}"
    else:
        filename = f"{operation}_{timestamp}.{extension}"
    return os.path.join(output_dir, filename)


def sanitize_voice(voice):
    """Sanitize voice name to prevent path traversal in filenames."""
    voice = os.path.basename(voice)
    voice = re.sub(r'[^a-zA-Z0-9_-]', '', voice)
    return voice


def validate_size(size_str):
    """Validate --size format and allowed values."""
    if not SIZE_RE.match(size_str):
        print(f"Error: --size must be in WxH format (e.g. 1024x1024), got '{size_str}'", file=sys.stderr)
        sys.exit(1)
    if size_str not in ALLOWED_SIZES:
        print(f"Error: --size must be one of {sorted(ALLOWED_SIZES)}, got '{size_str}'", file=sys.stderr)
        sys.exit(1)


def validate_steps(steps):
    """Validate --steps range."""
    if steps < 1 or steps > 50:
        print(f"Error: --steps must be 1-50, got {steps}", file=sys.stderr)
        sys.exit(1)


def validate_cfg_scale(cfg_scale):
    """Validate --cfg-scale range."""
    if cfg_scale < 0.1 or cfg_scale > 10.0:
        print(f"Error: --cfg-scale must be 0.1-10.0, got {cfg_scale}", file=sys.stderr)
        sys.exit(1)


def validate_url_safe(url):
    """Validate that a URL is safe to fetch (SSRF protection)."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        print(f"Error: URL scheme '{parsed.scheme}' is not allowed. Only https:// is permitted.", file=sys.stderr)
        sys.exit(1)
    hostname = parsed.hostname
    if not hostname:
        print(f"Error: URL has no hostname.", file=sys.stderr)
        sys.exit(1)
    if hostname not in ALLOWED_HOSTS and not any(hostname.endswith(suffix) for suffix in ALLOWED_HOST_SUFFIXES):
        print(f"Error: URL hostname '{hostname}' is not allowed.", file=sys.stderr)
        sys.exit(1)


def validate_input_path(input_path):
    """Validate that input path has no path traversal components."""
    # Check both Unix and Windows separators
    normalized = input_path.replace('\\', '/')
    parts = normalized.split('/')
    if '..' in parts:
        print(f"Error: Input path contains '..' which is not allowed.", file=sys.stderr)
        sys.exit(1)


def download_url(url, output_path):
    """Download a URL safely with SSRF protection, size limit, and atomic write."""
    validate_url_safe(url)
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "claw-skills/1.0"})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as response:
            content_length = response.headers.get('Content-Length')
            if content_length and int(content_length) > MAX_RESPONSE_SIZE:
                print(f"Error: Response too large ({content_length} bytes > {MAX_RESPONSE_SIZE})", file=sys.stderr)
                sys.exit(1)
            
            tmp_path = output_path + ".tmp"
            total = 0
            with open(tmp_path, "wb") as f:
                while True:
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_RESPONSE_SIZE:
                        os.unlink(tmp_path)
                        print(f"Error: Response too large (>{MAX_RESPONSE_SIZE} bytes)", file=sys.stderr)
                        sys.exit(1)
                    f.write(chunk)
            
            os.replace(tmp_path, output_path)
    except urllib.error.HTTPError as e:
        print(f"Error downloading from URL: HTTP {e.code}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Error downloading from URL: {e.reason}", file=sys.stderr)
        sys.exit(1)


def call_api(endpoint, data=None, files=None):
    """Make an API call to StepFun."""
    if not API_KEY:
        print("Error: STEP_FUN_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    url = f"{API_URL}/{endpoint}"
    headers = {"Authorization": f"Bearer {API_KEY}"}

    if files:
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
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as response:
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
    except urllib.error.URLError as e:
        print(f"API Error: {e.reason}", file=sys.stderr)
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
        validate_size(args.size)
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
    
    if len(image_bytes) > MAX_RESPONSE_SIZE:
        print(f"Error: Image data too large ({len(image_bytes)} bytes > {MAX_RESPONSE_SIZE})", file=sys.stderr)
        sys.exit(1)
    
    tmp_path = args.output + ".tmp"
    with open(tmp_path, "wb") as f:
        f.write(image_bytes)
    os.replace(tmp_path, args.output)
    
    print(f"Image generated: {args.output}")
    if args.verbose and "seed" in image_data:
        print(f"Seed: {image_data['seed']}", file=sys.stderr)


def edit_image(args):
    """Edit an existing image using a text prompt."""
    validate_input_path(args.input)
    
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
    
    if args.size:
        validate_size(args.size)
    if args.seed is not None:
        data["seed"] = args.seed
    if args.negative_prompt:
        data["negative_prompt"] = args.negative_prompt

    validate_steps(args.steps)
    validate_cfg_scale(args.cfg_scale)

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

    download_url(image_info["url"], args.output)
    
    print(f"Image edited: {args.output}")
    if args.verbose and "seed" in image_info:
        print(f"Seed: {image_info['seed']}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="StepFun Image API Client")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Generate subcommand
    gen_parser = subparsers.add_parser("generate", help="Generate a new image")
    gen_parser.add_argument("--prompt", required=True, help="Text prompt (1-512 characters)")
    gen_parser.add_argument("--model", default="step-image-edit-2", help="Model name")
    gen_parser.add_argument("--size", default="1024x1024", help="Output size (1024x1024, 768x1360, 896x1184, 1360x768, 1184x896)")
    gen_parser.add_argument("--steps", type=int, default=8, help="Number of inference steps (1-50)")
    gen_parser.add_argument("--cfg-scale", type=float, default=1.0, help="CFG scale (0.1-10.0)")
    gen_parser.add_argument("--seed", type=int, default=None, help="Random seed")
    gen_parser.add_argument("--text-mode", action="store_true", help="Enable text rendering")
    gen_parser.add_argument("--negative-prompt", default="", help="Negative prompt")
    gen_parser.add_argument("--verbose", action="store_true", help="Print metadata to stderr")

    # Edit subcommand
    edit_parser = subparsers.add_parser("edit", help="Edit an existing image")
    edit_parser.add_argument("--prompt", required=True, help="Edit description (1-512 characters)")
    edit_parser.add_argument("--input", required=True, help="Input image file")
    edit_parser.add_argument("--model", default="step-image-edit-2", help="Model name")
    edit_parser.add_argument("--size", default="1024x1024", help="Output size (note: ignored by API)")
    edit_parser.add_argument("--steps", type=int, default=8, help="Number of inference steps (1-50)")
    edit_parser.add_argument("--cfg-scale", type=float, default=1.0, help="CFG scale (0.1-10.0)")
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
        validate_steps(args.steps)
        validate_cfg_scale(args.cfg_scale)
        generate_image(args)
    elif args.command == "edit":
        validate_steps(args.steps)
        validate_cfg_scale(args.cfg_scale)
        edit_image(args)


if __name__ == "__main__":
    main()
