#!/usr/bin/env python3
"""
Bailian Wan2.7 Image API Client

Generate images using the Bailian Wan2.7 model.

Usage:
    python bailian_wan_image.py generate --prompt "A serene mountain landscape at sunset, photorealistic"

Environment:
    BAILIAN_WAN_API_KEY - Required. Your Bailian API key.
    BAILIAN_WAN_API_BASE - Optional. API base URL (default: https://token-plan.ap-southeast-1.maas.aliyuncs.com)
"""

import argparse
import http.client
import ipaddress
import json
import os
import re
import socket
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime

# ---------------------------------------------------------------------------
# Inlined from bailian_shared/http_utils.py
# ---------------------------------------------------------------------------

EXIT_OK = 0
EXIT_INPUT_ERROR = 2
EXIT_AUTH_ERROR = 3
EXIT_RATE_LIMIT = 4
EXIT_NETWORK_ERROR = 5
EXIT_API_ERROR = 6
EXIT_FILE_ERROR = 7

MAX_RESPONSE_SIZE = 50 * 1024 * 1024  # 50 MB
HTTP_TIMEOUT = 120
MAX_RETRY_AFTER = 300


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(newurl, code, msg, headers, fp)


def _urlopen_with_retry(req, timeout, max_retries=3, opener=None):
    """Open URL with retry logic for transient failures (429, 500-504)."""
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
            if isinstance(e.reason, socket.timeout):
                raise  # Don't retry on timeout
            if attempt < max_retries:
                print(f"Retrying after {2**attempt:.1f}s (attempt {attempt+1}/{max_retries}, network error)", file=sys.stderr)
                time.sleep(2 ** attempt)
            else:
                raise
    raise RuntimeError("Unreachable")


def _load_env_file(env_path, allowed_keys):
    """Load environment variables from .env file with key filtering."""
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
            # Strip surrounding quotes
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            if key and value and key not in os.environ and key in allowed_keys:
                os.environ[key] = value


def validate_api_base(url, allowed_host, allowed_suffixes):
    """Validate API base URL has allowed hostname."""
    from urllib.parse import urlparse
    if not url:
        return
    parsed = urlparse(url)
    if parsed.scheme != "https":
        print(f"Error: API base must use https scheme, got '{parsed.scheme}'", file=sys.stderr)
        sys.exit(EXIT_NETWORK_ERROR)
    hostname = parsed.hostname
    if not hostname:
        print(f"Error: API base has no hostname.", file=sys.stderr)
        sys.exit(EXIT_NETWORK_ERROR)
    if hostname != allowed_host and not any(hostname.endswith(suffix) for suffix in allowed_suffixes):
        print(f"Error: API base hostname '{hostname}' is not allowed.", file=sys.stderr)
        sys.exit(EXIT_NETWORK_ERROR)


def check_disk_space(path, required_bytes=100 * 1024 * 1024):
    """Check if there's enough disk space. Returns True if ok."""
    try:
        stat = os.statvfs(os.path.dirname(os.path.abspath(path)))
        available = stat.f_bavail * stat.f_frsize
        return available >= required_bytes
    except OSError:
        return True  # Can't check, proceed anyway


def strip_control_chars(text):
    """Remove control characters from text."""
    import re as _re
    return _re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)


# ---------------------------------------------------------------------------
# Inlined from bailian_shared/ssrf.py
# ---------------------------------------------------------------------------

def validate_url_safe(url, allowed_hosts, allowed_suffixes):
    """Validate that a URL is safe to fetch (SSRF protection).
    
    Args:
        url: URL to validate
        allowed_hosts: Set of exact hostnames to allow
        allowed_suffixes: Set of allowed hostname suffixes
    """
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme not in {"https"}:
        print(f"Error: URL scheme '{parsed.scheme}' is not allowed. Only https:// is permitted.", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)
    hostname = parsed.hostname
    if not hostname:
        print(f"Error: URL has no hostname.", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)
    if hostname not in allowed_hosts and not any(hostname.endswith(suffix) for suffix in allowed_suffixes):
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


