---
name: minimax-video
description: Generate videos from text prompts or images using the MiniMax API. Use when the user asks to create, generate, or produce videos from a description or starting image.
---

# MiniMax Video

Generate videos from text prompts or images using the MiniMax API.

## CRITICAL RULES

> **Read these before generating any video.**

1. **NEVER assume which image to use.** If the user sends a new image, use THAT image. If they don't send an image, ASK which one to use. Never carry over an image from a previous request without explicit confirmation.

2. **ALWAYS confirm before generating I2V.** Tell the user: "I will generate a video using [image path] — is this correct?" Wait for confirmation before proceeding.

3. **Report the task ID immediately.** Do not wait for the video to complete. Tell the user: "Your video is being generated. Task ID: [id]. Ask me for it in ~5 minutes."

4. **Do NOT use `send_message`.** Just report the task ID directly in your response.

5. **Use `retrieve` to fetch completed videos.** When the user asks for their video, run `retrieve --task-id <id>`.

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

### Image-to-Video (I2V)

Animate a **local image file** into a video. Use `--input-image` with a file path (not a URL):

```bash
python minimax_video.py generate --prompt "The cat walking gracefully" --input-image /path/to/cat.png
```

> **Important:** `--input-image` accepts a **local file path**. The script reads the file, encodes it, and sends it to the API. You do NOT need to upload the image to a URL first.

The image becomes the first frame of the generated video.

### Retrieve a video

When a video is generated in async mode, you get a task ID. Use `retrieve` to download the video once it's ready:

```bash
python minimax_video.py retrieve --task-id abc123xyz
```

If the video is still processing, the script will tell you to try again later. Use `--sync` to wait:

```bash
python minimax_video.py retrieve --task-id abc123xyz --sync
```

### Recommended I2V Workflow

**ALWAYS follow this flow to avoid wasting credits:**

1. User sends an image and asks to animate it
2. **Confirm the image:** "I will generate a video using [image path]. Is this correct?"
3. Wait for user confirmation
4. Run the generate command
5. Report the task ID: "Your video is being generated. Task ID: [id]. Ask me for it in ~5 minutes."
6. When user asks for video → use `retrieve --task-id <id>`

**If the user asks for multiple videos from the same image:**
- Confirm each time: "Using [image path] again for this video, correct?"
- This prevents accidentally using a stale image from a different request

**NEVER:**
- Assume which image the user wants without asking
- Carry over an image from a previous request without confirmation
- Wait for the video to complete (use async by default)
- Use `send_message` to report results

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
| `--duration` | None (API default) | 6, 10 | Video length in seconds |
| `--resolution` | None (API default) | 512P, 768P, 1080P | Output resolution (model dependent) |
| `--input-image` | None | local file path | Local image file to use as first frame (I2V). NOT a URL. |
| `--prompt-optimizer` | false | flag | Enable prompt optimizer |
| `--fast-pretreatment` | false | flag | Enable fast pretreatment |
| `--sync` | false | flag | Wait for completion and download |
| `--verbose` | false | flag | Print detailed metadata to stderr |
| `--timeout` | `120` | integer | HTTP timeout in seconds |

### Retrieve Parameters

| Parameter | Default | Range/Choices | Description |
|---|---|---|---|
| `--task-id` | (required) | string | Task ID from a previous generate command |
| `--sync` | false | flag | Wait for completion if still processing |
| `--verbose` | false | flag | Print detailed metadata to stderr |
| `--timeout` | `120` | integer | HTTP timeout in seconds |

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
/path/to/output/video_xxx.mp4
```

For async mode (default), it prints:
```
Task submitted: abc123xyz
Status: https://api.minimax.io/v1/query/video_generation?task_id=abc123xyz
```

For retrieve mode:
- If video is ready: prints the file path to stdout with metadata to stderr
- If still processing (without `--sync`): prints status and task ID to stdout, advice to stderr, exits 0
- If still processing (with `--sync`): waits for completion, then prints file path to stdout

The file is saved in `$OUTPUT_DIR` (default: `~/.zeroclaw/agents/default/workspace/output`).

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
- **"--model must be one of ..."** — use a supported model (e.g. `MiniMax-Hailuo-2.3`)
- **Video generation timed out** — try again or use a shorter duration
- **Rate limited** — wait ~30 seconds and retry

## Technical Reference

Full API parameters and response formats are in `TECHNICAL_REFERENCE.md` at the repository root.