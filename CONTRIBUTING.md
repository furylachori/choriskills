# Contributing to Claw Skills

Thank you for your interest in contributing! This document outlines the process for adding new skills or improving existing ones.

## Project Structure

```
claw-skills/
├── stepfun-image/                # Image generation & edit skill
│   ├── .env.example
│   ├── main.py
│   ├── README.md
│   ├── SKILL.md
│   ├── stepfun_image.py
│   └── TEST
├── stepfun-tts/                  # Text-to-speech skill
│   ├── .env.example
│   ├── main.py
│   ├── README.md
│   ├── SKILL.md
│   ├── stepfun_tts.py
│   └── TEST
├── stepfun-asr/                  # Speech recognition skill
│   ├── .env.example
│   ├── main.py
│   ├── README.md
│   ├── SKILL.md
│   ├── stepfun_asr.py
│   └── TEST
├── tests/                        # Unit tests
│   ├── test_stepfun_image.py
│   ├── test_stepfun_tts.py
│   ├── test_stepfun_asr.py
│   └── test_live_integration.py
├── README.md
├── TECHNICAL_REFERENCE.md
├── CONTRIBUTING.md
├── CHANGELOG.md
├── LICENSE
├── TEST_ALL
├── pytest.ini
└── .env.example
```

## Adding a New Skill

1. **Create a directory** under `stepfun-<name>/` following the existing pattern
2. **Create `SKILL.md`** with frontmatter (`name`, `description`) and usage docs
3. **Create the script** (e.g., `stepfun_<name>.py`) following these rules:
   - Python stdlib only (no external dependencies)
   - Auto-generate output paths (no `--output` flag)
   - Print output path to stdout
   - Validate inputs early with clear error messages
   - Use `https://api.stepfun.ai/step_plan/v1` for Step Plan credits
   - Add `--verbose` flag for metadata (stderr)
4. **Create tests** in `tests/test_stepfun_<name>.py`
5. **Add skill to README.md** and `TECHNICAL_REFERENCE.md`

## Running Tests

```bash
# All tests
pytest tests/ -v

# Single module
pytest tests/test_stepfun_tts.py -v
```

## Commit Message Format

Use conventional commits:

```
<type>: <short description>

<body (optional)>
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`

Examples:
```
feat: add support for PCM format in TTS
fix: handle empty SSE stream in ASR
docs: add rate limit table to TECHNICAL_REFERENCE.md
test: add boundary tests for prompt validation
```

## Script Conventions

- **Security**: Validate all inputs, prevent SSRF/path traversal, use atomic file writes
- **Reliability**: Add timeouts (60s), size limits (50MB), proper error handling
- **Testing**: Include happy path, error paths, and boundary tests for every script
- **Documentation**: Update TECHNICAL_REFERENCE.md for any new parameters or endpoints

## Code Review Checklist

- [ ] No `urlretrieve` — use `urlopen` with SSRF protection
- [ ] No path traversal in file operations
- [ ] Atomic file writes (`.tmp` then `os.replace()`)
- [ ] HTTP timeouts on all network calls
- [ ] Response size limits enforced
- [ ] Input validation (ranges, formats, lengths)
- [ ] SSRF protection: host whitelist + OSS suffix + redirect re-validation
- [ ] Symlink prevention: O_NOFOLLOW on file opens + realpath validation
- [ ] SSE limits: buffer cap (10MB) + wall-clock timeout (120s) for streaming
- [ ] Disk space check before writes
- [ ] Magic byte validation for input files (ASR)
- [ ] Prompt injection detection on text inputs
- [ ] CRLF injection prevention in multipart form-data
- [ ] JSON depth/size limits for nested parameters
- [ ] Tests cover error paths and boundaries
- [ ] Documentation updated

## Questions?

Open an issue at https://github.com/Kilo-Org/kilocode/issues
