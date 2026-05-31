# stepfun-asr

Convert speech to text using StepFun's ASR API.

## Quick Start

```bash
# Set your API key
export STEPFUN_API_KEY="your-key-here"

# Transcribe audio
python stepfun_asr.py --audio audio.mp3

# Or use the standardized entry point
python main.py --audio audio.mp3
```

## Validation

Quick test to verify the skill works (no API key required):

```bash
./TEST
```

## Files

- `stepfun_asr.py` — main script (direct invocation)
- `main.py` — standardized entry point (for frameworks)
- `SKILL.md` — agent-facing documentation
- `.env.example` — example environment variables
