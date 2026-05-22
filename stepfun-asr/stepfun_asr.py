# NOTE on live ASR testing:
#
# The StepFun ASR API requires real human speech audio to produce a transcript.
# A synthetic sine wave (e.g. 440Hz tone) or any other non-speech signal is not
# recognised as speech and the SSE stream returns zero data, causing any
# live-integration test to fail.  Since real speech cannot be generated
# programmatically in this codebase, automated live ASR tests are deliberately
# omitted.  To verify ASR manually, use a recorded speech file:
#     python stepfun_asr.py --audio recording.wav --language en


#!/usr/bin/env python3
"""
StepFun Automatic Speech Recognition (ASR) API Client

Transcribe audio to text using StepFun's stepaudio-2.5-asr model.

Usage:
    python stepfun_asr.py --audio recording.mp3
    python stepfun_asr.py --audio recording.wav --language en

Environment:
    STEPFUN_API_KEY - Required. Your StepFun API key.
    OUTPUT_DIR - Optional. Output directory for transcript (default: $HOME/.zeroclaw/workspace/output)
"""

import argparse
import base64
import json
import mimetypes
import os
import re
import sys
import time
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
MAX_RESPONSE_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_SSE_BUFFER = 10 * 1024 * 1024    # 10 MB max SSE buffer
SSE_READ_TIMEOUT = 120               # 2 minute wall-clock timeout for SSE streaming
HTTP_TIMEOUT = 60

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


def get_output_path(extension="txt"):
    """Generate a default output path in OUTPUT_DIR."""
    output_dir = get_output_dir()
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"asr_transcript_{timestamp}_{os.getpid()}.{extension}"
    output_path = os.path.join(output_dir, filename)

    # Resolve the full path and verify it is still under the validated output_dir
    real_output_path = os.path.realpath(output_path)
    real_output_dir = os.path.realpath(output_dir)
    if not real_output_path.startswith(real_output_dir + os.sep) and real_output_path != real_output_dir:
        print(f"Error: Computed output path '{output_path}' (resolved to '{real_output_path}') "
              f"escapes the output directory '{real_output_dir}'.", file=sys.stderr)
        sys.exit(EXIT_FILE_ERROR)

    return output_path


