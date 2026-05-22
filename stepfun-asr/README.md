# stepfun-asr

Convert speech to text using StepFun's ASR API.

## Quick Start

```bash
# Set your API key
export STEP_FUN_API_KEY="your-key-here"

# Transcribe audio
python stepfun_asr.py transcribe --file audio.mp3

# Or use the standardized entry point
python main.py transcribe --file audio.mp3
```

## Validation

Quick test to verify the skill works (no API key required):

```bash
./TEST.sh
```

## Files

- `stepfun_asr.py` — main script (direct invocation)
- `main.py` — standardized entry point (for frameworks)
- `SKILL.md` — agent-facing documentation
