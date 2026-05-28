# Technical Reference

This document contains the full API details for agent implementation and debugging.

## StepFun API

## Endpoint Base URLs

### StepFun

| Base URL | Purpose |
|---|---|
| `https://api.stepfun.ai/v1` | Open platform (budget credits, no billing plan required) |
| `https://api.stepfun.ai/step_plan/v1` | Step Plan billing (V0-V5 tiers) |

**Which to use:**
- Most audio endpoints (`audio/asr/sse`, `audio/speech`, etc.) use `step_plan/v1` for plan credits.
- The `files` endpoint uses `/v1` (open platform base), not `step_plan/v1`.
- For open platform access without a Step Plan, set `STEPFUN_API_BASE=https://api.stepfun.ai/v1`.

### Bailian (Alibaba Cloud)

| Base URL | Purpose |
|---|---|
| `https://token-plan.ap-southeast-1.maas.aliyuncs.com` | Token Plan billing (default) |

Override with `BAILIAN_TOKEN_PLAN_API_BASE`.

### MiniMax

| Base URL | Purpose |
|---|---|
| `https://api.minimax.io/v1` | Default video generation API |

Override with `MINIMAX_API_BASE`.

## Endpoints

### StepFun

| Feature | Endpoint | Method | Auth |
|---|---|---|---|
| Upload File | `/v1/files` | POST (multipart) | Bearer |
| Image Generate | `/images/generations` | POST | Bearer |
| Image Edit | `/images/edits` | POST (multipart) | Bearer |
| Text-to-Speech | `/audio/speech` | POST | Bearer |
| Speech-to-Text | `/audio/asr/sse` | POST (SSE) | Bearer |

### Bailian (Alibaba Cloud)

| Feature | Endpoint | Method | Auth |
|---|---|---|---|
| Image Generate | `/api/v1/services/aigc/multimodal-generation/generation` | POST | Bearer |

### MiniMax

| Feature | Endpoint | Method | Auth |
|---|---|---|---|
| Video Generate | `/video_generation` | POST | Bearer |
| Query Task | `/query/video_generation?task_id=<id>` | GET | Bearer |
| Get File | `/files/retrieve?file_id=<id>` | GET | Bearer |

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

> **Critical:** The `size` parameter in the edit request body is accepted by the API but **ignored** — the output image size cannot be controlled for edits.

## Text-to-Speech (TTS)

**Request:**
```json
{
  "model": "stepaudio-2.5-tts",
  "input": "text, 1-1000 chars",
  "voice": "lively-girl",
  "response_format": "mp3",
  "instruction": "emotion/style",
  "return_url": false,
  "speed": 1.0,
  "volume": 1.0,
  "sample_rate": 24000,
  "stream_format": "audio"
}
```

**Response:** 
- `return_url=false`: Raw audio binary
- `return_url=true`: JSON with signed URL — handles both `{"url": "..."}` and `{"data": {"url": "..."}}` shapes

**Parameters:**
| Parameter | Type | Default | Notes |
|---|---|---|---|
| `voice` | string | `lively-girl` | 40+ voices available |
| `response_format` | string | `mp3` | `mp3`, `wav`, `flac`, `opus`, `pcm` |
| `instruction` | string | none | Emotion/style guidance |
| `return_url` | bool | `false` | If true, returns `{"url": "..."}` instead of raw audio |
| `speed` | float | 1.0 | Playback speed multiplier (0.5-2.0) |
| `volume` | float | 1.0 | Volume gain (0.0-2.0) |
| `sample_rate` | int | 24000 | Output sample rate in Hz |
| `stream_format` | string | `audio` | Stream chunk format (audio or sse) |
| `voice_label` | string | none | Pronunciation guidance label |
| `pronunciation_map` | JSON | none | Phonetic overrides (max depth 10, 1000 keys) |

> **Note:** `return_url=true` generates a temporary URL valid for **12 hours**. The URL is signed and expires after that window.

