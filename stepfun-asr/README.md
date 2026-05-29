# stepfun-asr

Convert speech to text using StepFun's ASR API.

## Quick Start

```bash
# Set your API key
export STEPFUN_API_KEY="your-key-here"

# Transcribe audio
python3 $HOME/.zeroclaw/workspace/skills/stepfun-asr/stepfun_asr.py transcribe --file audio.mp3

# Or use the standardized entry point
python3 $HOME/.zeroclaw/workspace/skills/stepfun-asr/main.py transcribe --file audio.mp3
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
