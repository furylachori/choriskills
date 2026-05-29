#!/usr/bin/env python3
"""
MiniMax Video API Client

Generate videos from text prompts or images using the MiniMax API.

Usage:
    # Text-to-Video
    python minimax_video.py generate --prompt "A serene lake at sunset with birds flying"

    # Image-to-Video
    python minimax_video.py generate --prompt "The cat walking gracefully" --input-image cat.png

    # Sync mode (wait for completion)
    python minimax_video.py generate --prompt "Ocean waves crashing" --sync

    # Retrieve a previously submitted video
    python minimax_video.py retrieve --task-id <id>

Environment:
    MINIMAX_API_KEY - Required. Your MiniMax API key.
    MINIMAX_API_BASE - Optional. API base URL (default: https://api.minimax.io/v1)
"""

import argparse
import base64
import ipaddress
import json
import os
import re
import socket
import sys
import tempfile
import time
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime


ALLOWED_ENV_KEYS = {"MINIMAX_API_KEY", "MINIMAX_API_BASE", "OUTPUT_DIR"}


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
            if key not in ALLOWED_ENV_KEYS:
                continue
            if key and value and key not in os.environ:
                os.environ[key] = value


_load_env_file()


ALLOWED_SCHEMES = {"https"}
ALLOWED_HOSTS = {"api.minimax.io"}
ALLOWED_HOST_SUFFIXES = {"cdn.minimax.io"}
ALLOWED_RESOLUTIONS = {"512P", "768P", "1080P"}
ALLOWED_MODELS = {"MiniMax-Hailuo-2.3", "MiniMax-Hailuo-2.3-Fast", "MiniMax-Hailuo-02"}
MAX_RESPONSE_SIZE = 500 * 1024 * 1024  # 500 MB
MAX_INPUT_IMAGE_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_RETRY_AFTER = 60
HTTP_TIMEOUT = 60
POLL_INTERVAL = 5  # seconds
POLL_MAX_ATTEMPTS = 120  # 10 minutes max


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(newurl, code, msg, headers, fp)


API_URL = os.environ.get("MINIMAX_API_BASE", "https://api.minimax.io/v1")
API_KEY = os.environ.get("MINIMAX_API_KEY", "")

# Exit codes for agent programmatic handling
EXIT_OK = 0
EXIT_INPUT_ERROR = 2      # Bad arguments, file not found, validation failures
EXIT_AUTH_ERROR = 3      # Missing/invalid API key
EXIT_RATE_LIMIT = 4     # Rate limited
EXIT_NETWORK_ERROR = 5  # Connection failures
EXIT_API_ERROR = 6       # API returned error
EXIT_FILE_ERROR = 7      # Disk full, permission denied, I/O failures


def validate_api_base():
    """Validate MINIMAX_API_BASE environment variable."""
    from urllib.parse import urlparse
    base = os.environ.get("MINIMAX_API_BASE", "")
    if not base:
        return  # Will use default
    parsed = urlparse(base)
    if parsed.scheme != "https":
        print(f"Error: MINIMAX_API_BASE must use https scheme, got '{parsed.scheme}'", file=sys.stderr)
        sys.exit(EXIT_NETWORK_ERROR)
    hostname = parsed.hostname
    if not hostname or hostname != "api.minimax.io":
        print(f"Error: MINIMAX_API_BASE hostname '{hostname}' is not allowed. Must be api.minimax.io", file=sys.stderr)
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


def strip_control_chars(text):
    """Remove control characters from text."""
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)


