# stepfun-tts

Convert text to speech using StepFun's TTS API.

## Quick Start

```bash
# Set your API key
export STEPFUN_API_KEY="your-key-here"

# Synthesize speech
python stepfun_tts.py --text "Hello, world!"

# Or use the standardized entry point
python main.py --text "Hello, world!"
```

## Validation

Quick test to verify the skill works (no API key required):

```bash
./TEST
```

## Files

- `stepfun_tts.py` — main script (direct invocation)
- `main.py` — standardized entry point (for frameworks)
- `SKILL.md` — agent-facing documentation
- `.env.example` — environment variable template
- `TEST` — test runner script
