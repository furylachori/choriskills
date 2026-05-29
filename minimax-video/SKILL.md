---
name: minimax-video
description: Generate videos from text prompts or images using the MiniMax API. Use when the user asks to create, generate, or produce videos from a description or starting image.
---

# MiniMax Video

Generate videos from text prompts or images using the MiniMax API.

## When to Use

Use this skill when the user requests to:
- Generate a video from a text description
- Create video content from a prompt
- Animate an image into a video
- Produce short video clips (6-10 seconds)

## How to Use

### Text-to-Video

Run `generate` with a text prompt:

```bash
python minimax_video.py generate --prompt "A serene lake at sunset with birds flying"
```

### Image-to-Video

Run `generate` with an input image:

```bash
python minimax_video.py generate --prompt "The cat walking gracefully" --input-image cat.png
```

### Retrieve a video

When a video is generated in async mode, you get a task ID. Use `retrieve` to download the video once it's ready:

```bash
python minimax_video.py retrieve --task-id abc123xyz
```

If the video is still processing, the script will tell you to try again later. Use `--sync` to wait:

```bash
python minimax_video.py retrieve --task-id abc123xyz --sync
```

### Sync mode (wait for completion)

By default, the script returns immediately with a task_id. Use `--sync` to wait for completion and download:

```bash
python minimax_video.py generate --prompt "Ocean waves crashing" --sync
```

## Parameters

| Parameter | Default | Range/Choices | Description |
|---|---|---|---|
| `--prompt` | (required) | 1–2000 chars | Text description of the video |
| `--model` | `MiniMax-Hailuo-2.3` | See below | Model name |
| `--duration` | `6` | 6, 10 | Video length in seconds |
| `--resolution` | `768P` | 512P, 768P, 1080P | Output resolution (model dependent) |
| `--input-image` | None | file path | Starting image for I2V |
| `--sync` | false | flag | Wait for completion and download |
| `--verbose` | false | flag | Print detailed metadata to stderr |
| `--task-id` | (required for retrieve) | string | Task ID from a previous generate command |

### Retrieve Parameters

| Parameter | Default | Range/Choices | Description |
|---|---|---|---|
| `--task-id` | (required) | string | Task ID from a previous generate command |
| `--sync` | false | flag | Wait for completion if still processing |
| `--verbose` | false | flag | Print detailed metadata to stderr |

### Supported Models

**Text-to-Video (T2V):**

| Model | Duration |
|-------|----------|
| `MiniMax-Hailuo-2.3` | 6s, 10s |
| `MiniMax-Hailuo-02` | 6s, 10s |

**Image-to-Video (I2V):**

| Model | Duration |
|-------|----------|
| `MiniMax-Hailuo-2.3` | 6s only |
| `MiniMax-Hailuo-2.3-Fast` | 6s only |
| `MiniMax-Hailuo-02` | 6s only |

### Resolution Constraints

| Resolution | Availability |
|------------|--------------|
| `512P` | All models |
| `768P` | All models |
| `1080P` | Model dependent |

## Environment Setup

> **Note:** MiniMax uses separate API keys for different features.
> - `MINIMAX_API_KEY` — video generation only (pay-as-you-go credits)
> - `MINIMAX_PLAN_API_KEY` — music, lyrics, cover generation (plan credits)

Before running, set the required environment variable:

```bash
export MINIMAX_API_KEY="your-api-key-here"
```

Or create a `.env` file in the skill directory:
```
MINIMAX_API_KEY=your-api-key-here
```

## Output

The script prints the output file path to **stdout**:
```
Video generated: /path/to/output/video_xxx.mp4
```

For async mode (default), it prints:
```
Task submitted: abc123xyz
Status: https://api.minimax.io/v1/query/video_generation?task_id=abc123xyz
```

For retrieve mode:
- If video is ready: `Video downloaded: /path/to/output/video_xxx.mp4`
- If still processing: `Video is still processing. Try again in a few minutes.` (exits 0)

The file is saved in `$OUTPUT_DIR` (default: `~/.zeroclaw/workspace/output`).

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

## Troubleshooting

- **"API key not set"** — add `MINIMAX_API_KEY` to your environment
- **"Prompt must be 1–2000 characters"** — shorten your prompt
- **"model is required"** — specify a valid model
- **Video generation timed out** — try again or use a shorter duration
- **Rate limited** — wait ~30 seconds and retry

## Technical Reference

Full API parameters and response formats are in `TECHNICAL_REFERENCE.md` at the repository root.