# bailian-qwen-image

Generate images from text prompts using the Bailian Qwen model.

## Quick Start

```bash
# Set your API key
export BAILIAN_QWEN_API_KEY="your-key-here"

# Generate an image
python bailian_qwen_image.py generate --prompt "A serene mountain landscape at sunset"
```

## Files

- `bailian_qwen_image.py` — main script (direct invocation)
- `main.py` — standardized entry point (for frameworks)
- `SKILL.md` — agent-facing documentation

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BAILIAN_QWEN_API_KEY` | Yes | — | Your Bailian API key |
| `BAILIAN_QWEN_API_BASE` | No | `https://token-plan.ap-southeast-1.maas.aliyuncs.com` | API base URL |
| `OUTPUT_DIR` | No | `~/.zeroclaw/agents/default/workspace/output` | Output directory |

## Supported Sizes

| Size | Description |
|------|-------------|
| `2048*2048` | Default, high quality output |
| `1536*1536` | Medium quality output |
| `1024*1024` | Standard quality output |

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--prompt` | (required) | Text description (1–2000 chars) |
| `--size` | `2048*2048` | Output size (see Supported Sizes) |
| `--verbose` | `false` | Print image URL to stderr |
| `--timeout` | `120` | HTTP timeout in seconds |

## Output

The script prints the output file path and metadata to **stdout**:
```
/path/to/output/image_xxx.png
Format: PNG
Size: 1234567 bytes
Dimensions: 2048x2048
```

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

- **"API key not set"** — set `BAILIAN_QWEN_API_KEY` environment variable
- **"Prompt too long"** — max 2,000 characters
- **"Invalid size"** — must be one of `2048*2048`, `1536*1536`, `1024*1024`
- **Authentication failed** — verify your API key is correct and active
- **Rate limit exceeded** — wait and retry, or check your API plan limits
