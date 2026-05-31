# minimax-video

Generate videos from text prompts or images using the MiniMax API.

## Quick Start

```bash
# Set your API key
export MINIMAX_API_KEY="your-key-here"

# Generate a video (async — returns task ID)
python minimax_video.py generate --prompt "A serene lake at sunset with birds flying"

# Wait for completion and download
python minimax_video.py generate --prompt "Ocean waves crashing" --sync

# Image-to-video
python minimax_video.py generate --prompt "The cat walking gracefully" --input-image cat.png

# Or use the standardized entry point
python main.py generate --prompt "A serene lake at sunset" --sync
```

## Validation

Quick test to verify the skill works (no API key required):

```bash
./TEST
```

## Files

- `minimax_video.py` — main script (direct invocation)
- `main.py` — standardized entry point (for frameworks)
- `SKILL.md` — agent-facing documentation

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MINIMAX_API_KEY` | Yes | — | Your MiniMax API key |
| `MINIMAX_API_BASE` | No | `https://api.minimax.io/v1` | API base URL |
| `OUTPUT_DIR` | No | `~/.zeroclaw/agents/default/workspace/output` | Output directory |

## Supported Models

### Text-to-Video (T2V)

| Model | Duration |
|-------|----------|
| `MiniMax-Hailuo-2.3` | 6s, 10s |
| `MiniMax-Hailuo-02` | 6s, 10s |

### Image-to-Video (I2V)

| Model | Duration |
|-------|----------|
| `MiniMax-Hailuo-2.3` | 6s only |
| `MiniMax-Hailuo-2.3-Fast` | 6s only |
| `MiniMax-Hailuo-02` | 6s only |

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

- **"API key not set"** — set `MINIMAX_API_KEY` environment variable
- **"Prompt must be 1–2000 characters"** — shorten your prompt
- **"--model must be one of ..."** — use a supported model (e.g. `MiniMax-Hailuo-2.3`)
- **Video generation timed out** — try again or use a shorter duration
- **Rate limited** — wait ~30 seconds and retry
