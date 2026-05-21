---
name: stepfun-image-edit
description: Edit existing images using text prompts with the StepFun Image Edit API. Use when the user asks to modify, edit, transform, or alter an existing image.
---

# StepFun Image Edit

Edit an existing image using a text prompt.

## When to Use

Use this skill when the user requests to:
- Modify an existing image based on a description
- Add, remove, or change elements in an image
- Transform the style, content, or appearance of an image
- Apply edits like "make it look older", "add a hat", "change background"

## How to Use

Provide the image file and describe what to change.

```bash
python stepfun_image.py edit --prompt "Make the dog look older and chubbier" --input input.png
```

### Optional tweaks

- `--size 768x1360` — portrait shape
- `--steps 12` — higher quality (slower)
- `--seed 42` — same result each time
- `--text-mode` — render text in the image
- `--negative-prompt "blurry, low quality"` — exclude unwanted features

### Input requirements

- PNG or JPEG format
- Just pass the file path with `--input`

## What You'll See

```
Image edited: /Users/dastua/.zeroclaw/workspace/output/edit_make_the_dog_look_older_20250621_123456.png
```

The file is saved in `$OUTPUT_DIR` automatically.

## Troubleshooting

- **"Input file does not exist"** — check the `--input` path
- **"Invalid image format"** — use PNG or JPEG
- **"Prompt must be 1–512 characters"** — shorten your prompt

## Technical Reference

Full API parameters and response formats: [TECHNICAL_REFERENCE.md](../TECHNICAL_REFERENCE.md)
