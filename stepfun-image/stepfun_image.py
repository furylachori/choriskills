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
    STEPFUN_API_KEY - Required. Your StepFun API key.
"""

import argparse
import base64
import json
import os
import re
import sys
import tempfile
import time
import urllib.request
import urllib.error
import uuid
from datetime import datetime


def _load_env_file():
    """Load environment variables from `.env` file in the script's directory."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(script_dir, '.env')
    if not os.path.isfile(env_path):
        return
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip()
            if key and value and key not in os.environ:
                os.environ[key] = value

_load_env_file()


ALLOWED_SCHEMES = {"https"}
ALLOWED_HOSTS = {"api.stepfun.ai"}
ALLOWED_HOST_SUFFIXES = {".aliyuncs.com"}  # Alibaba Cloud OSS (StepFun image hosting)
ALLOWED_SIZES = {"1024x1024", "768x1360", "896x1184", "1360x768", "1184x896"}
MAX_RESPONSE_SIZE = 50 * 1024 * 1024  # 50 MB
SIZE_RE = re.compile(r'^\d+x\d+$')
HTTP_TIMEOUT = 60


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(newurl, code, msg, headers, fp)


API_URL = os.environ.get("STEPFUN_API_BASE", "https://api.stepfun.ai/step_plan/v1")
API_KEY = os.environ.get("STEPFUN_API_KEY", "")


def validate_api_base():
    """Validate STEPFUN_API_BASE environment variable."""
    from urllib.parse import urlparse
    base = os.environ.get("STEPFUN_API_BASE", "")
    if not base:
        return  # Will use default
    parsed = urlparse(base)
    if parsed.scheme != "https":
        print(f"Error: STEPFUN_API_BASE must use https scheme, got '{parsed.scheme}'", file=sys.stderr)
        sys.exit(EXIT_NETWORK_ERROR)
    hostname = parsed.hostname
    if not hostname or (hostname != "api.stepfun.ai" and not hostname.endswith(".aliyuncs.com")):
        print(f"Error: STEPFUN_API_BASE hostname '{hostname}' is not allowed. Must be api.stepfun.ai or *.aliyuncs.com", file=sys.stderr)
        sys.exit(EXIT_NETWORK_ERROR)


validate_api_base()

# Exit codes for agent programmatic handling
EXIT_OK = 0
EXIT_INPUT_ERROR = 2      # Bad arguments, file not found, validation failures
EXIT_AUTH_ERROR = 3       # Missing/invalid API key
EXIT_RATE_LIMIT = 4       # 429 rate limited
EXIT_NETWORK_ERROR = 5    # Connection failures
EXIT_API_ERROR = 6        # API returned error (400, 500, etc.)
EXIT_FILE_ERROR = 7       # Disk full, permission denied, I/O failures


def validate_output_dir():
    """Validate OUTPUT_DIR environment variable for path traversal."""
    output_dir = os.environ.get("OUTPUT_DIR", "")
    if not output_dir:
        return  # Will use default

    # Resolve to real path
    real_path = os.path.realpath(output_dir)

    # Check for path traversal
    if '..' in output_dir.replace('\\', '/').split('/'):
        print(f"Error: OUTPUT_DIR contains '..' which is not allowed.", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)

    # Check it's not a system directory
    forbidden_prefixes = ('/etc', '/sys', '/proc', '/dev', '/boot')
    if real_path.startswith(forbidden_prefixes):
        print(f"Error: OUTPUT_DIR points to a system directory.", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)


def get_output_dir():
    """Get OUTPUT_DIR from environment or use default."""
    output_dir = os.environ.get("OUTPUT_DIR")
    if output_dir:
        validate_output_dir()
        return output_dir
    # Default: use HOME or fail with clear error
    home = os.environ.get("HOME")
    if not home:
        print("Error: Neither OUTPUT_DIR nor HOME environment variable is set.", file=sys.stderr)
        sys.exit(EXIT_FILE_ERROR)
    return os.path.join(home, ".zeroclaw", "workspace", "output")


