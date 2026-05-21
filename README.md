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
├── stepfun-voice-cloning/            # Skill: Clone voices from reference audio
│   ├── SKILL.md
│   └── stepfun_voice.py

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
pytest tests/test_stepfun_voice.py -v

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
pytest tests/ -v -k "not Integration"
```

### Requirements

- `STEP_FUN_API_KEY` environment variable must be set (live tests are auto-skipped if missing)
- Internet connectivity to `api.stepfun.ai`
- Active StepFun plan with available credits

### What's tested

| Test | Verifies |
|---|---|
| `test_live_image_generation` | PNG output, valid signature, size > 0 < 50MB |
| `test_live_image_edit` | Edit from a generated base image, valid PNG output |
| `test_live_tts_mp3` | MP3 output, valid header, size > 1KB |
| `test_live_tts_wav_format` | WAV output format works correctly |
| `test_live_roundtrip_tts_asr` | TTS → ASR text match ≥ 80% fuzzy similarity |
| `test_live_roundtrip_tts_asr_short_text` | Short phrase roundtrip ≥ 70% similarity |

Text matching uses fuzzy comparison (`difflib.SequenceMatcher`) because TTS/ASR
roundtrips may vary in punctuation, casing, or minor word differences.

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
zeroclaw skills install /path/to/claw-skills/stepfun-voice-cloning

```

## Environment Variables

All scripts require:
- `STEP_FUN_API_KEY` — Your StepFun API key

Optional:
- `OUTPUT_DIR` — Output directory (default: `~/.zeroclaw/workspace/output`)
- `STEPFUN_API_BASE` — Override API base URL (default: `https://api.stepfun.ai/step_plan/v1`)
