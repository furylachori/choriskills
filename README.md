# Claw Skills Repository

Reusable skills for zeroclaw agents.

## Structure

```
claw-skills/
├── README.md                        # This file
├── stepfun-image/                   # StepFun Image API skill (generation + edit)
│   ├── generation.md                # Skill: Generate images from text
│   ├── edit.md                      # Skill: Edit existing images
│   └── stepfun_image.py             # Shared script (handles both operations)
├── stepfun-tts/                     # StepFun Text-to-Speech skill
│   ├── SKILL.md                     # Skill definition
│   └── stepfun_tts.py               # TTS script
├── stepfun-asr/                     # StepFun Speech Recognition skill
│   ├── SKILL.md                     # Skill definition
│   └── stepfun_asr.py               # ASR script
└── tests/                            # Unit tests for all skills
    ├── test_stepfun_image.py        # Tests for image gen/edit
    ├── test_stepfun_tts.py          # Tests for TTS
    └── test_stepfun_asr.py          # Tests for ASR
```

## Running Tests

```bash
# All tests
pytest tests/ -v

# Specific module
pytest tests/test_stepfun_image.py -v
pytest tests/test_stepfun_tts.py -v
pytest tests/test_stepfun_asr.py -v
```

## Script Conventions

- Use Python stdlib only (no external dependencies)
- Accept required argument (prompt/text/audio), everything else optional
- Auto-generate output path in `$OUTPUT_DIR` (agents don't choose filenames)
- Print output path to stdout so agent knows where the file is
- Validate inputs and exit with clear error messages
- All API calls use `https://api.stepfun.ai/step_plan/v1` (plan credits, not budget)

## Technical Reference

Full API specs, parameter details, and error codes: [TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md)

## Zeroclaw Integration

Skills are loaded from `~/.zeroclaw/workspace/skills/<name>/` by default.

To install skills from this repo:
```bash
zeroclaw skills install /path/to/claw-skills/stepfun-image
zeroclaw skills install /path/to/claw-skills/stepfun-tts
zeroclaw skills install /path/to/claw-skills/stepfun-asr
```

## Environment Variables

All scripts require:
- `STEP_FUN_API_KEY` — Your StepFun API key

Optional:
- `OUTPUT_DIR` — Output directory (default: `~/.zeroclaw/workspace/output`)
