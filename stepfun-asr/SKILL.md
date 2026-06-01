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

MP3, WAV, OGG, PCM, FLAC, M4A — auto-detected from file extension.

## All Parameters

| Parameter | Default | Range/Choices | Description |
|---|---|---|---|
| `--audio` | (required) | file path | Audio file to transcribe |
| `--language` | `en` | en, zh | Language code |
| `--format` | auto-detect | mp3, wav, ogg, pcm, flac, m4a | Audio format override |
| `--hotwords` | none | comma-separated | Words to boost in recognition (e.g., `AI,zeroclaw,API`) |
| `--print-transcript` | false | flag | Print transcript text to stdout |
| `--prompt` | none | string | Context prompt for ASR model |
| `--timeout` | `120` | positive int | HTTP timeout in seconds |
| `--verbose` | false | flag | Print file path and usage metadata to stderr |

## Supported Models

| Skill | Model | Notes |
|---|---|---|
| stepfun-asr | `stepaudio-2.5-asr` | Default model |

## What You'll See

### Output Format

By default, the transcript is saved to a file in `$OUTPUT_DIR` and the file path is printed to **stderr** with `--verbose`.

With `--print-transcript`, the transcript text is also printed to **stdout**:
```
This is the transcribed text from the audio file.
```

The transcript file path and usage metadata are printed to **stderr** with `--verbose`.

## Troubleshooting

- **"No transcript received"** — the audio may be too short, silent, or synthetic (TTS audio often fails)
- **"Audio file does not exist"** — check the `--audio` path
- **"API key not set"** — add `STEPFUN_API_KEY` to your environment

## Technical Reference

Full API parameters and SSE event formats are in `TECHNICAL_REFERENCE.md` at the repository root.
