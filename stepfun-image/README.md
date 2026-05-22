# stepfun-image

Generate and edit images using StepFun's Image API.

## Quick Start

```bash
# Set your API key
export STEPFUN_API_KEY="your-key-here"

# Generate an image
python stepfun_image.py generate --prompt "A cat in a hat"

# Or use the standardized entry point
python main.py generate --prompt "A cat in a hat"
```

## Validation

Quick test to verify the skill works (no API key required):

```bash
./TEST.sh
```

## Files

- `stepfun_image.py` — main script (direct invocation)
- `main.py` — standardized entry point (for frameworks)
- `SKILL.md` — agent-facing documentation
