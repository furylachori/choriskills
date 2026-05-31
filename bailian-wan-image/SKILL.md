---
name: bailian-wan-image
description: Generate images using the Bailian Wan2.7 model. Use when the user asks to create, generate, or produce high-quality images with text prompts.
---

# Bailian Wan2.7 Image

Generate images from text prompts using the Bailian Wan2.7 model.

## When to Use

Use this skill when the user requests to:
- Generate an image from a text description
- Create artwork, illustrations, or photos based on a prompt
- Generate images with specific size presets (4K, 2K)
- When high-quality or 4K output is needed

## How to Use

Run `generate` with a text prompt:

```bash
cd skills/bailian-wan-image && python main.py generate --prompt "A serene mountain landscape at sunset, photorealistic"
```

Or from the workspace root:
```bash
python skills/bailian-wan-image/main.py generate --prompt "A serene mountain landscape at sunset, photorealistic"
```

**Model**: `wan2.7-image-pro` (hardcoded, not configurable)  
**Default size**: `2K`

## Parameters

| Parameter | Default | Range/Choices | Description |
|---|---|---|---|
| `--prompt` | (required) | 1–5000 chars | Text description of the image |
| `--size` | `2K` | `2K`, `4K` | Output size/quality preset |
| `--verbose` | `false` | flag | Print image URL to stderr |
| `--timeout` | `120` | seconds | HTTP timeout in seconds |

## Environment Setup

Before running, set the required environment variable:

```bash
export BAILIAN_WAN_API_KEY="your-api-key-here"
```

Or create a `.env` file in the skill directory:
```
BAILIAN_WAN_API_KEY=your-api-key-here
```

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BAILIAN_WAN_API_KEY` | Yes | — | Your Bailian API key |
| `BAILIAN_WAN_API_BASE` | No | `https://token-plan.ap-southeast-1.maas.aliyuncs.com` | API base URL |
| `OUTPUT_DIR` | No | `~/.zeroclaw/agents/default/workspace/output` | Output directory |

## Output

The script prints the output file path to **stdout**, followed by image metadata:
```
/path/to/output/image_xxx.png
Format: PNG
Size: 1234567 bytes
Dimensions: 2048x2048
```

The file is saved in `$OUTPUT_DIR` (default: `~/.zeroclaw/agents/default/workspace/output`).

## Troubleshooting

- **"API key not set"** — add `BAILIAN_WAN_API_KEY` to your environment
- **"Prompt too long"** — max 5,000 characters
- **"Invalid size"** — must be one of: 2K, 4K
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
