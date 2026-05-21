---
name: stepfun-image-generation
description: Generate new images from text prompts using the StepFun Image Generation API. Use when the user asks to create, generate, or produce an image from a description.
---

# StepFun Image Generation

Generate a new image from a text prompt using the StepFun API.

## When to Use

Use this skill when the user requests to:
- Generate an image from a text description
- Create artwork, illustrations, or photos based on a prompt
- Produce visual content without an existing source image

## How to Use

Run the script with a prompt. It saves automatically and prints where the file is.

```bash
python stepfun_image.py generate --prompt "A serene alpine lake at sunset, mirror reflection, photorealistic, 8K"
```

### Optional tweaks

- `--size 768x1360` — portrait shape
- `--steps 12` — higher quality (slower)
- `--seed 42` — same result each time
- `--text-mode` — render text in the image
- `--negative-prompt "blurry, low quality"` — exclude unwanted features

### Image sizes

Square: `1024x1024` | Portrait: `768x1360`, `896x1184` | Landscape: `1360x768`, `1184x896`

## What You'll See

```
Image generated: /Users/dastua/.zeroclaw/workspace/output/generate_a_serene_alpine_lake_20250621_123456.png
```

The file is saved in `$OUTPUT_DIR` (default: `~/.zeroclaw/workspace/output`). No need to specify a filename.

## Troubleshooting

- **"Prompt must be 1–512 characters"** — shorten your prompt
- **"API key not set"** — add `STEP_FUN_API_KEY` to your environment
- **Image has wrong text** — try `--text-mode` flag

## Technical Reference

Full API parameters and response formats: [TECHNICAL_REFERENCE.md](../TECHNICAL_REFERENCE.md)
