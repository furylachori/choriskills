#!/usr/bin/env python3
"""
Live integration tests for StepFun API skills.

These tests hit the real StepFun API and require STEP_FUN_API_KEY to be set.
They are marked with @pytest.mark.integration so they can be skipped by default.

Run with:
    pytest tests/test_live_integration.py -v --integration
    # or
    pytest tests/ -v -m integration

Skip with:
    pytest tests/ -v -k "not Integration"
"""

import os
import sys
import tempfile
import unittest
import struct
from difflib import SequenceMatcher

import pytest

# Add script directories to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "stepfun-image"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "stepfun-tts"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "stepfun-asr"))

from unittest.mock import MagicMock

import stepfun_image
import stepfun_tts
import stepfun_asr


# Cost warning banner printed when module loads if API key is present
if os.environ.get("STEP_FUN_API_KEY"):
    print("""
======================================================================
  LIVE INTEGRATION TESTS — REAL API CALLS
======================================================================
  These tests will consume StepFun plan credits.
  Each test makes 1-2 API calls (image gen, TTS, ASR, image edit).
  Estimated cost per test run: ~$0.01 - $0.05 USD equivalent.

  To skip: pytest tests/ -v -k "not Integration"
  To run only: pytest tests/ -v -m integration
======================================================================
""", file=sys.stderr)


def _similarity_ratio(text1, text2):
    """Calculate fuzzy similarity ratio between two strings (0.0 to 1.0)."""
    return SequenceMatcher(None, text1.lower().strip(), text2.lower().strip()).ratio()


