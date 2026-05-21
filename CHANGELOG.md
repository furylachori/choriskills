# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `main.py` standardized entry point for each skill (framework compatibility)
- `TEST.sh` per-skill validation scripts (no API key required)
- `TEST_ALL.sh` root-level test runner
- `pytest.ini` with integration marker registration
- Skill-level `README.md` with quick start instructions
- Exit code constants for programmatic error handling (EXIT_INPUT_ERROR=2, EXIT_AUTH_ERROR=3, etc.)
- `validate_output_dir()` to prevent path traversal via OUTPUT_DIR env var
- `validate_api_base()` to prevent SSRF via STEPFUN_API_BASE env var
- `--print-transcript` flag for ASR (stdout output option)
- Runtime warning when `--size` is used with image edit (silently ignored by API)

### Fixed
- ASR stdout inconsistency: now prints only path to stdout, transcript to stderr
- TTS `stream_format` values corrected to `audio`/`sse` (API-compatible)
- TTS `return_url` JSON response parsing (handles nested `data.url` shape)
- Image edit size parameter warning added (API ignores it)
- Broken relative link in stepfun-image/SKILL.md
- Duplicate test methods in test_stepfun_tts.py removed
- WAV format removed from live integration tests (unsupported by API)

### Security
- SSRF protection on all download URLs
- Path traversal prevention on input paths and OUTPUT_DIR
- Atomic file writes (.tmp + os.replace)
- Response size limits (50MB) and HTTP timeouts (60s)
- STEPFUN_API_BASE validation (https + allowed hosts only)

## [1.0.0] - 2026-05-21

### Added
- Initial release: stepfun-image, stepfun-tts, stepfun-asr
