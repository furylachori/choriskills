# bailian-wan-image

Generate images from text prompts using the Bailian Wan2.7 model.

## Quick Start

```bash
# Set your API key
export BAILIAN_WAN_API_KEY="your-key-here"

# Generate an image
python bailian_wan_image.py generate --prompt "A serene mountain landscape at sunset"

# With specific size
python bailian_wan_image.py generate --prompt "A serene mountain landscape at sunset" --size 4K
```

## Files

- `bailian_wan_image.py` — main script (direct invocation)
- `main.py` — standardized entry point (for frameworks)
- `SKILL.md` — agent-facing documentation

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BAILIAN_WAN_API_KEY` | Yes | — | Your Bailian API key |
| `BAILIAN_WAN_API_BASE` | No | `https://token-plan.ap-southeast-1.maas.aliyuncs.com` | API base URL |
| `OUTPUT_DIR` | No | `~/.zeroclaw/agents/default/workspace/output` | Output directory |

## Supported Sizes

| Size | Description |
|------|-------------|
| `2K` | Default, recommended for most use cases |
| `4K` | High-quality output |

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

- **"API key not set"** — set `BAILIAN_WAN_API_KEY` environment variable
- **"Prompt too long"** — max 5,000 characters
- **"Invalid size"** — must be one of: 2K, 4K
- **Authentication failed** — verify your API key is correct and active
- **Rate limit exceeded** — wait and retry, or check your API plan limits
