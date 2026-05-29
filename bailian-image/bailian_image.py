#!/usr/bin/env python3
"""
Bailian Image API Client

Generate images using the Bailian (Alibaba Cloud) Image API.

Usage:
    python bailian_image.py generate --prompt "A serene mountain landscape at sunset, photorealistic"

Environment:
    BAILIAN_TOKEN_PLAN_API_KEY - Required. Your Bailian API key.
    BAILIAN_TOKEN_PLAN_API_BASE - Optional. API base URL (default: https://token-plan.ap-southeast-1.maas.aliyuncs.com)
"""

import argparse
import ipaddress
import json
import os
import re
import socket
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime

ALLOWED_SCHEMES = {"https"}
ALLOWED_HOSTS = {"token-plan.ap-southeast-1.maas.aliyuncs.com"}
ALLOWED_HOST_SUFFIXES = {".aliyuncs.com"}
MAX_RESPONSE_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_RETRY_AFTER = 60
HTTP_TIMEOUT = 120

API_BASE = os.environ.get("BAILIAN_TOKEN_PLAN_API_BASE", "https://token-plan.ap-southeast-1.maas.aliyuncs.com")
_ALLOWED_ENV_KEYS = {"BAILIAN_TOKEN_PLAN_API_KEY", "BAILIAN_TOKEN_PLAN_API_BASE", "OUTPUT_DIR"}

# Exit codes for agent programmatic handling
EXIT_OK = 0
EXIT_INPUT_ERROR = 2      # Bad arguments, file not found, validation failures
EXIT_AUTH_ERROR = 3       # Missing/invalid API key
EXIT_RATE_LIMIT = 4       # 429 rate limited
EXIT_NETWORK_ERROR = 5    # Connection failures
EXIT_API_ERROR = 6        # API returned error (400, 500, etc.)
EXIT_FILE_ERROR = 7       # Disk full, permission denied, I/O failures


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(newurl, code, msg, headers, fp)


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
            if key and value and key not in os.environ and key in _ALLOWED_ENV_KEYS:
                os.environ[key] = value

_load_env_file()


def validate_api_base():
    """Validate BAILIAN_TOKEN_PLAN_API_BASE environment variable."""
    from urllib.parse import urlparse
    base = API_BASE
    if not base:
        return  # Will use default
    parsed = urlparse(base)
    if parsed.scheme != "https":
        print(f"Error: BAILIAN_TOKEN_PLAN_API_BASE must use https scheme, got '{parsed.scheme}'", file=sys.stderr)
        sys.exit(EXIT_NETWORK_ERROR)
    hostname = parsed.hostname
    if not hostname:
        print(f"Error: BAILIAN_TOKEN_PLAN_API_BASE has no hostname.", file=sys.stderr)
        sys.exit(EXIT_NETWORK_ERROR)
    if hostname != "token-plan.ap-southeast-1.maas.aliyuncs.com" and not hostname.endswith(".aliyuncs.com"):
        print(f"Error: BAILIAN_TOKEN_PLAN_API_BASE hostname '{hostname}' is not allowed.", file=sys.stderr)
        sys.exit(EXIT_NETWORK_ERROR)


validate_api_base()


def validate_output_dir():
    """Validate OUTPUT_DIR environment variable for path traversal."""
    output_dir = os.environ.get("OUTPUT_DIR", "")
    if not output_dir:
        return  # Will use default

    real_path = os.path.realpath(output_dir)

    if '..' in output_dir.replace('\\', '/').split('/'):
        print(f"Error: OUTPUT_DIR contains '..' which is not allowed.", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)

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
    home = os.environ.get("HOME")
    if not home:
        print("Error: Neither OUTPUT_DIR nor HOME environment variable is set.", file=sys.stderr)
        sys.exit(EXIT_FILE_ERROR)
    return os.path.join(home, ".zeroclaw", "workspace", "output")


