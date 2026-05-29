---
name: stepfun-tts
description: Convert text to speech using StepFun's TTS API. Use when the user asks to generate voice, synthesize speech, create audio from text, or produce spoken audio.
---

# StepFun Text-to-Speech

Convert text to speech using StepFun's `stepaudio-2.5-tts` model with 40+ voice options.

## When to Use

Use this skill when the user requests to:
- Generate speech from text
- Create voiceovers or narration
- Synthesize vocals with specific voice characteristics
- Produce audio with emotion/style control

## How to Use

```bash
python3 $HOME/.zeroclaw/workspace/skills/stepfun-tts/stepfun_tts.py --text "Hello, this is a test" --voice lively-girl
```

### Choosing a voice

Common voices:
- `lively-girl` — energetic, upbeat
- `cixingnansheng` — deep, confident male
- `wenrounansheng` — soft-spoken male
- `elegantgentle-female` — polished, refined female
- `shenchennanyin` — deep, resonant male

Full list in `STEPFUN_VOICES` constant.

### Controlling emotion

Use `--instruction` to guide the delivery style:

```bash
python3 $HOME/.zeroclaw/workspace/skills/stepfun-tts/stepfun_tts.py --text "Welcome to Desampa" --voice elegantgentle-female --instruction "warm and welcoming"
```

## All Parameters

| Parameter | Default | Range/Choices | Description |
|---|---|---|---|
| `--text` | (required) | 1–1000 chars | Text to speak |
| `--voice` | `lively-girl` | 40+ voice IDs | Voice to use |
| `--format` | `mp3` | mp3, wav, flac, opus, pcm | Output audio format |
| `--instruction` | none | free text | Emotion/style guidance |
| `--speed` | `1.0` | 0.5–2.0 | Playback speed multiplier |
| `--volume` | `1.0` | 0.0–2.0 | Volume gain |
| `--sample-rate` | `24000` | positive int | Output sample rate in Hz |
| `--return-url` | false | flag | Return signed URL instead of binary audio |
| `--stream-format` | `audio` | audio, sse | Stream chunk format |
| `--voice-label` | none | free text | Pronunciation guidance label |
| `--pronunciation-map` | none | JSON string | Phonetic overrides |
| `--markdown-filter` | false | flag | Strip markdown syntax before synthesis |
| `--verbose` | false | flag | Print metadata to stderr |

## Supported Models

| Skill | Model | Notes |
|---|---|---|
| stepfun-tts | `stepaudio-2.5-tts` | 40+ voices available |

## What You'll See

### Output Format

The script prints a status message to **stdout**:
```
Audio generated: /Users/dastua/.zeroclaw/workspace/output/tts_lively_girl_20250621_123456.mp3
```
Extract the file path from the last whitespace-delimited token or after the colon.

Saved automatically to `$OUTPUT_DIR` as MP3.

## Environment Setup

Before running, set the required environment variable:

```bash
export STEPFUN_API_KEY="your-api-key-here"
```

Or create a `.env` file in the skill directory:
```
STEPFUN_API_KEY=your-api-key-here
```

## Troubleshooting

- **"Text must be 1–1000 characters"** — shorten or split your text
- **"API key not set"** — add `STEPFUN_API_KEY` to your environment
- **"Speed must be between 0.5 and 2.0"** — check `--speed` value
- **"Volume must be between 0.0 and 2.0"** — check `--volume` value
- **"pronunciation-map must be a valid JSON string"** — verify JSON syntax

## Technical Reference

Full API parameters, response formats, and error codes are in `TECHNICAL_REFERENCE.md` at the repository root.
