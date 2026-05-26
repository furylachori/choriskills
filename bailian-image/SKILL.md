---
name: bailian-image
description: Generate images using the Bailian (Alibaba Cloud) Image API. Use when the user asks to create, generate, or produce images with text prompts and wants high-quality output or specific aspect ratios.
---

# Bailian Image

Generate images from text prompts using the Bailian (Alibaba Cloud) Image API.

## When to Use

Use this skill when the user requests to:
- Generate an image from a text description
- Create artwork, illustrations, or photos based on a prompt
- Generate images with specific aspect ratios (4K, 2K, square)
- When high-quality or 4K output is needed

## How to Use

Run `generate` with a text prompt:

```bash
python bailian_image.py generate --prompt "A serene mountain landscape at sunset, photorealistic"
```

**Default model**: `wan2.7-image`  
**Default size**: `2K`

## Parameters

| Parameter | Default | Range/Choices | Description |
|---|---|---|---|
| `--prompt` | (required) | 1–5000 (wan2.7) / 1–2000 (qwen) chars | Text description of the image |

> **Note on prompt limits**: `wan2.7-image` and `wan2.7-image-pro` accept up to 5,000 characters. `qwen-image-2.0` and `qwen-image-2.0-pro` accept up to ~2,000 characters (the API auto-truncates beyond this, but the client validates conservatively).
| `--model` | `wan2.7-image` | See below | Model name |
| `--size` | `2K` | See below | Output size/quality preset |
| `--verbose` | `false` | flag | Print image URL to stderr |

### Supported Models

| Model | Sizes | Max Prompt |
|---|---|---|
| `wan2.7-image-pro` | 4K, 2K | 5,000 chars |
| `wan2.7-image` | 2K | 5,000 chars |
| `qwen-image-2.0-pro` | 2048x2048, 1536x1536, 1024x1024 | ~2,000 chars |
| `qwen-image-2.0` | 2048x2048, 1536x1536, 1024x1024 | ~2,000 chars |

### Image Sizes

- **wan2.7 models**: `2K` (recommended), `4K`
- **qwen-image-2.0 models**: `2048x2048`, `1536x1536`, `1024x1024`

## Environment Setup

Before running, set the required environment variable:

```bash
export BAILIAN_TOKEN_PLAN_API_KEY="your-api-key-here"
```

Or create a `.env` file in the skill directory:
```
BAILIAN_TOKEN_PLAN_API_KEY=your-api-key-here
```

## Output

The script prints the output file path to **stdout**:
```
Image generated: /path/to/output/image_xxx.png
```

The file is saved in `$OUTPUT_DIR` (default: `~/.zeroclaw/workspace/output`).

## Troubleshooting

- **"API key not set"** — add `BAILIAN_TOKEN_PLAN_API_KEY` to your environment
- **"Prompt too long"** — wan2.7 models: max 5,000 chars; qwen models: max ~2,000 chars
- **"Invalid model or size"** — check the supported models/sizes table

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

## Technical Reference

Full API parameters and response formats are in `TECHNICAL_REFERENCE.md` at the repository root.
