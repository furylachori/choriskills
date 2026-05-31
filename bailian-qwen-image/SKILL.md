---
name: bailian-qwen-image
description: Generate images using the Bailian Qwen model. Use when the user asks to create, generate, or produce images with text prompts.
---

# Bailian Qwen Image

Generate images from text prompts using the Bailian Qwen model.

## When to Use

Use this skill when the user requests to:
- Generate an image from a text description
- Create artwork, illustrations, or photos based on a prompt
- When standard-quality output is sufficient

## How to Use

Run `generate` with a text prompt:

```bash
cd skills/bailian-qwen-image && python main.py generate --prompt "A serene mountain landscape at sunset, photorealistic"
```

Or from the workspace root:
```bash
python skills/bailian-qwen-image/main.py generate --prompt "A serene mountain landscape at sunset, photorealistic"
```

**Model**: `qwen-image-2.0` (hardcoded, not configurable)  
**Default size**: `2048*2048`

## Parameters

| Parameter | Default | Range/Choices | Description |
|---|---|---|---|
| `--prompt` | (required) | 1–2000 chars | Text description of the image |
| `--size` | `2048*2048` | `2048*2048`, `1536*1536`, `1024*1024` | Output size (WxH pixels) |
| `--verbose` | `false` | flag | Print image URL to stderr |
| `--timeout` | `120` | integer (seconds) | HTTP request timeout |

## Environment Setup

Before running, set the required environment variable:

```bash
export BAILIAN_QWEN_API_KEY="your-api-key-here"
```

Or create a `.env` file in the skill directory:
```
BAILIAN_QWEN_API_KEY=your-api-key-here
```

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BAILIAN_QWEN_API_KEY` | Yes | — | Your Bailian API key |
| `BAILIAN_QWEN_API_BASE` | No | `https://token-plan.ap-southeast-1.maas.aliyuncs.com` | API base URL |
| `OUTPUT_DIR` | No | `~/.zeroclaw/agents/default/workspace/output` | Output directory |

## Output

The script prints the output file path and metadata to **stdout**:
```
/path/to/output/image_xxx.png
Format: PNG
Size: 1234567 bytes
Dimensions: 2048x2048
```

The file is saved in `$OUTPUT_DIR` (default: `~/.zeroclaw/agents/default/workspace/output`).

## Troubleshooting

- **"API key not set"** — add `BAILIAN_QWEN_API_KEY` to your environment
- **"Prompt too long"** — max 2,000 characters
- **"Invalid size"** — must be one of `2048*2048`, `1536*1536`, `1024*1024`
- **Authentication failed** — verify your API key is correct and active
- **Rate limit exceeded** — wait and retry, or check your API plan limits

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 2 | Input/validation error |
| 3 | Authentication failure |
| 4 | Rate limit exceeded |
| 5 | Network error |
| 6 | API error |
| 7 | File/IO error |
