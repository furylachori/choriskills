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

## Supported Models

| Skill | Model | Notes |
|---|---|---|
| stepfun-image | `step-image-edit-2` | Used for both generation and edit |

### Image sizes

Square: `1024x1024` | Portrait: `768x1360`, `896x1184` | Landscape: `1360x768`, `1184x896`

### Input requirements (edit only)

- PNG or JPEG format
- Pass the file path with `--input`

## All Parameters

| Parameter | Default | Range/Choices | Description |
|---|---|---|---|
| `generate --prompt` | (required) | 1–512 chars | Text description of the image |
| `edit --prompt` | (required) | 1–512 chars | Edit description |
| `generate --model` | `step-image-edit-2` | — | Model name |
| `edit --model` | `step-image-edit-2` | — | Model name |
| `--size` | `1024x1024` | 1024x1024, 768x1360, 896x1184, 1360x768, 1184x896 | Output dimensions (ignored for edit) |
| `--steps` | `8` | 1–50 | Inference steps (higher = slower, better quality) |
| `--cfg-scale` | `1.0` | 0.1–10.0 | Classifier-free guidance scale |
| `--seed` | random | any int | Random seed for reproducibility |
| `--text-mode` | false | flag | Enable text rendering in image |
| `--negative-prompt` | `""` | free text | Features to exclude |
| `--verbose` | false | flag | Print metadata to stderr |

## Environment Setup

Before running, set the required environment variable:

```bash
export STEP_FUN_API_KEY="your-api-key-here"
```

Or create a `.env` file in the skill directory:
```
STEP_FUN_API_KEY=your-api-key-here
```

## Output

### Output Format

The script prints a status message with the output file path to **stdout**:
```
Image generated: /Users/dastua/.zeroclaw/workspace/output/generate_a_cat_20250621_123456.png
```
Agents can extract the path by taking the last whitespace-delimited token, or by parsing after the colon.

The file is saved in `$OUTPUT_DIR` (default: `~/.zeroclaw/workspace/output`). No need to specify a filename.

## Troubleshooting

- **"--size is ignored for edit"** — The edit API accepts but ignores the size parameter; output dimensions are determined by the API
- **"Prompt must be 1–512 characters"** — shorten your prompt
- **"API key not set"** — add `STEP_FUN_API_KEY` to your environment
- **"Input file does not exist"** — check the `--input` path
- **"Invalid image format"** — use PNG or JPEG
- **Image has wrong text** — try `--text-mode` flag

## Technical Reference

Full API parameters and response formats: [TECHNICAL_REFERENCE.md](../TECHNICAL_REFERENCE.md)