**Voices:** See `STEPFUN_VOICES` in `providers.js` — 40+ options organized by category (Audiobook, Customer Service, Emotional, etc.).

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
        "enable_itn": true,
        "hotwords": ["word1", "word2"],
        "prompt": "context prompt"
      },
      "format": {
        "type": "mp3"
      }
    }
  }
}
```

Note: For PCM format, include rate, bits, and channel: `{"type": "pcm", "rate": 16000, "bits": 16, "channel": 1}`
For container formats (mp3, wav, ogg), only the "type" field is sent.

**Parameters:**
| Parameter | Type | Default | Notes |
|---|---|---|---|
| `language` | string | `en` | `en` or `zh` |
| `format` (override) | string | auto-detected | Override MIME type: `mp3`, `wav`, `ogg`, `pcm`, `flac` |
| `hotwords` | array | none | Boost recognition for specific terms (alphanumeric + spaces/hyphens, max 50 chars each) |
| `prompt` | string | none | Context prompt (requires stepaudio-2.5-asr-pro model) |

> **Note:** `prompt` and `hotwords` require the `stepaudio-2.5-asr-pro` model. The standard model ignores these fields.

**PCM format:** When using PCM, you must specify `rate`, `bits`, and `channel` in the `format` object.

**Response:** SSE stream with events:
- `transcript.text.delta` — incremental text
- `transcript.text.done` — final text + usage
- `error` — error message

The `done` event is authoritative — if present and non-empty, it replaces accumulated deltas.

## Bailian Image Generation

**Request:**
```json
{
  "model": "wan2.7-image",
  "input": {
    "messages": [{"role": "user", "content": [{"text": "prompt text"}]}]
  },
  "parameters": {
    "size": "2K",
    "n": 1,
    "watermark": false
  }
}
```

**Response:**
```json
{
  "output": {
    "choices": [{
      "message": {
        "content": [{"image": "https://..."}]
      }
    }]
  }
}
```

**Models:**

| Model | Sizes | Max Prompt |
|---|---|---|
| `wan2.7-image-pro` | 4K, 2K | 5,000 chars |
| `wan2.7-image` | 2K | 5,000 chars |
| `qwen-image-2.0-pro` | 2048x2048, 1536x1536, 1024x1024 | ~2,000 chars |
| `qwen-image-2.0` | 2048x2048, 1536x1536, 1024x1024 | ~2,000 chars |

## MiniMax Video Generation

**Request (T2V):**
```json
{
  "model": "MiniMax-Hailuo-2.3",
  "prompt": "A serene lake at sunset",
  "duration": 6,
  "resolution": "768P"
}
```

**Request (I2V):**
```json
{
  "model": "MiniMax-Hailuo-2.3",
  "prompt": "The cat walking",
  "first_frame_image": "<base64-encoded image>"
}
```

**Response (async):**
```json
{
  "task_id": "abc123xyz",
  "base_resp": {"status_code": 0, "status_msg": ""}
}
```

**Poll response (Success):**
```json
{
  "status": "Success",
  "file_id": "file_abc123",
  "base_resp": {"status_code": 0, "status_msg": ""}
}
```

**Models:**

| Model | Type | Duration |
|---|---|---|
| `MiniMax-Hailuo-2.3` | T2V, I2V | 6s, 10s (T2V) / 6s (I2V) |
| `MiniMax-Hailuo-2.3-Fast` | I2V | 6s only |
| `MiniMax-Hailuo-02` | T2V, I2V | 6s, 10s (T2V) / 6s (I2V) |

**Resolutions:** `512P`, `768P`, `1080P` (model dependent)

**MiniMax Error Codes (status_code):**

| Code | Meaning |
|---|---|
| 0 | Success |
| 1002 | Rate limited |
| 1004 | Authentication failed |
| 1026 | Prompt flagged (content safety) |
| 1027 | Content flagged |
| 2008 | Insufficient balance |
| 2013 | Invalid parameters |
| 2049 | Invalid API key |

## Error Codes

| Code | Meaning | Action |
|---|---|---|
| 400 | Bad request | Check parameter format and values |
| 401 | Unauthorized | Verify `STEPFUN_API_KEY` is set correctly |
| 402 | Payment required | Step Plan credits exhausted — top up or upgrade plan |
| 403 | Forbidden | API key lacks permission for this feature |
| 404 | Not found | Check endpoint URL |
| 413 | Payload too large | Audio/image exceeds size limit |
| 422 | Unprocessable entity | Invalid parameters (e.g. unsupported size) |
| 429 | Rate limited | Slow down requests (see rate limits below) |
| 451 | Unavailable for legal reasons | Restricted content detected |
| 500 | Internal server error | Retry with backoff |
| 503 | Service unavailable | StepFun is down — retry later |

## Rate Limits & Quotas

Step Plan V0-V5 tiers:

| Tier | RPM | TPM | Notes |
|---|---|---|---|
| V0 (Free) | 3 | 32,000 | Best-effort, may be deprioritized |
| V1 | 10 | 100,000 | Standard tier |
| V2 | 20 | 200,000 | Production tier |
| V3 | 50 | 500,000 | High-volume tier |
| V4 | 100 | 1,000,000 | Enterprise tier |
| V5 | 200 | 2,000,000 | Maximum tier |

- **RPM** = Requests Per Minute
- **TPM** = Tokens Per Minute (input + output tokens)
- Rate limits apply per API key
- Exceeding limits returns HTTP 429 with `Retry-After` header

## Script Conventions

All scripts in this repo follow these rules:

- **Python stdlib only** — no `pip install` needed
- **Auto-output** — files go to `$OUTPUT_DIR` (default: `~/.zeroclaw/workspace/output`)
- **No filename arguments** — agents don't choose output names
- **Print path to stdout** — agent reads it to know where the file is
- **Validate early** — clear errors before making API calls
- **`--verbose` flag** — metadata goes to stderr, clean stdout for agents

## Environment Variables

### StepFun

| Variable | Required | Default | Description |
|---|---|---|---|
| `STEPFUN_API_KEY` | Yes | — | StepFun API key |
| `OUTPUT_DIR` | No | `~/.zeroclaw/workspace/output` | Output directory |
| `STEPFUN_API_BASE` | No | `https://api.stepfun.ai/step_plan/v1` | Override API base URL |