def get_output_path(prompt=None, extension="mp4"):
    """Generate a default output path in $OUTPUT_DIR."""
    output_dir = get_output_dir()
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if prompt:
        cleaned_prompt = strip_control_chars(prompt)
        slug = "".join(c if c.isalnum() else "_" for c in cleaned_prompt[:30]).strip("_")
        filename = f"video_{slug}_{timestamp}_{os.getpid()}.{extension}"
    else:
        filename = f"video_{timestamp}_{os.getpid()}.{extension}"
    output_path = os.path.join(output_dir, filename)

    real_output_path = os.path.realpath(output_path)
    real_output_dir = os.path.realpath(output_dir)
    if not real_output_path.startswith(real_output_dir + os.sep) and real_output_path != real_output_dir:
        print(f"Error: Computed output path '{output_path}' (resolved to '{real_output_path}') "
              f"escapes the output directory '{real_output_dir}'.", file=sys.stderr)
        sys.exit(EXIT_FILE_ERROR)

    return output_path


def validate_input_path(input_path):
    """Validate that input path has no path traversal components."""
    normalized = input_path.replace('\\', '/')
    parts = normalized.split('/')
    if '..' in parts:
        print(f"Error: Input path contains '..' which is not allowed.", file=sys.stderr)
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

    # Check resolved IP against private ranges
    try:
        addr_info = socket.getaddrinfo(hostname, None)
        for family, _, _, _, sockaddr in addr_info:
            ip = sockaddr[0]
            try:
                addr = ipaddress.ip_address(ip)
                if addr.is_private or addr.is_loopback or addr.is_link_local:
                    print(f"Error: URL resolves to private/loopback/link-local IP '{ip}'.", file=sys.stderr)
                    sys.exit(EXIT_INPUT_ERROR)
            except ValueError:
                print(f"Error: Invalid IP address '{ip}'.", file=sys.stderr)
                sys.exit(EXIT_INPUT_ERROR)
    except socket.gaierror:
        pass  # Let the connection fail naturally — can't SSRF if we can't resolve


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
                sys.exit(EXIT_FILE_ERROR)
            if content_length_int > MAX_RESPONSE_SIZE:
                print(f"Error: Response too large ({content_length_int} bytes > {MAX_RESPONSE_SIZE})", file=sys.stderr)
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
            print(f"Warning: Potential prompt injection detected.", file=sys.stderr)
            return True
    return False


