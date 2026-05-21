# StepFun API Technical Reference

This document contains the full API details for agent implementation and debugging.

## Endpoints

All endpoints use `https://api.stepfun.ai/step_plan/v1` (plan credits).

| Feature | Endpoint | Method | Auth |
|---|---|---|---|
| Image Generate | `/images/generations` | POST | Bearer |
| Image Edit | `/images/edits` | POST (multipart) | Bearer |
| Text-to-Speech | `/audio/speech` | POST | Bearer |
| Speech-to-Text | `/audio/asr/sse` | POST (SSE) | Bearer |

## Image Generation

**Request:**
```json
{
  "model": "step-image-edit-2",
  "prompt": "string, 1-512 chars",
  "response_format": "b64_json",
  "cfg_scale": 1.0,
  "steps": 8,
  "seed": 42,
  "text_mode": true,
  "negative_prompt": "string",
  "size": "1024x1024"
}
```

**Response (b64_json):**
```json
{
  "data": [{
    "b64_json": "base64-encoded PNG",
    "seed": 42
  }]
}
```

**Sizes:** `1024x1024`, `768x1360`, `896x1184`, `1360x768`, `1184x896`

## Image Edit

**Request** (multipart/form-data):
- `model` = `step-image-edit-2`
- `image` = file (PNG/JPEG)
- `prompt` = string, 1-512 chars
- `size`, `steps`, `cfg_scale`, `text_mode`, `seed`, `negative_prompt` (same as generation)

**Response:**
```json
{
  "data": [{
    "url": "https://...",
    "seed": 42
  }]
}
```

Note: Edit endpoint only returns `url`, not `b64_json`. Download from URL.

## Text-to-Speech (TTS)

**Request:**
```json
{
  "model": "stepaudio-2.5-tts",
  "input": "text, 1-1000 chars",
  "voice": "lively-girl",
  "response_format": "mp3",
  "instruction": "emotion/style",
  "return_url": false
}
```

**Response:** Raw audio binary (or JSON with `url` if `return_url=true`).

**Voices:** See `STEPFUN_VOICES` in `providers.js` — 40+ options organized by category (Audiobook, Customer Service, Emotional, etc.).

**Formats:** `mp3`, `wav`, `flac`, `opus`, `pcm`

## Automatic Speech Recognition (ASR)

**Request:**
```json
{
  "audio": {
    "data": "base64-encoded audio",
    "input": {
      "transcription": {
        "model": "stepaudio-2.5-asr",
        "language": "en",
        "enable_itn": true
      },
      "format": {
        "type": "mp3",
        "rate": 16000,
        "bits": 16,
        "channel": 1
      }
    }
  }
}
```

**Response:** SSE stream with events:
- `transcript.text.delta` — incremental text
- `transcript.text.done` — final text + usage
- `error` — error message

**Languages:** English (`en`), Chinese (`zh`)

**Formats:** MP3, WAV, OGG, PCM, FLAC (auto-detected; PCM requires `rate`/`bits`/`channel`)

## Script Conventions

All scripts in this repo follow these rules:

- **Python stdlib only** — no `pip install` needed
- **Auto-output** — files go to `$OUTPUT_DIR` (default: `~/.zeroclaw/workspace/output`)
- **No filename arguments** — agents don't choose output names
- **Print path to stdout** — agent reads it to know where the file is
- **Validate early** — clear errors before making API calls
- **`--verbose` flag** — metadata goes to stderr, clean stdout for agents

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `STEP_FUN_API_KEY` | Yes | — | StepFun API key |
| `OUTPUT_DIR` | No | `~/.zeroclaw/workspace/output` | Output directory |
| `STEPFUN_API_BASE` | No | `https://api.stepfun.ai/step_plan/v1` | Override API base URL |

## Error Handling

Scripts exit with code 1 and print to stderr:
- Missing/invalid API key
- Prompt/text too short/long
- Missing input files
- HTTP errors (401, 400, 500)
- Empty API responses

## Testing

```bash
# All unit tests
pytest tests/ -v

# Specific module
pytest tests/test_stepfun_image.py -v
pytest tests/test_stepfun_tts.py -v
pytest tests/test_stepfun_asr.py -v
```