### Bailian (Alibaba Cloud)

| Variable | Required | Default | Description |
|---|---|---|---|
| `BAILIAN_TOKEN_PLAN_API_KEY` | Yes | — | Bailian API key |
| `BAILIAN_TOKEN_PLAN_API_BASE` | No | `https://token-plan.ap-southeast-1.maas.aliyuncs.com` | Override API base URL |
| `OUTPUT_DIR` | No | `~/.zeroclaw/workspace/output` | Output directory |

### MiniMax

| Variable | Required | Default | Description |
|---|---|---|---|
| `MINIMAX_API_KEY` | Yes | — | MiniMax API key (video generation) |
| `MINIMAX_API_BASE` | No | `https://api.minimax.io/v1` | Override API base URL |
| `OUTPUT_DIR` | No | `~/.zeroclaw/workspace/output` | Output directory |

## Security

All scripts implement:
- **SSRF protection** — only allows `https://` to whitelisted hosts for URL downloads
- **Path traversal prevention** — blocks `..`, absolute paths outside allowed dirs
- **Voice/filename sanitization** — strips path separators and special chars
- **Atomic file writes** — writes to `.tmp` then `os.replace()` to prevent partial files
- **Response size limits** — 50 MB (StepFun/Bailian), 500 MB (MiniMax) cap on all downloads
- **HTTP timeouts** — 60s (StepFun/MiniMax), 120s (Bailian) timeout on all network calls
- **Prompt injection detection** — warns on common injection patterns

## Testing

```bash
# All unit tests
pytest tests/ -v

# Specific module
pytest tests/test_stepfun_image.py -v
pytest tests/test_stepfun_tts.py -v
pytest tests/test_stepfun_asr.py -v
pytest tests/test_bailian_image.py -v
pytest tests/test_minimax_video.py -v
```