def transcribe_audio(args):
    """Transcribe audio using StepFun ASR."""
    api_key = os.environ.get("STEPFUN_API_KEY", "")
    if not api_key:
        print("Error: STEPFUN_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(EXIT_AUTH_ERROR)

    if not os.path.exists(args.audio):
        print(f"Error: Audio file '{args.audio}' does not exist.", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)

    if not os.path.isfile(args.audio):
        print(f"Error: '{args.audio}' is not a regular file.", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)

    # Resolve real path to prevent symlink attacks to sensitive system files
    real_audio_path = os.path.realpath(args.audio)
    sensitive_prefixes = ('/etc', '/sys', '/proc', '/dev', '/boot')
    if any(real_audio_path.startswith(p) for p in sensitive_prefixes):
        print(f"Error: Audio file resolves to a sensitive system path '{real_audio_path}'.", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)

    # Validate no path traversal in audio path
    normalized = args.audio.replace('\\', '/')
    parts = normalized.split('/')
    if '..' in parts:
        print(f"Error: Audio path contains '..' which is not allowed.", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)

    # Read audio file and encode to base64
    # Check file size before reading into memory
    audio_size = os.path.getsize(args.audio)
    if audio_size > MAX_RESPONSE_SIZE:
        print(f"Error: Audio file too large ({audio_size} bytes > {MAX_RESPONSE_SIZE})", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)

    try:
        fd = os.open(args.audio, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as e:
        print(f"Error: Could not open audio file '{args.audio}': {e}", file=sys.stderr)
        sys.exit(EXIT_FILE_ERROR)
    try:
        with os.fdopen(fd, "rb") as f:
            audio_data = f.read()
    except OSError as e:
        print(f"Error: Could not read audio file '{args.audio}': {e}", file=sys.stderr)
        sys.exit(EXIT_FILE_ERROR)
    
    if len(audio_data) > MAX_RESPONSE_SIZE:
        print(f"Error: Audio file too large ({len(audio_data)} bytes > {MAX_RESPONSE_SIZE})", file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)
    
    audio_base64 = base64.b64encode(audio_data).decode('utf-8')
    
    # Detect MIME type
    mime_type = mimetypes.guess_type(args.audio)[0] or "audio/mpeg"
    format_type = mime_type.split('/')[-1]
    if format_type == 'mpeg':
        format_type = 'mp3'
    
    # Allow format override via --format
    if args.format:
        format_type = args.format
    
    # Validate file header matches detected format
    MAGIC_SIGNATURES = {
        'wav': [b'RIFF'],
        'mp3': [b'ID3', b'\xff\xfb', b'\xff\xf3', b'\xff\xf2'],
        'ogg': [b'OggS'],
        'flac': [b'fLaC'],
        'pcm': [],  # PCM has no standard magic bytes
        'm4a': [b'\x00\x00\x00\x20ftypM4A', b'\x00\x00\x00\x18ftyp'],
    }

    try:
        fd = os.open(args.audio, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as e:
        print(f"Error: Could not open audio file '{args.audio}': {e}", file=sys.stderr)
        sys.exit(EXIT_FILE_ERROR)
    try:
        with os.fdopen(fd, "rb") as f:
            header = f.read(16)
    except OSError as e:
        print(f"Error: Could not read audio file '{args.audio}': {e}", file=sys.stderr)
        sys.exit(EXIT_FILE_ERROR)

    if format_type in MAGIC_SIGNATURES:
        valid_magics = MAGIC_SIGNATURES[format_type]
        if valid_magics and not any(header.startswith(m) for m in valid_magics):
            print(f"Warning: File header does not match {format_type} format. Proceeding anyway.", file=sys.stderr)
    
    # Build format object: for container formats (wav/mp3/ogg), only send `type`
    # since rate/bits/channel are optional and may confuse the API.
    if format_type in ("wav", "mp3", "ogg"):
        fmt = {"type": format_type}
    else:
        fmt = {
            "type": format_type,
            "rate": 16000,
            "bits": 16,
            "channel": 1
        }

    # Build request body
    body = {
        "audio": {
            "data": audio_base64,
            "input": {
                "transcription": {
                    "model": "stepaudio-2.5-asr",
                    "language": args.language,
                    "enable_itn": True
                },
                "format": fmt
            }
        }
    }

    # Add optional hotwords as array
    if args.hotwords_list:
        for word in args.hotwords_list:
            if not re.match(r'^[a-zA-Z0-9\s\-]{1,50}$', word):
                print(f"Error: hotword '{word}' contains invalid characters (only alphanumeric, spaces, hyphens allowed)", file=sys.stderr)
                sys.exit(EXIT_INPUT_ERROR)
        body["audio"]["input"]["transcription"]["hotwords"] = args.hotwords_list

    prompt = getattr(args, 'prompt', None)
    if isinstance(prompt, str) and prompt:
        body["audio"]["input"]["transcription"]["prompt"] = prompt

    url = f"{API_URL}/audio/asr/sse"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream"
    }

    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")

    try:
        full_text = ""
        final_usage = None
        done_text = None
        
        with _urlopen_with_retry(req, timeout=HTTP_TIMEOUT) as response:
            buffer = b""
            max_empty_reads = 3
            empty_reads = 0
            start_time = time.time()

            while True:
                if time.time() - start_time > SSE_READ_TIMEOUT:
                    print(f"Error: SSE stream timed out after {SSE_READ_TIMEOUT} seconds", file=sys.stderr)
                    sys.exit(EXIT_NETWORK_ERROR)

                chunk = response.read(1024)
                if not chunk:
                    empty_reads += 1
                    if empty_reads >= max_empty_reads:
                        break
                    continue

                empty_reads = 0
                buffer += chunk

                if len(buffer) > MAX_SSE_BUFFER:
                    print(f"Error: SSE buffer exceeded {MAX_SSE_BUFFER} bytes - possible runaway stream", file=sys.stderr)
                    sys.exit(EXIT_NETWORK_ERROR)

                while b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1)
                    line = line.decode('utf-8', errors='replace').strip()

                    if not line or not line.startswith('data:'):
                        continue

                    data_str = line[5:].strip()
                    if data_str == '[DONE]':
                        break

                    try:
                        event = json.loads(data_str)
                        event_type = event.get('type', '')

                        if event_type == 'transcript.text.delta':
                            delta = event.get('delta', '')
                            full_text += delta
                            if len(full_text) > 1_000_000:
                                print("Error: Transcript text exceeded 1 MB limit", file=sys.stderr)
                                sys.exit(EXIT_API_ERROR)
                        elif event_type == 'transcript.text.done':
                            done_text = event.get('text', '')
                            final_usage = event.get('usage')
                            # done event is authoritative; if it's empty use accumulated deltas
                            if done_text.strip():
                                full_text = done_text
                    except json.JSONDecodeError:
                        continue
        
        if not full_text:
            # Try parsing buffer as a JSON error response
            if len(buffer) > 0 and b'data:' not in buffer:
                try:
                    error_data = json.loads(buffer.decode('utf-8', errors='replace'))
                    error_msg = error_data.get('error', error_data.get('message', str(error_data)))
                    print(f"Error: API returned error: {error_msg}", file=sys.stderr)
                    sys.exit(EXIT_API_ERROR)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass
            print("Error: No transcript received from ASR service", file=sys.stderr)
            print(f"Debug: buffer size={len(buffer)}, empty_reads={empty_reads}", file=sys.stderr)
            if buffer:
                print(f"Debug: remaining buffer: {buffer[:200]}", file=sys.stderr)
            else:
                print("Debug: SSE stream returned zero data - endpoint may not support this audio format", file=sys.stderr)
            sys.exit(EXIT_API_ERROR)
        
        # Save transcript to file atomically
        output_path = get_output_path()
        transcript_bytes = full_text.encode('utf-8')
        
        if not check_disk_space(output_path, len(transcript_bytes) + 10 * 1024 * 1024):
            print("Error: Insufficient disk space for output file.", file=sys.stderr)
            sys.exit(EXIT_FILE_ERROR)
        
        tmp_path = output_path + ".tmp"
        try:
            with os.fdopen(os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w', encoding="utf-8") as f:
                f.write(full_text)
            os.replace(tmp_path, output_path)
        except FileExistsError:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            print(f"Error: Temporary file '{tmp_path}' already exists (possible symlink attack).", file=sys.stderr)
            sys.exit(EXIT_FILE_ERROR)
        except OSError as e:
            # Attempt cleanup of partial temp file
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            print(f"Error: Could not write transcript file: {e}", file=sys.stderr)
            sys.exit(EXIT_FILE_ERROR)
        
        print(f"Transcript: {output_path}")
        if args.print_transcript:
            print(full_text, file=sys.stdout)
        elif args.verbose:
            print(full_text, file=sys.stderr)
        
        if args.verbose and final_usage:
            print(f"Usage: {final_usage}", file=sys.stderr)
        
        return output_path, full_text
        
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        if len(error_body) > 200:
            error_msg = error_body[:200] + "... (truncated)"
        else:
            error_msg = error_body
        print(f"ASR API Error ({e.code}): {error_msg}", file=sys.stderr)
        sys.exit(EXIT_API_ERROR)
    except urllib.error.URLError as e:
        print(f"ASR API Error: {e.reason}", file=sys.stderr)
        sys.exit(EXIT_NETWORK_ERROR)


def main():
    parser = argparse.ArgumentParser(description="StepFun ASR Client")
    parser.add_argument("--audio", required=True, help="Audio file path (mp3, wav, etc.)")
    parser.add_argument("--language", default="en", help="Language code (default: en, supported: en/zh)")
    parser.add_argument("--verbose", action="store_true", help="Print usage metadata to stderr")
    parser.add_argument("--format", default=None, help="Audio format override (mp3, wav, etc.)")
    parser.add_argument("--hotwords", default=None, help="Comma-separated hotwords to boost recognition (e.g., 'AI,zeroclaw,API')")
    parser.add_argument("--print-transcript", action="store_true", help="Print transcript text to stdout (default: metadata only to stderr)")
    parser.add_argument("--prompt", default=None, help="Context prompt for pro model")

    args = parser.parse_args()

    # Parse hotwords string into a list
    args.hotwords_list = (
        [w.strip() for w in args.hotwords.split(",") if w.strip()]
        if args.hotwords
        else None
    )

    transcribe_audio(args)


if __name__ == "__main__":
    main()
