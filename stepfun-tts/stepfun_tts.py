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
ALLOWED_HOST_SUFFIXES = {".aliyuncs.com"}  # Alibaba Cloud OSS (StepFun image/audio hosting)
MAX_RESPONSE_SIZE = 50 * 1024 * 1024  # 50 MB
HTTP_TIMEOUT = 60

API_URL = os.environ.get("STEPFUN_API_BASE", "https://api.stepfun.ai/step_plan/v1")
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
    hostname = parsed.hostname
    if not hostname:
        print(f"Error: URL has no hostname.", file=sys.stderr)
        sys.exit(1)
    if hostname not in ALLOWED_HOSTS and not any(hostname.endswith(suffix) for suffix in ALLOWED_HOST_SUFFIXES):
        print(f"Error: URL hostname '{hostname}' is not allowed.", file=sys.stderr)
        sys.exit(1)


def download_url(url, output_path):
    """Download a URL safely with SSRF protection, size limit, and atomic write."""
    validate_url_safe(url)
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "claw-skills/1.0"})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as response:
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
            except OSError as e:
                print(f"Error writing to temporary file '{tmp_path}': {e}", file=sys.stderr)
                sys.exit(1)

            try:
                os.replace(tmp_path, output_path)
            except OSError as e:
                print(f"Error moving temporary file to '{output_path}': {e}", file=sys.stderr)
                sys.exit(1)
    except urllib.error.HTTPError as e:
        print(f"Error downloading from URL: HTTP {e.code}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Error downloading from URL: {e.reason}", file=sys.stderr)
        sys.exit(1)


def filter_markdown(text):
    """Remove markdown formatting syntax from text."""
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


def text_to_speech(args):
    """Convert text to speech using StepFun TTS."""
    api_key = os.environ.get("STEP_FUN_API_KEY", "")
    if not api_key:
        print("Error: STEP_FUN_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    if not args.text or len(args.text) < 1 or len(args.text) > 1000:
        print(f"Error: Text must be 1-1000 characters (got {len(args.text) if args.text else 0}).", file=sys.stderr)
        sys.exit(1)

    # Validate ranges
    if args.speed < 0.5 or args.speed > 2.0:
        print(f"Error: Speed must be between 0.5 and 2.0 (got {args.speed}).", file=sys.stderr)
        sys.exit(1)

    if args.volume < 0.0 or args.volume > 2.0:
        print(f"Error: Volume must be between 0.0 and 2.0 (got {args.volume}).", file=sys.stderr)
        sys.exit(1)

    if args.sample_rate <= 0:
        print(f"Error: Sample rate must be a positive integer (got {args.sample_rate}).", file=sys.stderr)
        sys.exit(1)

    text = args.text
    if args.markdown_filter:
        text = filter_markdown(text)
        if not text or len(text) > 1000:
            print(f"Error: Filtered text must be 1-1000 characters.", file=sys.stderr)
            sys.exit(1)

    output_path = get_output_path(args.voice, args.format)

    data = {
        "model": "stepaudio-2.5-tts",
        "input": text,
        "voice": args.voice,
        "response_format": args.format,
        "return_url": args.return_url,
        "speed": args.speed,
        "volume": args.volume,
        "sample_rate": args.sample_rate,
        "stream_format": args.stream_format,
        "markdown_filter": args.markdown_filter
    }

    if args.instruction:
        data["instruction"] = args.instruction

    if args.voice_label:
        data["voice_label"] = args.voice_label

    if args.pronunciation_map:
        try:
            pronunciation_map = json.loads(args.pronunciation_map)
            data["pronunciation_map"] = pronunciation_map
        except json.JSONDecodeError:
            print(f"Error: --pronunciation-map must be a valid JSON string.", file=sys.stderr)
            sys.exit(1)

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
                try:
                    with open(tmp_path, "wb") as f:
                        f.write(audio_data)
                except OSError as e:
                    print(f"Error writing audio to temporary file '{tmp_path}': {e}", file=sys.stderr)
                    sys.exit(1)
                try:
                    os.replace(tmp_path, output_path)
                except OSError as e:
                    print(f"Error moving temporary file to '{output_path}': {e}", file=sys.stderr)
                    sys.exit(1)
            
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

    parser.add_argument("--return-url", action="store_true", default=False,
                        help="Request URL return instead of binary audio")
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
    parser.add_argument("--stream-format", default="pcm",
                        choices=["pcm", "mp3", "wav", "flac"],
                        help="Stream chunk format (default: pcm)")
    parser.add_argument("--markdown-filter", action="store_true", default=False,
                        help="Filter markdown syntax from input text")

    args = parser.parse_args()

    text_to_speech(args)


if __name__ == "__main__":
    main()
