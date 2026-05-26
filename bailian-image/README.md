# bailian-image

Generate images from text prompts using the Bailian (Alibaba Cloud) Image API.

## Quick Start

```bash
# Set your API key
export BAILIAN_TOKEN_PLAN_API_KEY="your-key-here"

# Generate an image
python bailian_image.py generate --prompt "A serene mountain landscape at sunset"

# Or use the standardized entry point
python main.py generate --prompt "A serene mountain landscape at sunset"
```

## Files

- `bailian_image.py` — main script (direct invocation)
- `main.py` — standardized entry point (for frameworks)
- `SKILL.md` — agent-facing documentation

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BAILIAN_TOKEN_PLAN_API_KEY` | Yes | — | Your Bailian API key |
| `BAILIAN_TOKEN_PLAN_API_BASE` | No | `https://token-plan.ap-southeast-1.maas.aliyuncs.com` | API base URL |
| `OUTPUT_DIR` | No | `~/.zeroclaw/workspace/output` | Output directory |

## Validation

Quick test to verify the skill works (no API key required):

```bash
./TEST
```

## Supported Models

| Model | Sizes |
|-------|-------|
| `wan2.7-image-pro` | 2K, 4K |
| `wan2.7-image` | 2K |
| `qwen-image-2.0-pro` | 2048x2048, 1536x1536, 1024x1024 |
| `qwen-image-2.0` | 2048x2048, 1536x1536, 1024x1024 |

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

- **"API key not set"** — set `BAILIAN_TOKEN_PLAN_API_KEY` environment variable
- **"Prompt must be 1–2000 characters"** — shorten your prompt
- **"Invalid model or size"** — check the supported models/sizes table
- **Authentication failed** — verify your API key is correct and active
- **Rate limit exceeded** — wait and retry, or check your API plan limits