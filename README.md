# Claw Skills Repository

Reusable skills for zeroclaw agents.

## Structure

```
claw-skills/
├── README.md                        # This file
├── CHANGELOG.md                     # Version history
├── TECHNICAL_REFERENCE.md           # Full API specs, error codes, rate limits
├── CONTRIBUTING.md                  # How to add new skills
├── LICENSE                          # MIT License
├── TEST_ALL                         # Run all unit tests
├── pytest.ini                       # Pytest configuration
├── .env.example                     # Environment variable template
├── .gitignore
├── stepfun-image/                   # Skill: Generate and edit images
│   ├── .env.example
│   ├── main.py
│   ├── README.md
│   ├── SKILL.md
│   ├── stepfun_image.py
│   └── TEST
├── stepfun-tts/                     # Skill: Text-to-speech
│   ├── .env.example
│   ├── main.py
│   ├── README.md
│   ├── SKILL.md
│   ├── stepfun_tts.py
│   └── TEST
├── stepfun-asr/                     # Skill: Speech recognition
│   ├── .env.example
│   ├── main.py
│   ├── README.md
│   ├── SKILL.md
│   ├── stepfun_asr.py
│   └── TEST
└── tests/                           # Unit + integration tests
    ├── test_stepfun_image.py
    ├── test_stepfun_tts.py
    ├── test_stepfun_asr.py
    └── test_live_integration.py
```

## Quick Start

1. Copy the environment template and add your API key:
   ```bash
   cp .env.example .env
   # Edit .env and set STEPFUN_API_KEY=your-key-here
   ```

2. Validate the installation (no API key required):
   ```bash
   bash TEST_ALL
   ```

3. Set your API key and run a skill:
   ```bash
   export STEPFUN_API_KEY="your-key-here"
   cd stepfun-image && python main.py generate --prompt "A cat"
   ```

## Running Tests

```bash
# All unit tests (no API key required)
PYTHONPATH="stepfun-tts:stepfun-asr:stepfun-image" pytest tests/ -v -k "not integration"

# Or use the test runner script
bash TEST_ALL

# Specific module
PYTHONPATH="stepfun-tts:stepfun-asr:stepfun-image" pytest tests/test_stepfun_image.py -v -k "not integration"
PYTHONPATH="stepfun-tts:stepfun-asr:stepfun-image" pytest tests/test_stepfun_tts.py -v -k "not integration"
PYTHONPATH="stepfun-tts:stepfun-asr:stepfun-image" pytest tests/test_stepfun_asr.py -v -k "not integration"

```

## Live Integration Tests

The repository also includes **live integration tests** that make real API calls to
StepFun and consume plan credits. These are marked with `@pytest.mark.integration` and
are **skipped by default**.

**⚠️ Cost warning:** Each live test makes 1–2 API calls (image generation, TTS, ASR, or
image edit). Estimated cost per full run: ~$0.01–$0.05 USD equivalent in StepFun plan
credits. A banner is printed to stderr when integration tests are loaded with the API
key present.

### Running live tests

```bash
# Run only live integration tests
pytest tests/ -v -m integration

# Run all tests including live ones
pytest tests/ -v
```

### Running unit tests only (skipping live tests)

```bash
pytest tests/ -v -k "not integration"
```

### Requirements

- `STEPFUN_API_KEY` environment variable must be set (live tests are auto-skipped if missing)
- Internet connectivity to `api.stepfun.ai`
- Active StepFun plan with available credits

### What's tested

| Test | Verifies |
|---|---|
| `test_live_image_generation` | PNG output, valid signature, size > 0 < 50MB |
| `test_live_image_edit` | Edit from a generated base image, valid PNG output |
| `test_live_tts_mp3` | MP3 output, valid header, size > 1KB |
| `test_live_tts_return_url` | TTS with return_url flag, downloads from signed URL |
| `test_live_tts_with_instruction` | TTS with emotion instruction parameter |

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
zeroclaw skills install /path/to/claw-skills/stepfun-image
zeroclaw skills install /path/to/claw-skills/stepfun-tts
zeroclaw skills install /path/to/claw-skills/stepfun-asr

```

## Environment Variables

All scripts require:
- `STEPFUN_API_KEY` — Your StepFun API key

Optional:
- `OUTPUT_DIR` — Output directory (default: `~/.zeroclaw/workspace/output`)
- `STEPFUN_API_BASE` — Override API base URL (default: `https://api.stepfun.ai/step_plan/v1`)

Note: The files endpoint (`/v1/files`) always uses the open platform base URL (`/v1`), not `step_plan/v1`, regardless of this setting.
