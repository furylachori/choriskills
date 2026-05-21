#!/usr/bin/env python3
"""
StepFun Text-to-Speech API Client

Convert text to speech using StepFun's stepaudio-2.5-tts model.

Usage:
    python stepfun_tts.py --text "Hello, this is a test" --voice lively-girl
    python stepfun_tts.py --text "Sing this song" --voice cixingnansheng --instruction "happy, upbeat"

Environment:
    STEP_FUN_API_KEY - Required. Your StepFun API key.
    OUTPUT_DIR - Optional. Output directory (default: $HOME/.zeroclaw/workspace/output)
"""

import argparse
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
MAX_RESPONSE_SIZE = 50 * 1024 * 1024  # 50 MB
HTTP_TIMEOUT = 60

API_URL = "https://api.stepfun.ai/step_plan/v1"
API_KEY = os.environ.get("STEP_FUN_API_KEY", "")


def get_output_dir():
    """Get OUTPUT_DIR from environment or use default."""
    return os.environ.get("OUTPUT_DIR", os.path.expanduser("~/.zeroclaw/workspace/output"))


def get_output_path(voice=None, extension="mp3"):
    """Generate a default output path in OUTPUT_DIR."""
    voice = sanitize_voice(voice) if voice else "default"
    output_dir = get_output_dir()
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    voice_slug = voice.replace("-", "_") if voice else "default"
    filename = f"tts_{voice_slug}_{timestamp}.{extension}"
    return os.path.join(output_dir, filename)


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
        sys.exit(1)
    if parsed.hostname not in ALLOWED_HOSTS:
        print(f"Error: URL hostname '{parsed.hostname}' is not allowed.", file=sys.stderr)
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


def text_to_speech(args):
    """Convert text to speech using StepFun TTS."""
    api_key = os.environ.get("STEP_FUN_API_KEY", "")
    if not api_key:
        print("Error: STEP_FUN_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    if not args.text or len(args.text) < 1 or len(args.text) > 1000:
        print(f"Error: Text must be 1-1000 characters (got {len(args.text) if args.text else 0}).", file=sys.stderr)
        sys.exit(1)

    output_path = get_output_path(args.voice, args.format)
    
    data = {
        "model": "stepaudio-2.5-tts",
        "input": args.text,
        "voice": args.voice,
        "response_format": args.format,
        "return_url": False
    }
    
    if args.instruction:
        data["instruction"] = args.instruction

    url = f"{API_URL}/audio/speech"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as response:
            content_type = response.headers.get('content-type', '')
            
            if 'application/json' in content_type:
                result = json.loads(response.read().decode())
                if 'url' in result:
                    download_url(result['url'], output_path)
                else:
                    print(f"Error: Unexpected JSON response: {result}", file=sys.stderr)
                    sys.exit(1)
            else:
                audio_data = response.read()
                
                if len(audio_data) > MAX_RESPONSE_SIZE:
                    print(f"Error: Audio data too large ({len(audio_data)} bytes > {MAX_RESPONSE_SIZE})", file=sys.stderr)
                    sys.exit(1)
                
                tmp_path = output_path + ".tmp"
                with open(tmp_path, "wb") as f:
                    f.write(audio_data)
                os.replace(tmp_path, output_path)
            
            print(f"Audio generated: {output_path}")
            if args.verbose:
                if 'voice' in data:
                    print(f"Voice: {data['voice']}", file=sys.stderr)
                if data.get('instruction'):
                    print(f"Instruction: {data['instruction']}", file=sys.stderr)
            return output_path
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        try:
            error_data = json.loads(error_body)
            error_msg = error_data.get('error', error_body)
        except json.JSONDecodeError:
            error_msg = error_body
        print(f"TTS API Error ({e.code}): {error_msg}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"TTS API Error: {e.reason}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="StepFun Text-to-Speech Client")
    parser.add_argument("--text", required=True, help="Text to speak (1-1000 characters)")
    parser.add_argument("--voice", default="lively-girl", help="Voice ID (default: lively-girl)")
    parser.add_argument("--format", default="mp3", choices=["mp3", "wav", "flac", "opus", "pcm"], help="Audio format")
    parser.add_argument("--instruction", default=None, help="Emotion/style instruction (e.g., 'happy, upbeat')")
    parser.add_argument("--verbose", action="store_true", help="Print metadata to stderr")

    args = parser.parse_args()

    text_to_speech(args)


if __name__ == "__main__":
    main()
