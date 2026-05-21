# Voice Cloning Skill

Clone a voice from a short audio sample (5-10 seconds) and use it for text-to-speech.

## What This Does

Upload a reference audio recording of a voice, then create a cloned voice that can be
used with the TTS skill to generate speech in that person's voice.


## Plan Requirements

**Voice cloning is a separate Step Plan add-on** — it is not included in the base plan.

| Feature | Required Access |
|---|---|
| `clone` (permanent voice) | `step-tts-2` or `step-tts-mini` model access |
| `preview` (audition only) | `stepaudio-2.5-tts` (may require voice cloning add-on) |
| `upload` (file storage) | Standard Step Plan (1,000 file limit) |

If you receive `HTTP 404: model_invalid` on clone or `HTTP 503: service_unavailable` on preview, your account does not have voice cloning access enabled. Contact StepFun support to add the voice cloning feature to your Step Plan.

You can still use the existing TTS skill with built-in voices (`lively-girl`, `cixingnansheng`, etc.) without any add-on.
## Requirements

- `STEP_FUN_API_KEY` environment variable must be set
- A reference audio file in **WAV or MP3** format only — **OGG is not supported** by the StepFun API — **5-10 seconds** long
  - Longer files work but may take more time and credits
  - Clear, single-speaker audio with minimal background noise works best
  - Supported sample rates: 8000, 16000, 22050, 24000, 48000 Hz

## Usage

### 1. Upload the reference audio (optional)

If you already have a file ID from a previous upload, skip this step.

```bash
python stepfun_voice.py upload --audio reference.wav
```

Output:
```
File uploaded: file-abc123
Filename: reference.wav
Size: 245760 bytes
```

Save the `file-abc123` ID for the next steps.

### 2. Clone the voice

```bash
python stepfun_voice.py clone --audio reference.wav
```

Or use an existing file ID:
```bash
python stepfun_voice.py clone --file-id file-abc123
```

Provide the transcript for better quality:
```bash
python stepfun_voice.py clone --audio reference.wav --text "Hello, this is a sample of my voice."
```

Output:
```
Voice cloned: voice-xyz789
Model: step-tts-2
```

Save the `voice-xyz789` ID for use with TTS.

### 3. Preview the voice (recommended)

Before using the cloned voice in production, preview it:
> **Note:** Preview requires voice cloning access on your Step Plan. If you get a 503 error, your plan doesn't include this feature.

```bash
python stepfun_voice.py preview --file-id file-abc123 --text "Hello, this is a test."
```

Output:
```
Preview audio: /home/user/.zeroclaw/workspace/output/voice_preview_abc123_20250621_123456.wav
Request ID: req-12345
```

Listen to the preview file to verify voice quality.

### 4. Use the cloned voice with TTS

Use the voice ID returned by `clone` with the TTS skill:

```bash
python stepfun_tts.py --text "Hello from my cloned voice" --voice voice-xyz789
```

## Commands Reference

| Command | Description | Required Args |
|---|---|---|
| `upload` | Upload reference audio to StepFun storage | `--audio` |
| `clone` | Create a cloned voice asset | `--audio` or `--file-id` |
| `preview` | Preview voice without creating permanent asset | `--file-id`, `--text` |

> **Note:** The `preview` endpoint supports `stepaudio-2.5-tts`, so you can audition voice cloning without needing access to `step-tts-2`. However, the `clone` endpoint requires `step-tts-2` or `step-tts-mini`.

## Parameters

| Parameter | Description | Default |
|---|---|---|
| `--audio` | Path to reference audio file (WAV/MP3) | — |
| `--file-id` | Uploaded file ID (format: file-xxxxx) | — |
| `--model` | Cloning model. Note: `step-tts-2`/`step-tts-mini` require paid Step Plan access; `stepaudio-2.5-tts` works for **preview only** (no permanent voice created) | `step-tts-2` |
| `--text` | Transcript of reference audio (improves quality) | — |
| `--sample-text` | Text for preview clip (max 50 chars) | — |
| `--transcript` | Transcript for preview (improves preview quality) | — |
| `--instruction` | Emotion/style guidance (stepaudio-2.5-tts only) | — |
| `--speed` | Speaking rate: 0.5-2.0 | 1.0 |
| `--volume` | Volume level: 0.1-2.0 | 1.0 |
| `--verbose` | Print full API responses to stderr | off |

### Supported Formats

| Format | Upload | Clone | Preview |
|---|---|---|---|
| WAV | ✅ | ✅ | ✅ (output) |
| MP3 | ✅ | ✅ | ✅ (output) |
| OGG/FLAC/M4A | ❌ | ❌ | ❌ |

Files in unsupported formats will be rejected at upload time.

## Tips for Best Results

1. **Audio quality**: Use a clean recording with minimal background noise
2. **Duration**: 5-10 seconds is ideal; longer is okay but increases processing time
3. **Single speaker**: Only one person should be speaking in the reference audio
4. **Clear speech**: Avoid mumbling, music, or multiple people talking
5. **Transcript**: Providing the exact transcript significantly improves clone quality
6. **Preview first**: Always preview before using in production

## Output

- **upload**: Prints the file ID to stdout (e.g., `file-abc123`)
- **clone**: Prints the voice ID to stdout (e.g., `voice-xyz789`)
- **preview**: Prints the path to the preview WAV file to stdout

Metadata (model, file size, etc.) goes to stderr when `--verbose` is used.

## Notes

- Cloned voices are permanent assets until deleted via the StepFun dashboard
- Each user can upload up to 1,000 files
- Voice cloning consumes Step Plan credits; check the pricing page for current rates
- The `stepaudio-2.5-tts` model does **not** support the `voice_label` parameter — use `instruction` instead
- `step-tts-2` and `step-tts-mini` require `voice_label` for style/language control, **not** `instruction`

## Error Handling

All errors print to stderr and exit with code 1:
- Missing API key
- Invalid file format or size
- Network/API errors
- Missing required parameters
