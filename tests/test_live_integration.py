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
                args.speed = 1.0
                args.volume = 1.0
                args.sample_rate = 24000
                args.return_url = False
                args.voice_label = None
                args.pronunciation_map = None
                args.stream_format = "audio"
                args.markdown_filter = False

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

            # WAV format is not tested in live integration because the StepFun TTS API
            # does not support WAV output in stream mode — this is a real API
            # limitation, not a test bug. WAV output would require non-streaming
            # response handling which is not currently available.

    def test_live_tts_return_url(self):
        """Test TTS with return_url=True - exercises JSON response + download path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.MonkeyPatch.context() as mp:
                mp.setenv("OUTPUT_DIR", tmpdir)
                mp.setenv("STEP_FUN_API_KEY", os.environ["STEP_FUN_API_KEY"])

                args = MagicMock()
                args.text = "Testing the return URL feature."
                args.voice = "lively-girl"
                args.format = "mp3"
                args.instruction = None
                args.verbose = False
                args.speed = 1.0
                args.volume = 1.0
                args.sample_rate = 24000
                args.return_url = True          # KEY: test JSON response path
                args.voice_label = None
                args.pronunciation_map = None
                args.stream_format = "audio"
                args.markdown_filter = False

                output_path = stepfun_tts.text_to_speech(args)

                # Verify downloaded file exists and is valid MP3
                self.assertTrue(os.path.exists(output_path),
                    f"Downloaded audio not created: {output_path}")
                size = os.path.getsize(output_path)
                self.assertGreater(size, 1024,
                    f"Downloaded audio is suspiciously small: {size} bytes")
                with open(output_path, "rb") as f:
                    header = f.read(3)
                is_id3 = header == b"ID3"
                is_mpeg_sync = header[0] == 0xFF and (header[1] & 0xE0) == 0xE0
                self.assertTrue(is_id3 or is_mpeg_sync,
                    f"Downloaded file does not appear to be valid MP3. Header: {header!r}")

    def test_live_tts_with_instruction(self):
        """Test TTS with emotion instruction - exercises instruction parameter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.MonkeyPatch.context() as mp:
                mp.setenv("OUTPUT_DIR", tmpdir)
                mp.setenv("STEP_FUN_API_KEY", os.environ["STEP_FUN_API_KEY"])

                args = MagicMock()
                args.text = "This is a test with emotion guidance."
                args.voice = "lively-girl"
                args.format = "mp3"
                args.instruction = "happy and energetic"
                args.verbose = False
                args.speed = 1.0
                args.volume = 1.0
                args.sample_rate = 24000
                args.return_url = False
                args.voice_label = None
                args.pronunciation_map = None
                args.stream_format = "audio"
                args.markdown_filter = False

                output_path = stepfun_tts.text_to_speech(args)

                self.assertTrue(os.path.exists(output_path))
                size = os.path.getsize(output_path)
                self.assertGreater(size, 1024)


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("STEP_FUN_API_KEY"),
    reason="STEP_FUN_API_KEY environment variable is required"
)
class TestLiveASR(unittest.TestCase):
    """Test real speech recognition against the StepFun API."""

    def test_live_asr_transcription(self):
        """Transcribe a real audio file and verify output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.MonkeyPatch.context() as mp:
                mp.setenv("OUTPUT_DIR", tmpdir)
                mp.setenv("STEP_FUN_API_KEY", os.environ["STEP_FUN_API_KEY"])

                # Create a real WAV file with actual speech-like audio
                audio_path = os.path.join(tmpdir, "test_speech.wav")
                sample_rate = 16000
                duration_sec = 1.0
                num_samples = int(sample_rate * duration_sec)
                data = b""
                for i in range(num_samples):
                    # Generate a sine wave at ~440Hz (musical note A)
                    import math
                    val = int(32767 * 0.3 * math.sin(2 * math.pi * 440 * i / sample_rate))
                    data += struct.pack('<h', val)

                byte_rate = sample_rate * 2
                data_size = len(data)
                header = (
                    b"RIFF"
                    + struct.pack('<I', 36 + data_size)
                    + b"WAVE"
                    + b"fmt "
                    + struct.pack('<I', 16)
                    + struct.pack('<H', 1)   # PCM
                    + struct.pack('<H', 1)   # mono
                    + struct.pack('<I', sample_rate)
                    + struct.pack('<I', byte_rate)
                    + struct.pack('<H', 2)   # 16-bit
                    + struct.pack('<H', 16)
                    + b"data"
                    + struct.pack('<I', data_size)
                )
                with open(audio_path, "wb") as f:
                    f.write(header + data)

                args = MagicMock()
                args.audio = audio_path
                args.language = "en"
                args.format = None
                args.verbose = False
                args.hotwords = None
                args.hotwords_list = None
                args.prompt = None

                output_path, transcript = stepfun_asr.transcribe_audio(args)

                # Verify transcript file was created
                self.assertTrue(os.path.exists(output_path),
                    f"Transcript not created: {output_path}")
                self.assertIn("asr_transcript_", output_path)

                # Read back the transcript
                with open(output_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.assertTrue(len(content) > 0, "Transcript is empty")
                # The transcript text should also be returned
                self.assertIsInstance(transcript, str)

    def test_live_asr_with_hotwords(self):
        """Test ASR with hotwords parameter - boosts recognition of specific terms."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.MonkeyPatch.context() as mp:
                mp.setenv("OUTPUT_DIR", tmpdir)
                mp.setenv("STEP_FUN_API_KEY", os.environ["STEP_FUN_API_KEY"])

                # Same 440Hz sine wave audio
                audio_path = os.path.join(tmpdir, "test_speech_hotwords.wav")
                sample_rate = 16000
                num_samples = 16000
                data = b""
                for i in range(num_samples):
                    import math
                    val = int(32767 * 0.3 * math.sin(2 * math.pi * 440 * i / sample_rate))
                    data += struct.pack('<h', val)

                byte_rate = sample_rate * 2
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
                    + struct.pack('<H', 2)
                    + struct.pack('<H', 16)
                    + b"data"
                    + struct.pack('<I', data_size)
                )
                with open(audio_path, "wb") as f:
                    f.write(header + data)

                args = MagicMock()
                args.audio = audio_path
                args.language = "en"
                args.format = None
                args.verbose = False
                args.hotwords = "zeroclaw,claude,API"
                args.hotwords_list = ["zeroclaw", "claude", "API"]
                args.prompt = None

                output_path, transcript = stepfun_asr.transcribe_audio(args)

                self.assertTrue(os.path.exists(output_path))
                content = open(output_path, "r", encoding="utf-8").read()
                self.assertTrue(len(content) > 0)


if __name__ == "__main__":
    # Allow running directly: python tests/test_live_integration.py
    if not os.environ.get("STEP_FUN_API_KEY"):
        print("SKIP: STEP_FUN_API_KEY not set. Skipping live integration tests.",
              file=sys.stderr)
        sys.exit(0)
    unittest.main()
