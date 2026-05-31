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
python stepfun_tts.py --text "Hello, this is a test" --voice lively-girl
```

### Choosing a voice

Common voices:
- `lively-girl` — energetic, upbeat
- `cixingnansheng` — deep, confident male
- `wenrounansheng` — soft-spoken male
- `elegantgentle-female` — polished, refined female
- `shenchennanyin` — deep, resonant male

40+ voices available from StepFun's `stepaudio-2.5-tts` model.

### Controlling emotion

Use `--instruction` to guide the delivery style:

```bash
python stepfun_tts.py --text "Welcome to Desampa" --voice elegantgentle-female --instruction "warm and welcoming"
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
| `--voice-label` | none | free text | Pronunciation guidance label |
| `--pronunciation-map` | none | JSON string | Phonetic overrides |
| `--markdown-filter` | false | flag | Strip markdown syntax before synthesis |
| `--timeout` | `120` | positive int | HTTP timeout in seconds |
| `--verbose` | false | flag | Print metadata to stderr |

## Supported Models

| Skill | Model | Notes |
|---|---|---|
| stepfun-tts | `stepaudio-2.5-tts` | 40+ voices available |

## What You'll See

### Output Format

The script prints to **stdout**:
```
/path/to/output/tts_lively_girl_20250621_123456.mp3
Format: MP3
Size: 12345 bytes
```

Saved automatically to `$OUTPUT_DIR`. Format depends on `--format` (default: mp3).

Use `--verbose` to print voice and instruction to **stderr**.

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
- **"STEPFUN_API_KEY environment variable is not set"** — add `STEPFUN_API_KEY` to your environment
- **"Speed must be between 0.5 and 2.0"** — check `--speed` value
- **"Volume must be between 0.0 and 2.0"** — check `--volume` value
- **"--pronunciation-map: ..."** — verify your JSON syntax is valid

## Technical Reference

Full API parameters, response formats, and error codes are in `TECHNICAL_REFERENCE.md` at the repository root.
