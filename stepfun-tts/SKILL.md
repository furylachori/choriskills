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

Full list in `STEPFUN_VOICES` constant.

### Controlling emotion

Use `--instruction` to guide the delivery style:

```bash
python stepfun_tts.py --text "Welcome to Desampa" --voice elegantgentle-female --instruction "warm and welcoming"
```

### Optional tweaks

- `--format mp3` — audio format (mp3, wav, flac, opus, pcm)
- `--instruction "happy, upbeat"` — emotion/style

## What You'll See

```
Audio generated: /Users/dastua/.zeroclaw/workspace/output/tts_lively_girl_20250621_123456.mp3
```

Saved automatically to `$OUTPUT_DIR` as MP3.

## Troubleshooting

- **"Text must be 1–1000 characters"** — shorten or split your text
- **"API key not set"** — add `STEP_FUN_API_KEY` to your environment

## Technical Reference

Full API parameters and response formats: [TECHNICAL_REFERENCE.md](../TECHNICAL_REFERENCE.md)