def get_output_path(operation, prompt=None, extension="png"):
    """Generate a default output path in $OUTPUT_DIR."""
    output_dir = get_output_dir()
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if prompt:
        slug = "".join(c if c.isalnum() else "_" for c in prompt[:30]).strip("_")
        filename = f"{operation}_{slug}_{timestamp}_{os.getpid()}.{extension}"
    else:
        filename = f"{operation}_{timestamp}_{os.getpid()}.{extension}"
    output_path = os.path.join(output_dir, filename)

    # Resolve the full path and verify it is still under the validated output_dir
    real_output_path = os.path.realpath(output_path)
    real_output_dir = os.path.realpath(output_dir)
    if not real_output_path.startswith(real_output_dir + os.sep) and real_output_path != real_output_dir:
        print(f"Error: Computed output path '{output_path}' (resolved to '{real_output_path}') "
              f"escapes the output directory '{real_output_dir}'.", file=sys.stderr)
        sys.exit(EXIT_FILE_ERROR)

    return output_path


def sanitize_voice(voice):
    """Sanitize voice name to prevent path traversal in filenames."""
    voice = os.path.basename(voice)
    voice = re.sub(r'[^a-zA-Z0-9_-]', '', voice)
    return voice


def validate_size(size_str):
    """Validate --size format and allowed values."""
    if not SIZE_RE.match(size_str):
        print(f"Error: --size must be in WxH format (e.g. 1024x1024), got '{size_str}'", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)
    if size_str not in ALLOWED_SIZES:
        print(f"Error: --size must be one of {sorted(ALLOWED_SIZES)}, got '{size_str}'", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)


def validate_steps(steps):
    """Validate --steps range."""
    if steps < 1 or steps > 50:
        print(f"Error: --steps must be 1-50, got {steps}", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)


def validate_cfg_scale(cfg_scale):
    """Validate --cfg-scale range."""
    if cfg_scale < 0.1 or cfg_scale > 10.0:
        print(f"Error: --cfg-scale must be 0.1-10.0, got {cfg_scale}", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)


def validate_url_safe(url):
    """Validate that a URL is safe to fetch (SSRF protection)."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        print(f"Error: URL scheme '{parsed.scheme}' is not allowed. Only https:// is permitted.", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)
    hostname = parsed.hostname
    if not hostname:
        print(f"Error: URL has no hostname.", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)
    if hostname not in ALLOWED_HOSTS and not any(hostname.endswith(suffix) for suffix in ALLOWED_HOST_SUFFIXES):
        print(f"Error: URL hostname '{hostname}' is not allowed.", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)


def validate_input_path(input_path):
    """Validate that input path has no path traversal components."""
    # Check both Unix and Windows separators
    normalized = input_path.replace('\\', '/')
    parts = normalized.split('/')
    if '..' in parts:
        print(f"Error: Input path contains '..' which is not allowed.", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)


def _urlopen_with_retry(req, timeout, max_retries=2, opener=None):
    """Open URL with retry logic for transient failures."""
    for attempt in range(max_retries + 1):
        try:
            return opener.open(req, timeout=timeout) if opener else urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < max_retries:
                delay = 2 ** attempt
                ra = e.headers.get('Retry-After', str(delay))
                try:
                    delay = float(ra)
                except ValueError:
                    pass
                print(f"Retrying after {delay:.1f}s (attempt {attempt+1}/{max_retries}, HTTP {e.code})", file=sys.stderr)
                time.sleep(delay)
            else:
                raise
        except urllib.error.URLError as e:
            if attempt < max_retries:
                print(f"Retrying after {2**attempt:.1f}s (attempt {attempt+1}/{max_retries}, network error)", file=sys.stderr)
                time.sleep(2 ** attempt)
            else:
                raise
    raise RuntimeError("Unreachable")


def check_disk_space(path, required_bytes=100 * 1024 * 1024):
    """Check if there's enough disk space. Returns True if ok."""
    try:
        stat = os.statvfs(os.path.dirname(os.path.abspath(path)))
        available = stat.f_bavail * stat.f_frsize
        return available >= required_bytes
    except OSError:
        return True  # Can't check, proceed anyway


