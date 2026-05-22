#!/usr/bin/env python3
"""
StepFun Text-to-Speech API Client

Convert text to speech using StepFun's stepaudio-2.5-tts model.

Usage:
    python stepfun_tts.py --text "Hello, this is a test" --voice lively-girl
    python stepfun_tts.py --text "Sing this song" --voice cixingnansheng --instruction "happy, upbeat"

Environment:
    STEPFUN_API_KEY - Required. Your StepFun API key.
    OUTPUT_DIR - Optional. Output directory (default: $HOME/.zeroclaw/workspace/output)
"""

import argparse
import json
import os
import re
import sys
import tempfile
import time
import unicodedata
import urllib.request
import urllib.error
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
ALLOWED_HOST_SUFFIXES = {".aliyuncs.com"}  # Alibaba Cloud OSS (StepFun image/audio hosting)
MAX_RESPONSE_SIZE = 50 * 1024 * 1024  # 50 MB
HTTP_TIMEOUT = 60

# Exit codes for agent programmatic handling
EXIT_OK = 0
EXIT_INPUT_ERROR = 2      # Bad arguments, file not found, validation failures
EXIT_AUTH_ERROR = 3       # Missing/invalid API key
EXIT_RATE_LIMIT = 4       # 429 rate limited
EXIT_NETWORK_ERROR = 5    # Connection failures
EXIT_API_ERROR = 6        # API returned error (400, 500, etc.)
EXIT_FILE_ERROR = 7       # Disk full, permission denied, I/O failures

API_URL = os.environ.get("STEPFUN_API_BASE", "https://api.stepfun.ai/step_plan/v1")
API_KEY = os.environ.get("STEPFUN_API_KEY", "")


def _urlopen_with_retry(req, timeout, max_retries=2):
    """Open URL with retry logic for transient failures."""
    for attempt in range(max_retries + 1):
        try:
            return urllib.request.urlopen(req, timeout=timeout)
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


def get_output_path(voice=None, extension="mp3"):
    """Generate a default output path in OUTPUT_DIR."""
    voice = sanitize_voice(voice) if voice else "default"
    output_dir = get_output_dir()
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    voice_slug = voice.replace("-", "_") if voice else "default"
    filename = f"tts_{voice_slug}_{timestamp}_{os.getpid()}.{extension}"
    output_path = os.path.join(output_dir, filename)

    # Resolve both paths and verify output stays under output_dir (symlink attack prevention)
    real_output_path = os.path.realpath(output_path)
    real_output_dir = os.path.realpath(output_dir)
    if not real_output_path.startswith(real_output_dir + os.sep) and real_output_path != real_output_dir:
        print(f"Error: Computed output path '{output_path}' (resolved to '{real_output_path}') "
              f"escapes the output directory '{real_output_dir}'.", file=sys.stderr)
        sys.exit(EXIT_FILE_ERROR)

    return output_path


def sanitize_voice(voice):
    """Sanitize voice name to prevent path traversal in filenames."""
    voice = voice.rstrip('/\\')
    voice = os.path.basename(voice)
    voice = re.sub(r'[^a-zA-Z0-9_-]', '', voice)
    return voice


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


def download_url(url, output_path):
    """Download a URL safely with SSRF protection, size limit, and atomic write."""
    validate_url_safe(url)

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "claw-skills/1.0"})
        # Block automatic redirects - validate manually
        try:
            response = _urlopen_with_retry(req, timeout=HTTP_TIMEOUT)
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308):
                redirect_url = e.headers.get('Location')
                if redirect_url:
                    validate_url_safe(redirect_url)  # Re-validate redirect target
                    req2 = urllib.request.Request(redirect_url, headers={"User-Agent": "claw-skills/1.0"})
                    response = _urlopen_with_retry(req2, timeout=HTTP_TIMEOUT)
                else:
                    raise
            else:
                raise

        content_length = response.headers.get('Content-Length')
        if content_length:
            try:
                parsed_length = int(content_length)
            except ValueError:
                print(f"Error: Invalid Content-Length header value: '{content_length}'", file=sys.stderr)
                sys.exit(1)
            if parsed_length > MAX_RESPONSE_SIZE:
                print(f"Error: Response too large ({parsed_length} bytes > {MAX_RESPONSE_SIZE})", file=sys.stderr)
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


