---
name: stepfun-image
description: Generate and edit images using the StepFun Image API. Use when the user asks to create, generate, produce, modify, edit, transform, or alter images with text prompts.
---

# StepFun Image

Generate new images from text or edit existing ones using the StepFun Image API.

## When to Use

Use this skill when the user requests to:
- Generate an image from a text description
- Create artwork, illustrations, or photos based on a prompt
- Edit, modify, or transform an existing image
- Add, remove, or change elements in an image
- Change style, content, or appearance with a text instruction

## How to Use

### Generate a new image

Run `generate` with a text prompt. Output is saved automatically.

```bash
python stepfun_image.py generate --prompt "A serene alpine lake at sunset, mirror reflection, photorealistic, 8K"
```

### Edit an existing image

Run `edit` with a prompt and an input file.

```bash
python stepfun_image.py edit --prompt "Make the dog look older and chubbier" --input input.png
```

## Optional Parameters

Both commands accept:

- `--size 768x1360` — portrait shape
- `--steps 12` — higher quality (slower)
- `--seed 42` — same result each time
- `--text-mode` — render text in the image
- `--negative-prompt "blurry, low quality"` — exclude unwanted features

### Image sizes

Square: `1024x1024` | Portrait: `768x1360`, `896x1184` | Landscape: `1360x768`, `1184x896`

### Input requirements (edit only)

- PNG or JPEG format
- Pass the file path with `--input`

## Output

```
Image generated: /Users/dastua/.zeroclaw/workspace/output/generate_a_serene_alpine_lake_20250621_123456.png
```

The file is saved in `$OUTPUT_DIR` (default: `~/.zeroclaw/workspace/output`). No need to specify a filename.

## Troubleshooting

- **"Prompt must be 1–512 characters"** — shorten your prompt
- **"API key not set"** — add `STEP_FUN_API_KEY` to your environment
- **"Input file does not exist"** — check the `--input` path
- **"Invalid image format"** — use PNG or JPEG
- **Image has wrong text** — try `--text-mode` flag

## Technical Reference

Full API parameters and response formats: [TECHNICAL_REFERENCE.md](./TECHNICAL_REFERENCE.md)