def get_output_path(prompt=None, extension="png"):
    """Generate a default output path in $OUTPUT_DIR."""
    output_dir = get_output_dir()
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if prompt:
        slug = "".join(c if c.isalnum() else "_" for c in prompt[:30]).strip("_")
        filename = f"bailian_{slug}_{timestamp}_{os.getpid()}.{extension}"
    else:
        filename = f"bailian_{timestamp}_{os.getpid()}.{extension}"
    output_path = os.path.join(output_dir, filename)

    real_output_path = os.path.realpath(output_path)
    real_output_dir = os.path.realpath(output_dir)
    if not real_output_path.startswith(real_output_dir + os.sep) and real_output_path != real_output_dir:
        print(f"Error: Computed output path '{output_path}' (resolved to '{real_output_path}') "
              f"escapes the output directory '{real_output_dir}'.", file=sys.stderr)
        sys.exit(EXIT_FILE_ERROR)

    return output_path


def validate_size(size_str, model):
    """Validate --size format and allowed values based on model."""
    if model.startswith("qwen-image-2.0"):
        allowed = {"2048x2048", "1536x1536", "1024x1024"}
        if size_str not in allowed:
            print(f"Error: --size for {model} must be one of {sorted(allowed)}, got '{size_str}'", file=sys.stderr)
            sys.exit(EXIT_INPUT_ERROR)
    elif model == "wan2.7-image-pro":
        allowed = {"2K", "4K"}
        if size_str not in allowed:
            print(f"Error: --size for {model} must be one of {sorted(allowed)}, got '{size_str}'", file=sys.stderr)
            sys.exit(EXIT_INPUT_ERROR)
    elif model == "wan2.7-image":
        allowed = {"2K"}
        if size_str not in allowed:
            print(f"Error: --size for {model} must be one of {sorted(allowed)}, got '{size_str}'", file=sys.stderr)
            sys.exit(EXIT_INPUT_ERROR)
    else:
        # Default: treat as qwen model
        allowed = {"2048x2048", "1536x1536", "1024x1024"}
        if size_str not in allowed:
            print(f"Error: --size for {model} must be one of {sorted(allowed)}, got '{size_str}'", file=sys.stderr)
            sys.exit(EXIT_INPUT_ERROR)


def validate_model(model):
    """Validate model name."""
    allowed_models = {"wan2.7-image-pro", "wan2.7-image", "qwen-image-2.0-pro", "qwen-image-2.0"}
    if model not in allowed_models:
        print(f"Error: --model must be one of {sorted(allowed_models)}, got '{model}'", file=sys.stderr)
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

    # DNS-level SSRF protection: resolve hostname and block private/linklocal IPs
    try:
        addrinfos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        print(f"Error: Could not resolve hostname '{hostname}'.", file=sys.stderr)
        sys.exit(EXIT_NETWORK_ERROR)
    for family, _, _, _, sockaddr in addrinfos:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            print(f"Error: URL hostname '{hostname}' resolves to a private/internal IP address.", file=sys.stderr)
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
                    delay = min(float(ra), MAX_RETRY_AFTER)
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
        try:
            response = _urlopen_with_retry(req, timeout=HTTP_TIMEOUT, opener=opener)
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308):
                redirect_url = e.headers.get('Location')
                if redirect_url:
                    validate_url_safe(redirect_url)
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
                sys.exit(EXIT_INPUT_ERROR)
            if content_length_int > MAX_RESPONSE_SIZE:
                print(f"Error: Response too large ({content_length_int} bytes > {MAX_RESPONSE_SIZE})", file=sys.stderr)
                sys.exit(EXIT_INPUT_ERROR)

        if not check_disk_space(output_path):
            print(f"Error: Insufficient disk space to download file", file=sys.stderr)
            sys.exit(EXIT_FILE_ERROR)

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