def filter_markdown(text):
    """Remove markdown formatting syntax from text."""
    # Normalize Unicode to prevent homoglyph/RTL bypasses
    text = unicodedata.normalize('NFKC', text)
    # Remove control characters except whitespace
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', '', text)
    # Remove inline code
    text = re.sub(r'`[^`]*`', '', text)
    # Remove headers
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Remove bold/italic markers
    text = re.sub(r'[*_]{1,3}([^*_]+)[*_]{1,3}', r'\1', text)
    # Remove links: [text](url) -> text
    text = re.sub(r'\[([^\]]*)\]\([^\)]*\)', r'\1', text)
    # Remove images: ![alt](url)
    text = re.sub(r'!\[([^\]]*)\]\([^\)]*\)', '', text)
    # Remove horizontal rules
    text = re.sub(r'^---+$', '', text, flags=re.MULTILINE)
    # Remove blockquotes
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)
    # Remove list markers
    text = re.sub(r'^[\*\-\+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)
    return text


def sanitize_text(text, max_len=1000):
    """Remove null bytes and control characters."""
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return text[:max_len]


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
            print(f"Warning: Potential prompt injection detected in input text.", file=sys.stderr)
            return True
    return False


def validate_json_depth(obj, max_depth=10, max_keys=1000):
    """Validate JSON object depth and size to prevent DoS."""
    if isinstance(obj, dict):
        if len(obj) > max_keys:
            raise ValueError(f"pronunciation_map has too many keys ({len(obj)} > {max_keys})")
        for v in obj.values():
            validate_json_depth(v, max_depth - 1, max_keys)
    elif isinstance(obj, list):
        if len(obj) > max_keys:
            raise ValueError(f"pronunciation_map list too large ({len(obj)} > {max_keys})")
        for item in obj:
            validate_json_depth(item, max_depth - 1, max_keys)
    if max_depth <= 0:
        raise ValueError("pronunciation_map exceeds maximum nesting depth")


def text_to_speech(args):
    """Convert text to speech using StepFun TTS."""
    api_key = os.environ.get("STEPFUN_API_KEY", "")
    if not api_key:
        print("Error: STEPFUN_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(EXIT_AUTH_ERROR)

    # Sanitize text input
    args_text = sanitize_text(args.text, 1000)
    if not args_text:
        print("Error: Text is empty after sanitization.", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)

    if check_prompt_injection(args_text):
        print(f"Warning: Proceeding with potentially adversarial input.", file=sys.stderr)

    if not args_text or len(args_text) < 1 or len(args_text) > 1000:
        print(f"Error: Text must be 1-1000 characters (got {len(args_text) if args_text else 0}).", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)

    # Validate ranges
    if args.speed < 0.5 or args.speed > 2.0:
        print(f"Error: Speed must be between 0.5 and 2.0 (got {args.speed}).", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)

    if args.volume < 0.0 or args.volume > 2.0:
        print(f"Error: Volume must be between 0.0 and 2.0 (got {args.volume}).", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)

    if args.sample_rate <= 0:
        print(f"Error: Sample rate must be a positive integer (got {args.sample_rate}).", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)

    text = args_text
    if args.markdown_filter:
        text = filter_markdown(text)
        if not text or len(text) > 1000:
            print(f"Error: Filtered text must be 1-1000 characters.", file=sys.stderr)
            sys.exit(EXIT_INPUT_ERROR)

    output_path = get_output_path(args.voice, args.format)

    data = {
        "model": "stepaudio-2.5-tts",
        "input": text,
        "voice": args.voice,
        "response_format": args.format,
        "return_url": True,
        "speed": args.speed,
        "volume": args.volume,
        "sample_rate": args.sample_rate,
    }

    if args.instruction:
        data["instruction"] = sanitize_text(args.instruction, 500)

    if args.voice_label:
        data["voice_label"] = sanitize_text(args.voice_label, 200)

    if args.pronunciation_map:
        try:
            pronunciation_map = json.loads(args.pronunciation_map)
            validate_json_depth(pronunciation_map)
            data["pronunciation_map"] = pronunciation_map
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error: --pronunciation-map: {e}", file=sys.stderr)
            sys.exit(EXIT_INPUT_ERROR)

    url = f"{API_URL}/audio/speech"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers, method="POST")

    try:
        with _urlopen_with_retry(req, timeout=HTTP_TIMEOUT) as response:
            content_type = response.headers.get('content-type', '')

            if 'application/json' not in content_type:
                print(f"Error: Expected JSON response, got '{content_type}'", file=sys.stderr)
                sys.exit(EXIT_API_ERROR)

            try:
                result = json.loads(response.read().decode())
            except json.JSONDecodeError:
                print(f"Error: Invalid JSON response from TTS API", file=sys.stderr)
                sys.exit(EXIT_API_ERROR)

            url = result.get('url') or (result.get('data') or {}).get('url')
            if not url:
                print(f"Error: No URL in response: {result}", file=sys.stderr)
                sys.exit(EXIT_API_ERROR)

            download_url(url, output_path)

            print(f"Audio generated: {output_path}")
            if args.verbose:
                if 'voice' in data:
                    print(f"Voice: {data['voice']}", file=sys.stderr)
                if data.get('instruction'):
                    print(f"Instruction: {data['instruction']}", file=sys.stderr)
            return output_path
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        if len(error_body) > 200:
            error_msg = error_body[:200] + "... (truncated)"
        else:
            error_msg = error_body
        print(f"TTS API Error ({e.code}): {error_msg}", file=sys.stderr)
        sys.exit(EXIT_API_ERROR)
    except urllib.error.URLError as e:
        print(f"TTS API Error: {e.reason}", file=sys.stderr)
        sys.exit(EXIT_NETWORK_ERROR)


def main():
    parser = argparse.ArgumentParser(description="StepFun Text-to-Speech Client")
    parser.add_argument("--text", required=True, help="Text to speak (1-1000 characters)")
    parser.add_argument("--voice", default="lively-girl", help="Voice ID (default: lively-girl)")
    parser.add_argument("--format", default="mp3", choices=["mp3", "wav", "flac", "opus", "pcm"], help="Audio format")
    parser.add_argument("--instruction", default=None, help="Emotion/style instruction (e.g., 'happy, upbeat')")
    parser.add_argument("--verbose", action="store_true", help="Print metadata to stderr")

    parser.add_argument("--speed", type=float, default=1.0,
                        help="Playback speed multiplier (range: 0.5-2.0, default: 1.0)")
    parser.add_argument("--volume", type=float, default=1.0,
                        help="Volume gain (range: 0.0-2.0, default: 1.0)")
    parser.add_argument("--sample-rate", type=int, default=24000,
                        help="Output sample rate in Hz (default: 24000)")
    parser.add_argument("--voice-label", default=None,
                        help="Voice label for pronunciation guidance")
    parser.add_argument("--pronunciation-map", default=None,
                        help="JSON string for pronunciation overrides (e.g., '{\"word\": \"phonetic\"}')")
    parser.add_argument("--markdown-filter", action="store_true", default=False,
                        help="Filter markdown syntax from input text")

    args = parser.parse_args()

    text_to_speech(args)


if __name__ == "__main__":
    main()
