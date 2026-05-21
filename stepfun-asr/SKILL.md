---
name: stepfun-asr
description: Transcribe audio to text using StepFun's ASR API. Use when the user asks to transcribe, convert speech to text, or extract text from audio.
---

# StepFun Automatic Speech Recognition

Transcribe audio files to text using StepFun's `stepaudio-2.5-asr` model.

## When to Use

Use this skill when the user requests to:
- Transcribe audio files to text
- Convert speech to written text
- Extract lyrics or dialogue from recordings
- Process voice notes or interviews

## How to Use

```bash
python stepfun_asr.py --audio recording.mp3 --language en
```

### Language support

- `en` — English (default)
- `zh` — Chinese

### Supported audio formats

MP3, WAV, OGG, PCM, FLAC — auto-detected from file extension.

## What You'll See

```
Transcript: /Users/dastua/.zeroclaw/workspace/output/asr_transcript_20250621_123456.txt
This is the real end. We are going to make it now.
```

The transcript is saved as a text file and printed to the screen.

## Troubleshooting

- **"No transcript received"** — the audio may be too short, silent, or synthetic (TTS audio often fails)
- **"Audio file does not exist"** — check the `--audio` path
- **"API key not set"** — add `STEP_FUN_API_KEY` to your environment
- **"Unsupported language"** — use `en` or `zh`

## Technical Reference

Full API parameters and SSE event formats: [TECHNICAL_REFERENCE.md](../TECHNICAL_REFERENCE.md)
