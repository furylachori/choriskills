#!/usr/bin/env python3
"""
StepFun Automatic Speech Recognition (ASR) API Client

Transcribe audio to text using StepFun's stepaudio-2.5-asr model.

Usage:
    python stepfun_asr.py --audio recording.mp3
    python stepfun_asr.py --audio recording.wav --language en

Environment:
    STEP_FUN_API_KEY - Required. Your StepFun API key.
    OUTPUT_DIR - Optional. Output directory for transcript (default: $HOME/.zeroclaw/workspace/output)
"""

import argparse
import base64
import json
import mimetypes
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime


API_URL = os.environ.get("STEPFUN_API_BASE", "https://api.stepfun.ai/step_plan/v1")
API_KEY = os.environ.get("STEP_FUN_API_KEY", "")


def get_output_dir():
    """Get OUTPUT_DIR from environment or use default."""
    return os.environ.get("OUTPUT_DIR", os.path.expanduser("~/.zeroclaw/workspace/output"))


def get_output_path(extension="txt"):
    """Generate a default output path in OUTPUT_DIR."""
    output_dir = get_output_dir()
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"asr_transcript_{timestamp}.{extension}"
    return os.path.join(output_dir, filename)


def transcribe_audio(args):
    """Transcribe audio using StepFun ASR."""
    api_key = os.environ.get("STEP_FUN_API_KEY", "")
    if not api_key:
        print("Error: STEP_FUN_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(args.audio):
        print(f"Error: Audio file '{args.audio}' does not exist.", file=sys.stderr)
        sys.exit(1)

    # Read audio file and encode to base64
    with open(args.audio, "rb") as f:
        audio_data = f.read()
    
    audio_base64 = base64.b64encode(audio_data).decode('utf-8')
    
    # Detect MIME type
    mime_type = mimetypes.guess_type(args.audio)[0] or "audio/mpeg"
    format_type = mime_type.split('/')[-1]
    if format_type == 'mpeg':
        format_type = 'mp3'
    
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
                "format": {
                    "type": format_type,
                    "rate": 16000,
                    "bits": 16,
                    "channel": 1
                }
            }
        }
    }

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
        
        with urllib.request.urlopen(req) as response:
            # Read SSE stream
            buffer = b""
            max_empty_reads = 3
            empty_reads = 0
            
            while True:
                chunk = response.read(1024)
                if not chunk:
                    empty_reads += 1
                    if empty_reads >= max_empty_reads:
                        break
                    continue
                
                empty_reads = 0
                buffer += chunk
                
                # Process complete lines
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
                        elif event_type == 'transcript.text.done':
                            full_text = event.get('text', full_text)
                            final_usage = event.get('usage')
                        elif event_type == 'error':
                            error_msg = event.get('message', 'Unknown ASR error')
                            print(f"ASR Error: {error_msg}", file=sys.stderr)
                            sys.exit(1)
                    except json.JSONDecodeError:
                        continue
        
        if not full_text:
            print("Error: No transcript received from ASR service", file=sys.stderr)
            print(f"Debug: buffer size={len(buffer)}, empty_reads={empty_reads}", file=sys.stderr)
            if buffer:
                print(f"Debug: remaining buffer: {buffer[:200]}", file=sys.stderr)
            else:
                print("Debug: SSE stream returned zero data - endpoint may not support this audio format", file=sys.stderr)
            sys.exit(1)
        
        # Save transcript to file
        output_path = get_output_path()
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(full_text)
        
        print(f"Transcript: {output_path}")
        print(full_text)
        
        if args.verbose and final_usage:
            print(f"Usage: {final_usage}", file=sys.stderr)
        
        return output_path, full_text
        
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        try:
            error_data = json.loads(error_body)
            error_msg = error_data.get('error', error_body)
        except json.JSONDecodeError:
            error_msg = error_body
        print(f"ASR API Error ({e.code}): {error_msg}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="StepFun ASR Client")
    parser.add_argument("--audio", required=True, help="Audio file path (mp3, wav, etc.)")
    parser.add_argument("--language", default="en", help="Language code (default: en, supported: en/zh)")
    parser.add_argument("--verbose", action="store_true", help="Print usage metadata to stderr")
    parser.add_argument("--format", default=None, help="Audio format (mp3, wav, etc.) - auto-detected if not specified")

    args = parser.parse_args()

    transcribe_audio(args)


if __name__ == "__main__":
    main()
