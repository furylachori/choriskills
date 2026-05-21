# Claw Skills Repository

Reusable skills for zeroclaw agents.

## Structure

```
claw-skills/
├── README.md                        # This file
├── TECHNICAL_REFERENCE.md           # Full API specs, error codes, rate limits
├── CONTRIBUTING.md                  # How to add new skills
├── LICENSE                          # MIT License
├── .env.example                     # Environment variable template
├── .gitignore
├── stepfun-image-generation/        # Skill: Generate images from text
│   └── SKILL.md
├── stepfun-image-edit/              # Skill: Edit existing images
│   └── SKILL.md
├── stepfun-tts/                     # StepFun Text-to-Speech skill
│   ├── SKILL.md
│   └── stepfun_tts.py
├── stepfun-asr/                     # StepFun Speech Recognition skill
│   ├── SKILL.md
│   └── stepfun_asr.py
└── tests/                           # Unit tests for all skills
    ├── test_stepfun_image.py
    ├── test_stepfun_tts.py
    └── test_stepfun_asr.py
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

Full API specs, parameter details, error codes, and rate limits: [TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md)

## Zeroclaw Integration

Skills are loaded from `~/.zeroclaw/workspace/skills/<name>/` by default.

To install skills from this repo:
```bash
zeroclaw skills install /path/to/claw-skills/stepfun-image-generation
zeroclaw skills install /path/to/claw-skills/stepfun-image-edit
zeroclaw skills install /path/to/claw-skills/stepfun-tts
zeroclaw skills install /path/to/claw-skills/stepfun-asr
```

## Environment Variables

All scripts require:
- `STEP_FUN_API_KEY` — Your StepFun API key

Optional:
- `OUTPUT_DIR` — Output directory (default: `~/.zeroclaw/workspace/output`)
- `STEPFUN_API_BASE` — Override API base URL (default: `https://api.stepfun.ai/step_plan/v1`)