def call_api(endpoint, data=None):
    """Make an API call to Bailian."""
    if not os.environ.get("BAILIAN_TOKEN_PLAN_API_KEY"):
        print("Error: BAILIAN_TOKEN_PLAN_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(EXIT_AUTH_ERROR)

    url = f"{API_BASE}{endpoint}"
    headers = {
        "Authorization": f"Bearer {os.environ.get('BAILIAN_TOKEN_PLAN_API_KEY')}",
        "Content-Type": "application/json"
    }

    body = json.dumps(data).encode()

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    try:
        response = _urlopen_with_retry(req, timeout=HTTP_TIMEOUT)
        try:
            return json.loads(response.read().decode())
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON response from API", file=sys.stderr)
            sys.exit(EXIT_API_ERROR)
        finally:
            response.close()
    except urllib.error.HTTPError as e:
        if e.code == 401 or e.code == 403:
            print(f"Error: Authentication failed. Check your BAILIAN_TOKEN_PLAN_API_KEY.", file=sys.stderr)
            sys.exit(EXIT_AUTH_ERROR)
        if e.code == 429:
            print(f"Error: Rate limit exceeded.", file=sys.stderr)
            sys.exit(EXIT_RATE_LIMIT)
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
    args.output = get_output_path(args.prompt)

    data = {
        "model": args.model,
        "input": {
            "messages": [{"role": "user", "content": [{"text": args.prompt}]}]
        },
        "parameters": {
            "size": args.size,
            "n": 1,
            "watermark": False
        }
    }

    response = call_api("/api/v1/services/aigc/multimodal-generation/generation", data=data)

    if "output" not in response:
        if "error" in response:
            print(f"Error: {response['error']}", file=sys.stderr)
            sys.exit(EXIT_API_ERROR)
        else:
            print("Error: No output in API response", file=sys.stderr)
        sys.exit(EXIT_API_ERROR)

    output = response["output"]
    if "choices" not in output or not output["choices"]:
        print("Error: No choices in API response output", file=sys.stderr)
        sys.exit(EXIT_API_ERROR)

    choices = output["choices"]
    if not choices or not choices[0].get("message", {}).get("content"):
        print("Error: No image URL in API response", file=sys.stderr)
        sys.exit(EXIT_API_ERROR)

    image_url = choices[0]["message"]["content"][0].get("image")
    if not image_url:
        print("Error: No image URL in API response content", file=sys.stderr)
        sys.exit(EXIT_API_ERROR)

    if args.verbose:
        print(f"Image URL: {image_url}", file=sys.stderr)

    download_url(image_url, args.output)

    print(f"Image generated: {args.output}")


def main():
    parser = argparse.ArgumentParser(description="Bailian Image API Client")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Generate subcommand
    gen_parser = subparsers.add_parser("generate", help="Generate a new image")
    gen_parser.add_argument("--prompt", required=True, help="Text prompt (1-5000 chars for wan2.7 models, 1-2000 chars for qwen models)")
    gen_parser.add_argument("--model", default="wan2.7-image", help="Model name (wan2.7-image-pro, wan2.7-image, qwen-image-2.0-pro, qwen-image-2.0)")
    gen_parser.add_argument("--size", default="2K", help="Output size (2K, 4K for wan models; 2048x2048, 1536x1536, 1024x1024 for qwen models)")
    gen_parser.add_argument("--verbose", action="store_true", help="Print metadata to stderr")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(EXIT_INPUT_ERROR)

    if check_prompt_injection(args.prompt):
        print(f"Warning: Proceeding with potentially adversarial prompt.", file=sys.stderr)

    # Validate model (before prompt length check, since max length depends on model)
    validate_model(args.model)

    # Sanitize prompt (remove control chars) - do this BEFORE length validation
    args.prompt = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', args.prompt)

    # Validate prompt length (model-specific)
    max_len = 5000 if args.model.startswith("wan2.7") else 2000
    if len(args.prompt) < 1 or len(args.prompt) > max_len:
        print(f"Error: Prompt must be 1-{max_len} characters for {args.model} (got {len(args.prompt)})", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)

    # Validate size
    validate_size(args.size, args.model)

    if args.command == "generate":
        generate_image(args)


if __name__ == "__main__":
    main()