def download_url(url, api_key, max_size, output_path, allowed_hosts, allowed_suffixes, timeout=HTTP_TIMEOUT):
    """Download a URL safely with SSRF protection, size limit, and atomic write.
    
    Args:
        url: URL to download
        api_key: API key for Authorization header
        max_size: Maximum response size in bytes
        output_path: Where to save the file
        allowed_hosts: Set of exact hostnames to allow
        allowed_suffixes: Set of allowed hostname suffixes
    """
    validate_url_safe(url, allowed_hosts, allowed_suffixes)

    try:
        opener = urllib.request.build_opener(_NoRedirectHandler)
        req = urllib.request.Request(url, headers={
            "User-Agent": "claw-skills/1.0",
            "Authorization": f"Bearer {api_key}"
        })
        try:
            response = _urlopen_with_retry(req, timeout=timeout, opener=opener)
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308):
                redirect_url = e.headers.get('Location')
                if redirect_url:
                    validate_url_safe(redirect_url, allowed_hosts, allowed_suffixes)
                    req2 = urllib.request.Request(redirect_url, headers={
                        "User-Agent": "claw-skills/1.0",
                        "Authorization": f"Bearer {api_key}"
                    })
                    response = _urlopen_with_retry(req2, timeout=timeout, opener=opener)
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
            if content_length_int > max_size:
                print(f"Error: Response too large ({content_length_int} bytes > {max_size})", file=sys.stderr)
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
                    if total > max_size:
                        print(f"Error: Response too large (>{max_size} bytes)", file=sys.stderr)
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
    except socket.timeout:
        print(f"TIMEOUT: Request timed out after {timeout}s. Try again with --timeout {timeout*2}", file=sys.stderr)
        sys.exit(EXIT_NETWORK_ERROR)
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        if len(error_body) > 200:
            error_msg = error_body[:200] + "... (truncated)"
        else:
            error_msg = error_body
        print(f"Error downloading from URL: HTTP {e.code}: {error_msg}", file=sys.stderr)
        sys.exit(EXIT_API_ERROR)
    except urllib.error.URLError as e:
        if isinstance(e.reason, socket.timeout):
            print(f"TIMEOUT: Request timed out after {timeout}s. Try again with --timeout {timeout*2}", file=sys.stderr)
            sys.exit(EXIT_NETWORK_ERROR)
        print(f"Error downloading from URL: {e.reason}", file=sys.stderr)
        sys.exit(EXIT_NETWORK_ERROR)


# ---------------------------------------------------------------------------
# Bailian Wan2.7 Image API Client
# ---------------------------------------------------------------------------

# Model is hardcoded - agents cannot change it
MODEL = "wan2.7-image-pro"
MAX_PROMPT_LENGTH = 5000
DEFAULT_SIZE = "2K"
ALLOWED_SIZES = {"2K", "4K"}

ALLOWED_HOST = "token-plan.ap-southeast-1.maas.aliyuncs.com"
ALLOWED_HOST_SUFFIXES = {".aliyuncs.com"}
_ALLOWED_ENV_KEYS = {"BAILIAN_WAN_API_KEY", "BAILIAN_WAN_API_BASE", "OUTPUT_DIR"}

_script_dir = os.path.dirname(os.path.abspath(__file__))
_WAN_DEFAULT_API_BASE = "https://token-plan.ap-southeast-1.maas.aliyuncs.com"


def validate_output_dir():
    """Validate OUTPUT_DIR environment variable for path traversal."""
    output_dir = os.environ.get("OUTPUT_DIR", "")
    if not output_dir:
        return

    if '..' in output_dir.replace('\\', '/').split('/'):
        print(f"Error: OUTPUT_DIR contains '..' which is not allowed: {output_dir}", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)

    forbidden_prefixes = ('/etc', '/sys', '/proc', '/dev', '/boot')
    real_path = os.path.realpath(output_dir)
    if real_path.startswith(forbidden_prefixes):
        print(f"Error: OUTPUT_DIR points to a system directory: {output_dir}", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)


def get_output_dir():
    """Get OUTPUT_DIR from environment or use default."""
    output_dir = os.environ.get("OUTPUT_DIR")
    if output_dir:
        output_dir = os.path.expanduser(output_dir)
        validate_output_dir()
        return output_dir
    home = os.environ.get("HOME")
    if not home:
        print("Error: Neither OUTPUT_DIR nor HOME environment variable is set.", file=sys.stderr)
        sys.exit(EXIT_FILE_ERROR)
    return os.path.join(home, ".zeroclaw", "agents", "default", "workspace", "output")


def get_output_path(prompt=None, extension="png"):
    """Generate a default output path in $OUTPUT_DIR."""
    output_dir = get_output_dir()
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if prompt:
        slug = "".join(c if c.isalnum() else "_" for c in prompt[:30]).strip("_")
        filename = f"bailian_wan_{slug}_{timestamp}_{os.getpid()}.{extension}"
    else:
        filename = f"bailian_wan_{timestamp}_{os.getpid()}.{extension}"
    output_path = os.path.join(output_dir, filename)

    real_output_path = os.path.realpath(output_path)
    real_output_dir = os.path.realpath(output_dir)
    if not real_output_path.startswith(real_output_dir + os.sep) and real_output_path != real_output_dir:
        print(f"Error: Computed output path '{output_path}' escapes the output directory.", file=sys.stderr)
        sys.exit(EXIT_FILE_ERROR)

    return output_path


