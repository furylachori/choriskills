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
import sys
import urllib.request
import urllib.error
from datetime import datetime


API_URL = "https://api.stepfun.ai/step_plan/v1"
API_KEY = os.environ.get("STEP_FUN_API_KEY", "")


def get_output_dir():
    """Get OUTPUT_DIR from environment or use default."""
    return os.environ.get("OUTPUT_DIR", os.path.expanduser("~/.zeroclaw/workspace/output"))


def get_output_path(voice=None, extension="mp3"):
    """Generate a default output path in OUTPUT_DIR."""
    output_dir = get_output_dir()
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    voice_slug = voice.replace("-", "_") if voice else "default"
    filename = f"tts_{voice_slug}_{timestamp}.{extension}"
    return os.path.join(output_dir, filename)


def text_to_speech(args):
    """Convert text to speech using StepFun TTS."""
    api_key = os.environ.get("STEP_FUN_API_KEY", "")
    if not api_key:
        print("Error: STEP_FUN_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    if not args.text or len(args.text) < 1 or len(args.text) > 1000:
        print(f"Error: Text must be 1-1000 characters (got {len(args.text) if args.text else 0}).", file=sys.stderr)
        sys.exit(1)

    output_path = get_output_path(args.voice)
    
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
        with urllib.request.urlopen(req) as response:
            content_type = response.headers.get('content-type', '')
            
            if 'application/json' in content_type:
                # Response is JSON (shouldn't happen with return_url=false, but handle it)
                result = json.loads(response.read().decode())
                if 'url' in result:
                    # Download from URL
                    urllib.request.urlretrieve(result['url'], output_path)
                else:
                    print(f"Error: Unexpected JSON response: {result}", file=sys.stderr)
                    sys.exit(1)
            else:
                # Response is raw audio
                audio_data = response.read()
                with open(output_path, "wb") as f:
                    f.write(audio_data)
            
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