def download_url(url, output_path):
    """Download a URL safely with SSRF protection, size limit, and atomic write."""
    validate_url_safe(url)

    try:
        opener = urllib.request.build_opener(_NoRedirectHandler)
        req = urllib.request.Request(url, headers={"User-Agent": "claw-skills/1.0"})
        # Block automatic redirects - validate manually
        try:
            response = _urlopen_with_retry(req, timeout=HTTP_TIMEOUT, opener=opener)
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308):
                redirect_url = e.headers.get('Location')
                if redirect_url:
                    validate_url_safe(redirect_url)  # Re-validate redirect target
                    req2 = urllib.request.Request(redirect_url, headers={"User-Agent": "claw-skills/1.0"})
                    response = _urlopen_with_retry(req2, timeout=HTTP_TIMEOUT, opener=opener)
                else:
                    raise
            else:
                raise

        content_length = response.headers.get('Content-Length')
        if content_length:
            try:
                content_length_int = int(content_length)
            except ValueError:
                print(f"Error: Non-numeric Content-Length header: '{content_length}'", file=sys.stderr)
                sys.exit(1)
            if content_length_int > MAX_RESPONSE_SIZE:
                print(f"Error: Response too large ({content_length_int} bytes > {MAX_RESPONSE_SIZE})", file=sys.stderr)
                sys.exit(1)

        tmp_path = output_path + ".tmp"
        total = 0
        try:
            with os.fdopen(os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as f:
                while True:
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_RESPONSE_SIZE:
                        print(f"Error: Response too large (>{MAX_RESPONSE_SIZE} bytes)", file=sys.stderr)
                        raise OSError("response too large")
                    f.write(chunk)
            os.replace(tmp_path, output_path)
        except FileExistsError:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            print(f"Error: Temporary file '{tmp_path}' already exists (possible symlink attack).", file=sys.stderr)
            sys.exit(EXIT_FILE_ERROR)
        except OSError as e:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            print(f"Error writing/moving output to '{output_path}': {e}", file=sys.stderr)
            sys.exit(EXIT_FILE_ERROR)
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        if len(error_body) > 200:
            error_msg = error_body[:200] + "... (truncated)"
        else:
            error_msg = error_body
        print(f"Error downloading from URL: HTTP {e.code}: {error_msg}", file=sys.stderr)
        sys.exit(EXIT_API_ERROR)
    except urllib.error.URLError as e:
        print(f"Error downloading from URL: {e.reason}", file=sys.stderr)
        sys.exit(EXIT_NETWORK_ERROR)


def escape_crlf(s):
    """Prevent CRLF injection in multipart form data."""
    if isinstance(s, str):
        return s.replace('\r', '%0D').replace('\n', '%0A')
    return s


def check_prompt_injection(text):
    """Detect common prompt injection patterns."""
    injection_patterns = [
        r'ignore\s+(all\s+)?previous\s+instructions?',
        r'you\s+are\s+now',
        r'system\s+prompt',
        r'new\s+instructions?',
        r'disregard\s+previous',
        r'override\s+',
    ]
    text_lower = text.lower()
    for pattern in injection_patterns:
        if re.search(pattern, text_lower):
            print(f"Warning: Potential prompt injection detected in image prompt.", file=sys.stderr)
            return True
    return False


def call_api(endpoint, data=None, files=None):
    """Make an API call to StepFun."""
    if not API_KEY:
        print("Error: STEPFUN_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(EXIT_AUTH_ERROR)

    url = f"{API_URL}/{endpoint}"
    headers = {"Authorization": f"Bearer {API_KEY}"}

    if files:
        import mimetypes
        boundary = f"----FormBoundary{uuid.uuid4().hex[:16]}"
        
        body = b""
        for key, value in data.items():
            body += f"--{boundary}\r\n".encode()
            body += f'Content-Disposition: form-data; name="{escape_crlf(key)}"\r\n\r\n'.encode()
            body += f"{escape_crlf(str(value))}\r\n".encode()
        
        for file_key, file_path in files.items():
            filename = os.path.basename(file_path)
            mime_type = mimetypes.guess_type(filename)[0] or "image/png"
            fd = os.open(file_path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, 'rb') as f:
                file_data = f.read()
            body += f"--{boundary}\r\n".encode()
            body += f'Content-Disposition: form-data; name="{escape_crlf(file_key)}"; filename="{escape_crlf(filename)}"\r\n'.encode()
            body += f"Content-Type: {mime_type}\r\n\r\n".encode()
            body += file_data + b"\r\n"
        
        body += f"--{boundary}--\r\n".encode()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    else:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    
    try:
        with _urlopen_with_retry(req, timeout=HTTP_TIMEOUT) as response:
            try:
                return json.loads(response.read().decode())
            except json.JSONDecodeError:
                print(f"Error: Invalid JSON response from API", file=sys.stderr)
                sys.exit(EXIT_API_ERROR)
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        if len(error_body) > 200:
            error_msg = error_body[:200] + "... (truncated)"
        else:
            error_msg = error_body
        print(f"API Error ({e.code}): {error_msg}", file=sys.stderr)
        sys.exit(EXIT_API_ERROR)
    except urllib.error.URLError as e:
        print(f"API Error: {e.reason}", file=sys.stderr)
        sys.exit(EXIT_NETWORK_ERROR)


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

    b64_string = image_data["b64_json"]
    # Estimate decoded size (base64 expands by ~4/3)
    estimated_size = len(b64_string) * 3 // 4
    if estimated_size > MAX_RESPONSE_SIZE:
        print(f"Error: Image data too large (estimated {estimated_size} bytes > {MAX_RESPONSE_SIZE})", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)
    try:
        image_bytes = base64.b64decode(b64_string)
    except Exception as e:
        print(f"Error decoding base64 image data: {e}", file=sys.stderr)
        sys.exit(1)
    
    if len(image_bytes) > MAX_RESPONSE_SIZE:
        print(f"Error: Image data too large ({len(image_bytes)} bytes > {MAX_RESPONSE_SIZE})", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)
    
    if not check_disk_space(args.output, len(image_bytes) + 10 * 1024 * 1024):
        print("Error: Insufficient disk space for output file.", file=sys.stderr)
        sys.exit(EXIT_FILE_ERROR)
    
    tmp_path = args.output + ".tmp"
    try:
        with os.fdopen(os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as f:
            f.write(image_bytes)
        os.replace(tmp_path, args.output)
    except FileExistsError:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        print(f"Error: Temporary file '{tmp_path}' already exists (possible symlink attack).", file=sys.stderr)
        sys.exit(EXIT_FILE_ERROR)
    except OSError as e:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        print(f"Error writing image to temporary file '{tmp_path}': {e}", file=sys.stderr)
        sys.exit(EXIT_FILE_ERROR)
    
    print(f"Image generated: {args.output}")
    if args.verbose and "seed" in image_data:
        print(f"Seed: {image_data['seed']}", file=sys.stderr)


def edit_image(args):
    """Edit an existing image using a text prompt."""
    validate_input_path(args.input)
    
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' does not exist.", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)

    if args.size:
        print(f"Warning: --size is ignored for edit operations; output dimensions are determined by the API.", file=sys.stderr)

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

    # Sanitize prompt (remove control chars)
    args.prompt = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', args.prompt)

    if check_prompt_injection(args.prompt):
        print(f"Warning: Proceeding with potentially adversarial prompt.", file=sys.stderr)

    # Validate prompt length
    if len(args.prompt) < 1 or len(args.prompt) > 512:
        print(f"Error: Prompt must be 1-512 characters (got {len(args.prompt)})", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)

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