def _print_image_metadata(path):
    """Print image file metadata to stdout."""
    ext = os.path.splitext(path)[1].lstrip('.').upper()
    print(f"Format: {ext}")
    try:
        print(f"Size: {os.path.getsize(path)} bytes")
    except OSError:
        pass
    try:
        from PIL import Image
        with Image.open(path) as img:
            print(f"Dimensions: {img.width}x{img.height}")
    except (ImportError, Exception):
        pass


def validate_size(size_str):
    """Validate --size format for Wan2.7 model."""
    if size_str not in ALLOWED_SIZES:
        print(f"Error: --size must be one of {sorted(ALLOWED_SIZES)}, got '{size_str}'", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)


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


def call_api(endpoint, data=None, timeout=HTTP_TIMEOUT):
    """Make an API call to Bailian."""
    api_key = os.environ.get("BAILIAN_WAN_API_KEY")
    if not api_key:
        print("Error: BAILIAN_WAN_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(EXIT_AUTH_ERROR)

    api_base = os.environ.get("BAILIAN_WAN_API_BASE", _WAN_DEFAULT_API_BASE)
    url = f"{api_base}{endpoint}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    try:
        with _urlopen_with_retry(req, timeout=timeout) as response:
            try:
                return json.loads(response.read().decode())
            except json.JSONDecodeError:
                print(f"Error: Invalid JSON response from API", file=sys.stderr)
                sys.exit(EXIT_API_ERROR)
    except socket.timeout:
        print(f"TIMEOUT: Request timed out after {timeout}s. Try again with --timeout {timeout*2}", file=sys.stderr)
        sys.exit(EXIT_NETWORK_ERROR)
    except urllib.error.HTTPError as e:
        if e.code == 401 or e.code == 403:
            print(f"Error: Authentication failed. Check your BAILIAN_WAN_API_KEY.", file=sys.stderr)
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
        if isinstance(e.reason, socket.timeout):
            print(f"TIMEOUT: Request timed out after {timeout}s. Try again with --timeout {timeout*2}", file=sys.stderr)
            sys.exit(EXIT_NETWORK_ERROR)
        print(f"API Error: {e.reason}", file=sys.stderr)
        sys.exit(EXIT_NETWORK_ERROR)


def generate_image(args):
    """Generate a new image from a text prompt."""
    args.output = get_output_path(args.prompt)

    data = {
        "model": MODEL,
        "input": {
            "messages": [{"role": "user", "content": [{"text": args.prompt}]}]
        },
        "parameters": {
            "size": args.size,
            "n": 1,
            "watermark": False
        }
    }

    response = call_api("/api/v1/services/aigc/multimodal-generation/generation", data=data, timeout=args.timeout)

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

    api_key = os.environ.get("BAILIAN_WAN_API_KEY", "")
    download_url(image_url, api_key, 50 * 1024 * 1024, args.output, {ALLOWED_HOST}, ALLOWED_HOST_SUFFIXES, timeout=args.timeout)

    print(args.output)
    _print_image_metadata(args.output)


def main():
    _load_env_file(os.path.join(_script_dir, '.env'), _ALLOWED_ENV_KEYS)
    api_base = os.environ.get("BAILIAN_WAN_API_BASE", _WAN_DEFAULT_API_BASE)
    validate_api_base(api_base, ALLOWED_HOST, ALLOWED_HOST_SUFFIXES)

    parser = argparse.ArgumentParser(description="Bailian Wan2.7 Image API Client")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    gen_parser = subparsers.add_parser("generate", help="Generate a new image")
    gen_parser.add_argument("--prompt", required=True, help=f"Text prompt (1-{MAX_PROMPT_LENGTH} chars)")
    gen_parser.add_argument("--size", default=DEFAULT_SIZE, help=f"Output size ({', '.join(sorted(ALLOWED_SIZES))})")
    gen_parser.add_argument("--verbose", action="store_true", help="Print metadata to stderr")
    gen_parser.add_argument("--timeout", type=int, default=120, help="HTTP timeout in seconds (default: 120)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(EXIT_INPUT_ERROR)

    args.prompt = strip_control_chars(args.prompt)

    if check_prompt_injection(args.prompt):
        print(f"Warning: Proceeding with potentially adversarial prompt.", file=sys.stderr)

    if len(args.prompt) < 1 or len(args.prompt) > MAX_PROMPT_LENGTH:
        print(f"Error: Prompt must be 1-{MAX_PROMPT_LENGTH} characters (got {len(args.prompt)})", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)

    validate_size(args.size)

    if args.command == "generate":
        generate_image(args)


if __name__ == "__main__":
    main()
