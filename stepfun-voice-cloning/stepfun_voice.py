#!/usr/bin/env python3
"""
StepFun Voice Cloning API Client

Clone a voice from a reference audio file (5-10 seconds) and use it for TTS.
Also supports previewing a cloned voice before committing to it.

Usage:
    # Upload a reference audio file
    python stepfun_voice.py upload --audio reference.wav

    # Clone a voice from an uploaded file
    python stepfun_voice.py clone --file-id file-abc123 --model step-tts-2

    # Preview a cloned voice (no permanent asset created)
    python stepfun_voice.py preview --file-id file-abc123 --text "Hello world"

    # Full workflow: clone and preview in one step
    python stepfun_voice.py clone --audio reference.wav --sample-text "Hello world"

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
import uuid
from datetime import datetime


ALLOWED_SCHEMES = {"https"}
ALLOWED_HOSTS = {"api.stepfun.ai"}
ALLOWED_HOST_SUFFIXES = {".aliyuncs.com"}
MAX_RESPONSE_SIZE = 50 * 1024 * 1024  # 50 MB
HTTP_TIMEOUT = 60

API_URL = os.environ.get("STEPFUN_API_BASE", "https://api.stepfun.ai/step_plan/v1")
FILES_API_URL = "https://api.stepfun.ai/v1"
API_KEY = os.environ.get("STEP_FUN_API_KEY", "")


def get_output_dir():
    """Get OUTPUT_DIR from environment or use default."""
    return os.environ.get("OUTPUT_DIR", os.path.expanduser("~/.zeroclaw/workspace/output"))


def get_output_path(prefix, extension="bin"):
    """Generate a default output path in OUTPUT_DIR."""
    output_dir = get_output_dir()
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_uuid = uuid.uuid4().hex[:8]
    filename = f"{prefix}_{short_uuid}_{timestamp}.{extension}"
    return os.path.join(output_dir, filename)


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
    normalized = input_path.replace('\\', '/')
    parts = normalized.split('/')
    if '..' in parts:
        print(f"Error: Input path contains '..' which is not allowed.", file=sys.stderr)
        sys.exit(1)


def validate_audio_file(path):
    """Validate audio file exists, is a supported format, and has reasonable size."""
    if not os.path.exists(path):
        print(f"Error: Audio file '{path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    validate_input_path(path)

    file_size = os.path.getsize(path)
    if file_size > MAX_RESPONSE_SIZE:
        print(f"Error: Audio file too large ({file_size} bytes > {MAX_RESPONSE_SIZE})", file=sys.stderr)
        sys.exit(1)

    # StepFun API constraint: only WAV and MP3 are supported for voice cloning uploads
    # See: https://platform.stepfun.ai/docs/en/api-reference/audio/create-voice
    # See: https://platform.stepfun.ai/docs/en/api-reference/files/create
    ext = os.path.splitext(path)[1].lower()
    if ext not in ('.wav', '.mp3', '.mpeg'):
        print(f"Error: Unsupported audio format '{ext}'. The StepFun API only accepts .wav and .mp3 for voice cloning. OGG, FLAC, M4A, and other formats are not supported.", file=sys.stderr)
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
    api_key = os.environ.get("STEP_FUN_API_KEY", "")
    if not api_key:
        print("Error: STEP_FUN_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    base_url = FILES_API_URL if endpoint == "files" else API_URL
    url = f"{base_url}/{endpoint}"
    headers = {"Authorization": f"Bearer {api_key}"}

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
            mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
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


def upload_audio_file(args):
    """Upload a reference audio file to StepFun file storage."""
    validate_audio_file(args.audio)

    print(f"Uploading audio file: {args.audio}")

    response = call_api("files", data={"purpose": "storage"}, files={"file": args.audio})

    if "id" not in response:
        print(f"Error: Unexpected response: {response}", file=sys.stderr)
        sys.exit(1)

    file_id = response["id"]
    print(f"File uploaded: {file_id}")
    print(f"Filename: {response.get('filename', 'unknown')}")
    print(f"Size: {response.get('bytes', 0)} bytes")
    if args.verbose:
        print(f"Full response: {json.dumps(response, indent=2)}", file=sys.stderr)

    return file_id


def clone_voice(args):
    """Clone a voice from a reference audio file."""
    if args.audio:
        # Upload first if audio file provided
        validate_audio_file(args.audio)
        print(f"Uploading reference audio: {args.audio}")
        upload_response = call_api("files", data={"purpose": "storage"}, files={"file": args.audio})
        file_id = upload_response["id"]
        print(f"Uploaded as: {file_id}")
    elif args.file_id:
        file_id = args.file_id
    else:
        print("Error: Either --audio or --file-id is required.", file=sys.stderr)
        sys.exit(1)

    data = {
        "model": args.model,
        "file_id": file_id,
    }

    if args.text:
        data["text"] = args.text

    if args.sample_text:
        data["sample_text"] = args.sample_text

    print(f"Cloning voice with model: {args.model}")

    response = call_api("audio/voices", data=data)

    if "id" not in response:
        print(f"Error: Unexpected response: {response}", file=sys.stderr)
        sys.exit(1)

    voice_id = response["id"]
    print(f"Voice cloned: {voice_id}")
    print(f"Model: {args.model}")
    print(f"Duplicated: {response.get('duplicated', False)}")

    if args.verbose:
        print(f"Full response: {json.dumps(response, indent=2)}", file=sys.stderr)

    return voice_id


def preview_voice(args):
    """Preview a cloned voice using a reference audio file."""
    if not args.file_id:
        print("Error: --file-id is required for preview.", file=sys.stderr)
        sys.exit(1)

    if not args.text:
        print("Error: --text is required for preview (text to synthesize).", file=sys.stderr)
        sys.exit(1)

    data = {
        "file_id": args.file_id,
        "model": args.model,
        "sample_text": args.text,
        "response_format": "wav",
    }

    if args.transcript:
        data["text"] = args.transcript

    if args.instruction:
        data["instruction"] = args.instruction

    if args.speed:
        data["speed"] = args.speed

    if args.volume:
        data["volume"] = args.volume

    print(f"Generating preview with model: {args.model}")

    response = call_api("audio/voices/preview", data=data)

    if "sample_audio" not in response:
        print(f"Error: No audio in preview response: {response}", file=sys.stderr)
        sys.exit(1)

    # Decode base64 audio
    audio_b64 = response["sample_audio"]
    audio_bytes = base64.b64decode(audio_b64)

    if len(audio_bytes) > MAX_RESPONSE_SIZE:
        print(f"Error: Preview audio too large ({len(audio_bytes)} bytes)", file=sys.stderr)
        sys.exit(1)

    output_path = get_output_path("voice_preview", "wav")
    tmp_path = output_path + ".tmp"
    with open(tmp_path, "wb") as f:
        f.write(audio_bytes)
    os.replace(tmp_path, output_path)

    print(f"Preview audio: {output_path}")
    print(f"Request ID: {response.get('request_id', 'N/A')}")
    if args.verbose:
        print(f"Full response: {json.dumps(response, indent=2)}", file=sys.stderr)

    return output_path


def main():
    parser = argparse.ArgumentParser(description="StepFun Voice Cloning API Client")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Upload subcommand
    upload_parser = subparsers.add_parser("upload", help="Upload a reference audio file")
    upload_parser.add_argument("--audio", required=True, help="Reference audio file path (WAV or MP3, 5-10 seconds recommended)")
    upload_parser.add_argument("--verbose", action="store_true", help="Print full API response to stderr")

    # Clone subcommand
    clone_parser = subparsers.add_parser("clone", help="Clone a voice from a reference audio file")
    clone_parser.add_argument("--audio", help="Reference audio file path (uploaded automatically)")
    clone_parser.add_argument("--file-id", help="Previously uploaded file ID (e.g. file-abc123)")
    clone_parser.add_argument("--model", default="step-tts-2", choices=["step-tts-2", "step-tts-mini"], help="Cloning model (requires Step Plan access to step-tts-2/step-tts-mini)")
    clone_parser.add_argument("--text", help="Transcript of the reference audio (improves cloning quality)")
    clone_parser.add_argument("--sample-text", help="Text for preview clip (max 50 characters)")
    clone_parser.add_argument("--verbose", action="store_true", help="Print full API response to stderr")

    # Preview subcommand
    preview_parser = subparsers.add_parser("preview", help="Preview a cloned voice (no permanent asset created)")
    preview_parser.add_argument("--file-id", required=True, help="Uploaded reference audio file ID")
    preview_parser.add_argument("--text", required=True, help="Text to synthesize for preview (max 50 chars recommended)")
    preview_parser.add_argument("--model", default="stepaudio-2.5-tts", choices=["step-tts-2", "step-tts-mini", "stepaudio-2.5-tts"], help="Model for preview (stepaudio-2.5-tts works without paid clone access)")
    preview_parser.add_argument("--transcript", help="Transcript of the reference audio")
    preview_parser.add_argument("--instruction", help="Emotion/style instruction (stepaudio-2.5-tts only)")
    preview_parser.add_argument("--speed", type=float, help="Speaking rate (0.5-2.0)")
    preview_parser.add_argument("--volume", type=float, help="Volume level (0.1-2.0)")
    preview_parser.add_argument("--verbose", action="store_true", help="Print full API response to stderr")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "upload":
        upload_audio_file(args)
    elif args.command == "clone":
        clone_voice(args)
    elif args.command == "preview":
        preview_voice(args)


if __name__ == "__main__":
    main()