def _make_minimal_wav(path, duration_sec=0.1, sample_rate=16000):
    """Create a minimal valid WAV file at the given path."""
    num_samples = int(sample_rate * duration_sec)
    data = b""
    for i in range(num_samples):
        val = int(32767 * 0.1 * (i % 100) / 100)
        data += struct.pack('<h', val)

    byte_rate = sample_rate * 2
    block_align = 2
    data_size = len(data)
    header = (
        b"RIFF"
        + struct.pack('<I', 36 + data_size)
        + b"WAVE"
        + b"fmt "
        + struct.pack('<I', 16)
        + struct.pack('<H', 1)
        + struct.pack('<H', 1)
        + struct.pack('<I', sample_rate)
        + struct.pack('<I', byte_rate)
        + struct.pack('<H', block_align)
        + struct.pack('<H', 16)
        + b"data"
        + struct.pack('<I', data_size)
    )
    with open(path, "wb") as f:
        f.write(header + data)


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("STEP_FUN_API_KEY"),
    reason="STEP_FUN_API_KEY environment variable is required"
)
class TestLiveImageGeneration(unittest.TestCase):
    """Test real image generation against the StepFun API."""

    def test_live_image_generation(self):
        """Generate a real image from text prompt and verify output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.MonkeyPatch.context() as mp:
                mp.setenv("OUTPUT_DIR", tmpdir)
                mp.setenv("STEP_FUN_API_KEY", os.environ["STEP_FUN_API_KEY"])

                args = MagicMock()
                args.prompt = "A cute red panda sitting on a bamboo branch, digital art"
                args.model = "step-image-edit-2"
                args.size = "1024x1024"
                args.steps = 8
                args.cfg_scale = 1.0
                args.seed = None
                args.text_mode = False
                args.negative_prompt = ""
                args.verbose = False

                # Call the real API
                stepfun_image.generate_image(args)

                # Verify output file was created
                self.assertTrue(os.path.exists(args.output),
                    f"Output file not created: {args.output}")

                # Verify it's a valid PNG
                with open(args.output, "rb") as f:
                    header = f.read(8)
                self.assertEqual(header, b"\x89PNG\r\n\x1a\n",
                    "Output file does not have valid PNG signature")

                # Verify file size is reasonable (> 0 and < 50MB)
                size = os.path.getsize(args.output)
                self.assertGreater(size, 0, "Generated image is empty")
                self.assertLess(size, 50 * 1024 * 1024,
                    f"Generated image exceeds 50MB limit: {size} bytes")

    def test_live_image_generation_with_size_variant(self):
        """Test image generation with a non-default size."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.MonkeyPatch.context() as mp:
                mp.setenv("OUTPUT_DIR", tmpdir)
                mp.setenv("STEP_FUN_API_KEY", os.environ["STEP_FUN_API_KEY"])

                args = MagicMock()
                args.prompt = "A mountain landscape at sunset"
                args.model = "step-image-edit-2"
                args.size = "768x1360"
                args.steps = 8
                args.cfg_scale = 1.0
                args.seed = None
                args.text_mode = False
                args.negative_prompt = ""
                args.verbose = False

                stepfun_image.generate_image(args)

                self.assertTrue(os.path.exists(args.output))
                with open(args.output, "rb") as f:
                    header = f.read(8)
                self.assertEqual(header, b"\x89PNG\r\n\x1a\n")


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("STEP_FUN_API_KEY"),
    reason="STEP_FUN_API_KEY environment variable is required"
)
class TestLiveImageEdit(unittest.TestCase):
    """Test real image editing against the StepFun API."""

    def test_live_image_edit(self):
        """Edit an existing image and verify output is a valid, different image."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.MonkeyPatch.context() as mp:
                mp.setenv("OUTPUT_DIR", tmpdir)
                mp.setenv("STEP_FUN_API_KEY", os.environ["STEP_FUN_API_KEY"])

                # Step 1: Generate a base image to edit
                gen_args = MagicMock()
                gen_args.prompt = "A simple white square on black background"
                gen_args.model = "step-image-edit-2"
                gen_args.size = "1024x1024"
                gen_args.steps = 8
                gen_args.cfg_scale = 1.0
                gen_args.seed = 42
                gen_args.text_mode = False
                gen_args.negative_prompt = ""
                gen_args.verbose = False

                stepfun_image.generate_image(gen_args)
                self.assertTrue(os.path.exists(gen_args.output),
                    "Failed to generate base image for edit test")
                input_path = gen_args.output

                # Step 2: Edit the image
                edit_args = MagicMock()
                edit_args.prompt = "Add a small red circle in the center"
                edit_args.input = input_path
                edit_args.model = "step-image-edit-2"
                edit_args.size = "1024x1024"
                edit_args.steps = 8
                edit_args.cfg_scale = 1.0
                edit_args.seed = None
                edit_args.text_mode = False
                edit_args.negative_prompt = ""
                edit_args.verbose = False

                stepfun_image.edit_image(edit_args)

                # Verify output
                self.assertTrue(os.path.exists(edit_args.output),
                    f"Edited image not created: {edit_args.output}")

                with open(edit_args.output, "rb") as f:
                    header = f.read(8)
                self.assertEqual(header, b"\x89PNG\r\n\x1a\n",
                    "Edited image does not have valid PNG signature")

                size = os.path.getsize(edit_args.output)
                self.assertGreater(size, 0, "Edited image is empty")
                self.assertLess(size, 50 * 1024 * 1024,
                    f"Edited image exceeds 50MB: {size} bytes")


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("STEP_FUN_API_KEY"),
    reason="STEP_FUN_API_KEY environment variable is required"
)
class TestLiveTTS(unittest.TestCase):
    """Test real text-to-speech against the StepFun API."""

    def test_live_tts_mp3(self):
        """Generate speech from text and verify valid MP3 output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.MonkeyPatch.context() as mp:
                mp.setenv("OUTPUT_DIR", tmpdir)
                mp.setenv("STEP_FUN_API_KEY", os.environ["STEP_FUN_API_KEY"])

                args = MagicMock()
                args.text = "Hello, this is a live integration test of the text to speech system."
                args.voice = "lively-girl"
                args.format = "mp3"
                args.instruction = None
                args.verbose = False

                output_path = stepfun_tts.text_to_speech(args)

                # Verify output file exists
                self.assertTrue(os.path.exists(output_path),
                    f"TTS output not created: {output_path}")

                # Verify file size is reasonable (> 1KB)
                size = os.path.getsize(output_path)
                self.assertGreater(size, 1024,
                    f"Generated audio is suspiciously small: {size} bytes")

                # Verify MP3 header bytes (ID3 or MPEG frame sync)
                with open(output_path, "rb") as f:
                    header = f.read(3)
                is_id3 = header == b"ID3"
                is_mpeg_sync = header[0] == 0xFF and (header[1] & 0xE0) == 0xE0
                self.assertTrue(is_id3 or is_mpeg_sync,
                    f"Output does not appear to be a valid MP3. Header: {header!r}")

                self.assertTrue(output_path.endswith(".mp3"),
                    f"Output file should end with .mp3: {output_path}")

    def test_live_tts_wav_format(self):
        """Test TTS with WAV format output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.MonkeyPatch.context() as mp:
                mp.setenv("OUTPUT_DIR", tmpdir)
                mp.setenv("STEP_FUN_API_KEY", os.environ["STEP_FUN_API_KEY"])

                args = MagicMock()
                args.text = "Testing WAV audio output format."
                args.voice = "lively-girl"
                args.format = "wav"
                args.instruction = None
                args.verbose = False

                output_path = stepfun_tts.text_to_speech(args)

                self.assertTrue(os.path.exists(output_path))
                size = os.path.getsize(output_path)
                self.assertGreater(size, 1024)

                # Verify WAV header
                with open(output_path, "rb") as f:
                    header = f.read(4)
                self.assertEqual(header, b"RIFF",
                    f"Output does not have valid WAV header: {header!r}")


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("STEP_FUN_API_KEY"),
    reason="STEP_FUN_API_KEY environment variable is required"
)
class TestLiveRoundtripTTSASR(unittest.TestCase):
    """Test the full TTS -> ASR roundtrip: text -> speech -> text."""

    def test_live_roundtrip_tts_asr(self):
        """Generate TTS, transcribe with ASR, and verify fuzzy text match."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.MonkeyPatch.context() as mp:
                mp.setenv("OUTPUT_DIR", tmpdir)
                mp.setenv("STEP_FUN_API_KEY", os.environ["STEP_FUN_API_KEY"])

                original_text = (
                    "The quick brown fox jumps over the lazy dog. "
                    "This is a standard pangram used for testing."
                )

                # Step 1: Generate TTS
                tts_args = MagicMock()
                tts_args.text = original_text
                tts_args.voice = "lively-girl"
                tts_args.format = "mp3"
                tts_args.instruction = None
                tts_args.verbose = False

                audio_path = stepfun_tts.text_to_speech(tts_args)
                self.assertTrue(os.path.exists(audio_path),
                    f"TTS failed to produce audio: {audio_path}")

                audio_size = os.path.getsize(audio_path)
                self.assertGreater(audio_size, 1024,
                    f"TTS audio too small ({audio_size} bytes), may be empty")

                # Verify it's valid MP3
                with open(audio_path, "rb") as f:
                    header = f.read(3)
                is_id3 = header == b"ID3"
                is_mpeg_sync = header[0] == 0xFF and (header[1] & 0xE0) == 0xE0
                self.assertTrue(is_id3 or is_mpeg_sync,
                    f"TTS output not a valid MP3: {header!r}")

                # Step 2: Transcribe with ASR
                asr_args = MagicMock()
                asr_args.audio = audio_path
                asr_args.language = "en"
                asr_args.format = None  # Auto-detect from file
                asr_args.verbose = False

                output_path, transcript = stepfun_asr.transcribe_audio(asr_args)

                # Verify transcript file was created
                self.assertTrue(os.path.exists(output_path),
                    f"ASR transcript not created: {output_path}")

                # Verify transcript contains text
                self.assertTrue(transcript and transcript.strip(),
                    "ASR returned empty transcript")

                # Verify transcript file content matches returned text
                with open(output_path, "r", encoding="utf-8") as f:
                    file_content = f.read().strip()
                self.assertEqual(file_content, transcript.strip(),
                    "Transcript file content doesn't match returned text")

                # Fuzzy match: similarity should be > 80%
                # TTS/ASR roundtrips may vary slightly in punctuation/casing
                similarity = _similarity_ratio(original_text, transcript)
                self.assertGreater(
                    similarity, 0.80,
                    f"Text match too low ({similarity:.1%}). "
                    f"Original: {original_text!r}\n"
                    f"Got:      {transcript!r}"
                )

    def test_live_roundtrip_tts_asr_short_text(self):
        """Roundtrip with a very short phrase."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.MonkeyPatch.context() as mp:
                mp.setenv("OUTPUT_DIR", tmpdir)
                mp.setenv("STEP_FUN_API_KEY", os.environ["STEP_FUN_API_KEY"])

                original_text = "Hello world"

                tts_args = MagicMock()
                tts_args.text = original_text
                tts_args.voice = "lively-girl"
                tts_args.format = "mp3"
                tts_args.instruction = None
                tts_args.verbose = False

                audio_path = stepfun_tts.text_to_speech(tts_args)
                self.assertTrue(os.path.exists(audio_path))

                asr_args = MagicMock()
                asr_args.audio = audio_path
                asr_args.language = "en"
                asr_args.format = None
                asr_args.verbose = False

                _, transcript = stepfun_asr.transcribe_audio(asr_args)

                # For short text, allow slightly lower threshold (70%)
                similarity = _similarity_ratio(original_text, transcript)
                self.assertGreater(
                    similarity, 0.70,
                    f"Short text match too low ({similarity:.1%}). "
                    f"Original: {original_text!r}\n"
                    f"Got:      {transcript!r}"
                )


if __name__ == "__main__":
    # Allow running directly: python tests/test_live_integration.py
    if not os.environ.get("STEP_FUN_API_KEY"):
        print("SKIP: STEP_FUN_API_KEY not set. Skipping live integration tests.",
              file=sys.stderr)
        sys.exit(0)
    unittest.main()
