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
├── install                          # One-command zeroclaw skill installer
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
├── bailian-image/                   # Skill: Generate images (Alibaba Cloud)
│   ├── .env.example
│   ├── main.py
│   ├── README.md
│   ├── SKILL.md
│   ├── bailian_image.py
│   └── TEST
├── minimax-video/                   # Skill: Generate videos (MiniMax)
│   ├── .env.example
│   ├── main.py
│   ├── README.md
│   ├── SKILL.md
│   ├── minimax_video.py
│   └── TEST
└── tests/                           # Unit + integration tests
    ├── test_stepfun_image.py
    ├── test_stepfun_tts.py
    ├── test_stepfun_asr.py
    ├── test_bailian_image.py
    ├── test_minimax_video.py
    └── test_live_integration.py
```

## One-Command Install (zeroclaw)

```bash
git clone https://github.com/furylachori/choriskills.git /tmp/choriskills
cd /tmp/choriskills
bash install <your-stepfun-api-key>
```

This installs `stepfun-image`, `stepfun-tts`, `stepfun-asr`, `bailian-image`, and `minimax-video` into zeroclaw with their `.env` files set.

### Install manually (one by one)

```bash
git clone https://github.com/furylachori/choriskills.git /tmp/choriskills
zeroclaw skills install /tmp/choriskills/stepfun-image
zeroclaw skills install /tmp/choriskills/stepfun-tts
zeroclaw skills install /tmp/choriskills/stepfun-asr
zeroclaw skills install /tmp/choriskills/bailian-image
zeroclaw skills install /tmp/choriskills/minimax-video
```

Then create each `.env`:

```bash
echo "STEPFUN_API_KEY=your-key" > ~/.zeroclaw/workspace/skills/stepfun-image/.env
echo "STEPFUN_API_KEY=your-key" > ~/.zeroclaw/workspace/skills/stepfun-tts/.env
echo "STEPFUN_API_KEY=your-key" > ~/.zeroclaw/workspace/skills/stepfun-asr/.env
echo "BAILIAN_TOKEN_PLAN_API_KEY=your-key" > ~/.zeroclaw/workspace/skills/bailian-image/.env
echo "MINIMAX_API_KEY=your-key" > ~/.zeroclaw/workspace/skills/minimax-video/.env
```

## Running Tests

```bash
# All unit tests (no API key required)
PYTHONPATH="stepfun-tts:stepfun-asr:stepfun-image:bailian-image:minimax-video" pytest tests/ -v -k "not integration"

# Or use the test runner script
bash TEST_ALL
```

## Live Integration Tests

⚠️ **Cost warning:** Each live test makes 1–2 API calls. Requires `STEPFUN_API_KEY` set.

```bash
pytest tests/ -v -m integration
```

| Test | Verifies |
|---|---|
| `test_live_image_generation` | PNG output, valid signature, size > 0 < 50MB |
| `test_live_image_edit` | Edit from a generated base image, valid PNG output |
| `test_live_tts_mp3` | MP3 output, valid header, size > 1KB |
| `test_live_tts_return_url` | TTS with return_url flag, downloads from signed URL |
| `test_live_tts_with_instruction` | TTS with emotion instruction parameter |

## Script Conventions

- Python stdlib only (no external dependencies)
- Auto-generate output path in `$OUTPUT_DIR` (default: `~/.zeroclaw/workspace/output`)
- Print output path to stdout so agent knows where the file is
- Auto-loads `.env` from script directory (no export needed)
- Validate inputs and exit with clear error messages

## Technical Reference

Full API specs, parameter details, error codes, and rate limits: [TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md)
