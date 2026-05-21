#!/usr/bin/env python3
"""
Unit tests for stepfun_tts.py

Run with: python -m pytest tests/test_stepfun_tts.py -v
Or: python tests/test_stepfun_tts.py
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# Add parent directory to path so we can import stepfun_tts
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "stepfun-tts"))

import stepfun_tts
from stepfun_tts import get_output_path, get_output_dir, text_to_speech


class TestOutputPath(unittest.TestCase):
    """Test output path generation."""

    def test_tts_output_path_format(self):
        """Test TTS output path follows expected pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"OUTPUT_DIR": tmpdir}):
                path = get_output_path("lively-girl", "mp3")
                self.assertIn("tts_lively_girl_", path)
                self.assertIn(".mp3", path)
                self.assertTrue(path.startswith(tmpdir))

    def test_default_voice_slug(self):
        """Test default voice slug in filename."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"OUTPUT_DIR": tmpdir}):
                path = get_output_path(voice="cixingnansheng")
                self.assertIn("tts_cixingnansheng_", path)

    def test_output_dir_created(self):
        """Test OUTPUT_DIR is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = os.path.join(tmpdir, "does_not_exist", "nested")
            with patch.dict(os.environ, {"OUTPUT_DIR": new_dir}):
                path = get_output_path()
                self.assertTrue(os.path.exists(new_dir))

    def test_default_output_dir(self):
        """Test default OUTPUT_DIR when env var not set."""
        with patch.dict(os.environ, {}, clear=False):
            if "OUTPUT_DIR" in os.environ:
                del os.environ["OUTPUT_DIR"]
            expected = os.path.expanduser("~/.zeroclaw/workspace/output")
            self.assertEqual(get_output_dir(), expected)


class TestTextValidation(unittest.TestCase):
    """Test text length validation."""

    def test_text_too_short(self):
        """Test that empty text is rejected."""
        with self.assertRaises(SystemExit):
            with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test"}):
                text_to_speech(MagicMock(text="", voice="lively-girl", format="mp3", instruction=None))

    def test_text_too_long(self):
        """Test that text > 1000 chars is rejected."""
        long_text = "a" * 1001
        with self.assertRaises(SystemExit):
            with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test"}):
                text_to_speech(MagicMock(text=long_text, voice="lively-girl", format="mp3", instruction=None))

    def test_text_valid_length(self):
        """Test that valid text length passes validation."""
        # Should not raise
        with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test"}):
            with patch("stepfun_tts.get_output_path", return_value="/tmp/test.mp3"):
                with patch("urllib.request.urlopen") as mock_urlopen:
                    mock_response = MagicMock()
                    mock_response.headers.get.return_value = "audio/mpeg"
                    mock_response.read.return_value = b"fake audio data"
                    mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_response)
                    mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
                    
                    args = MagicMock(text="Hello world", voice="lively-girl", format="mp3", instruction=None)
                    text_to_speech(args)


class TestApiKeyValidation(unittest.TestCase):
    """Test API key presence check."""

    def test_missing_api_key(self):
        """Test that missing API key exits with error."""
        with patch.dict(os.environ, {}, clear=False):
            if "STEP_FUN_API_KEY" in os.environ:
                del os.environ["STEP_FUN_API_KEY"]
            with self.assertRaises(SystemExit):
                text_to_speech(MagicMock(text="test", voice="lively-girl", format="mp3", instruction=None))


class TestTTSIntegration(unittest.TestCase):
    """Integration-style tests with mocked API responses."""

    def test_tts_success_audio(self):
        """Test successful TTS with raw audio response."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_response = MagicMock()
            mock_response.headers.get.return_value = "audio/mpeg"
            mock_response.read.return_value = b"fake audio data"
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            
            with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test", "OUTPUT_DIR": tmpdir}):
                with patch("urllib.request.urlopen", return_value=mock_response):
                    args = MagicMock(text="Hello world", voice="lively-girl", format="mp3", instruction=None)
                    output_path = text_to_speech(args)
                    
                    self.assertTrue(os.path.exists(output_path))
                    self.assertIn("tts_lively_girl_", output_path)
                    self.assertTrue(output_path.endswith(".mp3"))

    def test_tts_with_instruction(self):
        """Test TTS with emotion instruction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_response = MagicMock()
            mock_response.headers.get.return_value = "audio/mpeg"
            mock_response.read.return_value = b"fake audio data"
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            
            with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test", "OUTPUT_DIR": tmpdir}):
                with patch("urllib.request.urlopen", return_value=mock_response):
                    args = MagicMock(
                        text="Hello world",
                        voice="lively-girl",
                        format="mp3",
                        instruction="happy, upbeat"
                    )
                    output_path = text_to_speech(args)
                    
                    self.assertTrue(os.path.exists(output_path))


if __name__ == "__main__":
    unittest.main()