def call_api(endpoint, data=None, method="POST"):
    """Make an API call to MiniMax."""
    if not API_KEY:
        print("Error: MINIMAX_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(EXIT_AUTH_ERROR)

    url = f"{API_URL}/{endpoint}"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    body = json.dumps(data).encode()

    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        response = _urlopen_with_retry(req, timeout=HTTP_TIMEOUT)
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
        # Check for specific MiniMax error codes
        try:
            err_json = json.loads(error_body)
            base_resp = err_json.get("base_resp", {})
            status_code = base_resp.get("status_code", 0)
            status_msg = base_resp.get("status_msg", error_msg)
            if status_code == 1002:
                print(f"Rate limited: {status_msg}", file=sys.stderr)
                sys.exit(EXIT_RATE_LIMIT)
            elif status_code == 1004:
                print(f"Auth failed: {status_msg}", file=sys.stderr)
                sys.exit(EXIT_AUTH_ERROR)
            elif status_code == 1026:
                print(f"Prompt flagged: {status_msg}", file=sys.stderr)
                sys.exit(EXIT_API_ERROR)
            elif status_code == 1027:
                print(f"Content flagged: {status_msg}", file=sys.stderr)
                sys.exit(EXIT_API_ERROR)
            elif status_code == 2008:
                print(f"Insufficient balance: {status_msg}", file=sys.stderr)
                sys.exit(EXIT_API_ERROR)
            elif status_code == 2013:
                print(f"Invalid parameters: {status_msg}", file=sys.stderr)
                sys.exit(EXIT_INPUT_ERROR)
            elif status_code == 2049:
                print(f"Invalid API key: {status_msg}", file=sys.stderr)
                sys.exit(EXIT_AUTH_ERROR)
        except (json.JSONDecodeError, KeyError):
            pass
        print(f"API Error ({e.code}): {error_msg}", file=sys.stderr)
        sys.exit(EXIT_API_ERROR)
    except urllib.error.URLError as e:
        print(f"API Error: {e.reason}", file=sys.stderr)
        sys.exit(EXIT_NETWORK_ERROR)


def query_task(task_id):
    """Query the status of a video generation task."""
    url = f"{API_URL}/query/video_generation?task_id={urllib.parse.quote(task_id)}"
    headers = {"Authorization": f"Bearer {API_KEY}"}

    req = urllib.request.Request(url, headers=headers, method="GET")

    try:
        response = _urlopen_with_retry(req, timeout=HTTP_TIMEOUT)
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


def get_file_download_url(file_id):
    """Get the download URL for a generated video file."""
    url = f"{API_URL}/files/retrieve?file_id={urllib.parse.quote(file_id)}"
    headers = {"Authorization": f"Bearer {API_KEY}"}

    req = urllib.request.Request(url, headers=headers, method="GET")

    try:
        response = _urlopen_with_retry(req, timeout=HTTP_TIMEOUT)
        try:
            resp_data = json.loads(response.read().decode())
            file_data = resp_data.get("file", {})
            return file_data.get("download_url")
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


def poll_task(task_id, args):
    """Poll until the task completes or fails."""
    for attempt in range(POLL_MAX_ATTEMPTS):
        result = query_task(task_id)

        base_resp = result.get("base_resp", {})
        if base_resp.get("status_code") == 1002:
            wait_time = 30
            print(f"Rate limited (1002), waiting {wait_time}s before retry", file=sys.stderr)
            time.sleep(wait_time)
            continue

        status = result.get("status", "Unknown")

        if args.verbose:
            print(f"[{attempt+1}/{POLL_MAX_ATTEMPTS}] Status: {status}", file=sys.stderr)

        if status == "Success":
            file_id = result.get("file_id")
            if not file_id:
                print("Error: Task succeeded but no file_id returned", file=sys.stderr)
                sys.exit(EXIT_API_ERROR)
            return file_id
        elif status in ("Fail", "Failed"):
            status_msg = result.get("base_resp", {}).get("status_msg", "Unknown error")
            print(f"Video generation failed: {status_msg}", file=sys.stderr)
            sys.exit(EXIT_API_ERROR)
        elif status in ("Processing", "Queueing"):
            time.sleep(POLL_INTERVAL)
        else:
            print(f"Unknown status '{status}', continuing...", file=sys.stderr)
            time.sleep(POLL_INTERVAL)

    print("Error: Video generation timed out after 10 minutes", file=sys.stderr)
    sys.exit(EXIT_NETWORK_ERROR)


def generate_video(args):
    """Generate a video from text prompt or image."""
    args.prompt = strip_control_chars(args.prompt)

    if check_prompt_injection(args.prompt):
        print(f"Warning: Proceeding with potentially adversarial prompt.", file=sys.stderr)

    if len(args.prompt) < 1 or len(args.prompt) > 2000:
        print(f"Error: Prompt must be 1-2000 characters (got {len(args.prompt)})", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)

    data = {
        "model": args.model,
        "prompt": args.prompt,
    }

    if args.duration is not None:
        data["duration"] = args.duration
    if args.resolution:
        data["resolution"] = args.resolution
    if args.prompt_optimizer:
        data["prompt_optimizer"] = True
    if args.fast_pretreatment:
        data["fast_pretreatment"] = True

    if args.input_image:
        validate_input_path(args.input_image)
        real_path = os.path.realpath(args.input_image)
        forbidden_prefixes = ('/etc', '/sys', '/proc', '/dev', '/boot')
        if real_path.startswith(forbidden_prefixes):
            print(f"Error: Input image path points to a system directory.", file=sys.stderr)
            sys.exit(EXIT_INPUT_ERROR)
        if not os.path.exists(args.input_image):
            print(f"Error: Input image file '{args.input_image}' does not exist.", file=sys.stderr)
            sys.exit(EXIT_INPUT_ERROR)
        file_size = os.path.getsize(args.input_image)
        if file_size > MAX_INPUT_IMAGE_SIZE:
            print(f"Error: Input image file too large ({file_size} bytes > {MAX_INPUT_IMAGE_SIZE} bytes).", file=sys.stderr)
            sys.exit(EXIT_INPUT_ERROR)
        try:
            fd = os.open(args.input_image, os.O_RDONLY | os.O_NOFOLLOW)
        except OSError as e:
            print(f"Error: Cannot open input image (possible symlink): {e}", file=sys.stderr)
            sys.exit(EXIT_INPUT_ERROR)
        with os.fdopen(fd, 'rb') as f:
            image_data = f.read()
        b64_image = base64.b64encode(image_data).decode('ascii')
        data["first_frame_image"] = b64_image

    response = call_api("video_generation", data=data)

    base_resp = response.get("base_resp", {})
    if base_resp.get("status_code") != 0:
        status_msg = base_resp.get("status_msg", "Unknown error")
        status_code = base_resp.get("status_code")
        print(f"Error: API returned status_code {status_code}: {status_msg}", file=sys.stderr)
        if status_code == 1002:
            sys.exit(EXIT_RATE_LIMIT)
        elif status_code == 1004:
            sys.exit(EXIT_AUTH_ERROR)
        elif status_code == 1026:
            sys.exit(EXIT_API_ERROR)
        elif status_code == 1027:
            sys.exit(EXIT_API_ERROR)
        elif status_code == 2008:
            sys.exit(EXIT_API_ERROR)
        elif status_code == 2049:
            sys.exit(EXIT_AUTH_ERROR)
        sys.exit(EXIT_API_ERROR)

    task_id = response.get("task_id")
    if not task_id:
        print("Error: No task_id in response", file=sys.stderr)
        sys.exit(EXIT_API_ERROR)

    if args.verbose:
        print(f"Task submitted: {task_id}", file=sys.stderr)
        print(f"Status: {API_URL}/query/video_generation?task_id={urllib.parse.quote(task_id)}", file=sys.stderr)

    if not args.sync:
        print(f"Task submitted: {task_id}")
        print(f"Status: {API_URL}/query/video_generation?task_id={urllib.parse.quote(task_id)}")
        sys.exit(EXIT_OK)

    file_id = poll_task(task_id, args)

    if args.verbose:
        print(f"File ID: {file_id}", file=sys.stderr)

    download_url_result = get_file_download_url(file_id)
    if not download_url_result:
        print("Error: No download URL in file response", file=sys.stderr)
        sys.exit(EXIT_API_ERROR)

    if args.verbose:
        print(f"Download URL: {download_url_result}", file=sys.stderr)

    output_path = get_output_path(args.prompt)

    if not check_disk_space(output_path):
        print("Error: Insufficient disk space for output file.", file=sys.stderr)
        sys.exit(EXIT_FILE_ERROR)

    download_url(download_url_result, output_path)

    print(f"Video generated: {output_path}")


def retrieve_video(args):
    """Retrieve a video by task_id."""
    if not args.task_id or not args.task_id.strip():
        print("Error: --task-id cannot be empty.", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)
    if len(args.task_id) > 256:
        print("Error: --task-id is too long (max 256 characters).", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)

    result = query_task(args.task_id)
    
    base_resp = result.get("base_resp", {})
    status = result.get("status", "Unknown")
    
    if args.verbose:
        print(f"Task status: {status}", file=sys.stderr)
        print(f"Task ID: {args.task_id}", file=sys.stderr)
        if status == "Success":
            print(f"File ID: {result.get('file_id')}", file=sys.stderr)
    
    if status == "Success":
        file_id = result.get("file_id")
        if not file_id:
            print("Error: Task succeeded but no file_id returned", file=sys.stderr)
            sys.exit(EXIT_API_ERROR)
        
        download_url_result = get_file_download_url(file_id)
        if not download_url_result:
            print("Error: No download URL in file response", file=sys.stderr)
            sys.exit(EXIT_API_ERROR)
        
        output_path = get_output_path(args.task_id)
        
        if not check_disk_space(output_path):
            print("Error: Insufficient disk space for output file.", file=sys.stderr)
            sys.exit(EXIT_FILE_ERROR)
        
        download_url(download_url_result, output_path)
        print(f"Video downloaded: {output_path}")
        
    elif status in ("Processing", "Queueing"):
        print(f"Status: {status}")
        print(f"Task ID: {args.task_id}")
        print(f"Video is still {status.lower()}. Try again in a few minutes.", file=sys.stderr)
        if args.sync:
            print("Waiting for completion...", file=sys.stderr)
            file_id = poll_task(args.task_id, args)
            download_url_result = get_file_download_url(file_id)
            if not download_url_result:
                print("Error: No download URL in file response", file=sys.stderr)
                sys.exit(EXIT_API_ERROR)
            output_path = get_output_path(args.task_id)
            if not check_disk_space(output_path):
                print("Error: Insufficient disk space for output file.", file=sys.stderr)
                sys.exit(EXIT_FILE_ERROR)
            download_url(download_url_result, output_path)
            print(f"Video downloaded: {output_path}")
        else:
            sys.exit(EXIT_OK)
    
    elif status in ("Fail", "Failed"):
        status_msg = base_resp.get("status_msg", "Unknown error")
        print(f"Video generation failed: {status_msg}", file=sys.stderr)
        sys.exit(EXIT_API_ERROR)
    
    else:
        print(f"Unknown status: {status}", file=sys.stderr)
        sys.exit(EXIT_API_ERROR)


def main():
    parser = argparse.ArgumentParser(description="MiniMax Video API Client")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Generate subcommand
    gen_parser = subparsers.add_parser("generate", help="Generate a new video")
    gen_parser.add_argument("--prompt", required=True, help="Text prompt (1-2000 characters)")
    gen_parser.add_argument("--model", default="MiniMax-Hailuo-2.3", help="Model name")
    gen_parser.add_argument("--duration", type=int, default=None, help="Video length in seconds (6 or 10)")
    gen_parser.add_argument("--resolution", default=None, help="Output resolution (512P, 768P, 1080P)")
    gen_parser.add_argument("--prompt-optimizer", action="store_true", help="Enable prompt optimizer")
    gen_parser.add_argument("--fast-pretreatment", action="store_true", help="Enable fast pretreatment")
    gen_parser.add_argument("--input-image", default=None, help="Input image file for I2V")
    gen_parser.add_argument("--sync", action="store_true", help="Wait for completion")
    gen_parser.add_argument("--verbose", action="store_true", help="Print metadata to stderr")

    # Retrieve subcommand
    ret_parser = subparsers.add_parser("retrieve", help="Retrieve a video by task ID")
    ret_parser.add_argument("--task-id", required=True, help="Task ID from a previous generate command")
    ret_parser.add_argument("--sync", action="store_true", help="Wait for completion if still processing")
    ret_parser.add_argument("--verbose", action="store_true", help="Print metadata to stderr")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(EXIT_INPUT_ERROR)

    if args.command == "generate":
        if args.model not in ALLOWED_MODELS:
            print(f"Error: --model must be one of {ALLOWED_MODELS}, got '{args.model}'", file=sys.stderr)
            sys.exit(EXIT_INPUT_ERROR)
        if args.duration is not None and args.duration not in (6, 10):
            print(f"Error: --duration must be 6 or 10, got {args.duration}", file=sys.stderr)
            sys.exit(EXIT_INPUT_ERROR)
        if args.resolution is not None and args.resolution not in ALLOWED_RESOLUTIONS:
            print(f"Error: --resolution must be one of {ALLOWED_RESOLUTIONS}, got '{args.resolution}'", file=sys.stderr)
            sys.exit(EXIT_INPUT_ERROR)
        generate_video(args)

    elif args.command == "retrieve":
        retrieve_video(args)


if __name__ == "__main__":
    main()
