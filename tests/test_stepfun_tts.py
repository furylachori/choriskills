#!/usr/bin/env python3
"""
Unit tests for stepfun_tts.py

Run with: python -m pytest tests/test_stepfun_tts.py -v
Or: python tests/test_stepfun_tts.py
"""

import json
import os
import sys
import tempfile
import unittest
import urllib.error
import wave
import struct
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "stepfun-tts"))

import stepfun_tts
from stepfun_tts import get_output_path, get_output_dir, text_to_speech, sanitize_voice


class TestOutputPath(unittest.TestCase):
    def test_tts_output_path_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"OUTPUT_DIR": tmpdir}):
                path = get_output_path("lively-girl", "mp3")
                self.assertIn("tts_lively_girl_", path)
                self.assertIn(".mp3", path)
                self.assertTrue(path.startswith(tmpdir))

    def test_default_voice_slug(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"OUTPUT_DIR": tmpdir}):
                path = get_output_path(voice="cixingnansheng")
                self.assertIn("tts_cixingnansheng_", path)

    def test_output_dir_created(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = os.path.join(tmpdir, "does_not_exist", "nested")
            with patch.dict(os.environ, {"OUTPUT_DIR": new_dir}):
                path = get_output_path()
                self.assertTrue(os.path.exists(new_dir))

    def test_default_output_dir(self):
        with patch.dict(os.environ, {}, clear=False):
            if "OUTPUT_DIR" in os.environ:
                del os.environ["OUTPUT_DIR"]
            expected = os.path.expanduser("~/.zeroclaw/agents/default/workspace/output")
            self.assertEqual(get_output_dir(), expected)


class TestTextValidation(unittest.TestCase):
    def test_text_too_short(self):
        with self.assertRaises(SystemExit):
            with patch.dict(os.environ, {"STEPFUN_API_KEY": "test"}):
                text_to_speech(MagicMock(text="", voice="lively-girl", format="mp3", instruction=None, speed=1.0, volume=1.0, sample_rate=24000, return_url=False, voice_label=None, pronunciation_map=None, stream_format="pcm", markdown_filter=False))

    def test_text_too_long(self):
        long_text = "a" * 1001
        with self.assertRaises(SystemExit):
            with patch.dict(os.environ, {"STEPFUN_API_KEY": "test"}):
                text_to_speech(MagicMock(text=long_text, voice="lively-girl", format="mp3", instruction=None, speed=1.0, volume=1.0, sample_rate=24000, return_url=False, voice_label=None, pronunciation_map=None, stream_format="pcm", markdown_filter=False))

    def test_text_valid_length(self):
        """Test that valid text length passes validation."""
        with patch.dict(os.environ, {"STEPFUN_API_KEY": "test"}):
            with patch("stepfun_tts.get_output_path", return_value="/tmp/test.mp3"):
                with patch("urllib.request.urlopen") as mock_urlopen:
                    # Mock API response (JSON with URL)
                    api_response = MagicMock()
                    api_response.headers.get.return_value = "application/json"
                    api_response.read.return_value = json.dumps(
                        {"url": "https://cdn.aliyuncs.com/audio.mp3"}
                    ).encode()
                    api_response.__enter__ = MagicMock(return_value=api_response)
                    api_response.__exit__ = MagicMock(return_value=False)
                    mock_urlopen.return_value = api_response

                    # Mock download_url to write fake audio
                    with patch("stepfun_tts.download_url") as mock_download:
                        def fake_download(url, output_path, **kwargs):
                            with open(output_path, 'wb') as f:
                                f.write(b"fake audio data")
                        mock_download.side_effect = fake_download

                        args = MagicMock(text="Hello world", voice="lively-girl", format="mp3", instruction=None, speed=1.0, volume=1.0, sample_rate=24000, return_url=False, voice_label=None, pronunciation_map=None, stream_format="pcm", markdown_filter=False)
                        text_to_speech(args)

    def test_text_boundary_1000(self):
        """Text exactly 1000 chars should pass."""
        with patch.dict(os.environ, {"STEPFUN_API_KEY": "test"}):
            with patch("stepfun_tts.get_output_path", return_value="/tmp/test.mp3"):
                with patch("urllib.request.urlopen") as mock_urlopen:
                    # Mock API response (JSON with URL)
                    api_response = MagicMock()
                    api_response.headers.get.return_value = "application/json"
                    api_response.read.return_value = json.dumps(
                        {"url": "https://cdn.aliyuncs.com/audio.mp3"}
                    ).encode()
                    api_response.__enter__ = MagicMock(return_value=api_response)
                    api_response.__exit__ = MagicMock(return_value=False)
                    mock_urlopen.return_value = api_response

                    # Mock download_url to write fake audio
                    with patch("stepfun_tts.download_url") as mock_download:
                        def fake_download(url, output_path, **kwargs):
                            with open(output_path, 'wb') as f:
                                f.write(b"fake audio data")
                        mock_download.side_effect = fake_download

                        args = MagicMock(text="a" * 1000, voice="lively-girl", format="mp3", instruction=None, speed=1.0, volume=1.0, sample_rate=24000, return_url=False, voice_label=None, pronunciation_map=None, stream_format="pcm", markdown_filter=False)
                        text_to_speech(args)

    def test_text_boundary_1(self):
        """Text exactly 1 char should pass."""
        with patch.dict(os.environ, {"STEPFUN_API_KEY": "test"}):
            with patch("stepfun_tts.get_output_path", return_value="/tmp/test.mp3"):
                with patch("urllib.request.urlopen") as mock_urlopen:
                    # Mock API response (JSON with URL)
                    api_response = MagicMock()
                    api_response.headers.get.return_value = "application/json"
                    api_response.read.return_value = json.dumps(
                        {"url": "https://cdn.aliyuncs.com/audio.mp3"}
                    ).encode()
                    api_response.__enter__ = MagicMock(return_value=api_response)
                    api_response.__exit__ = MagicMock(return_value=False)
                    mock_urlopen.return_value = api_response

                    # Mock download_url to write fake audio
                    with patch("stepfun_tts.download_url") as mock_download:
                        def fake_download(url, output_path, **kwargs):
                            with open(output_path, 'wb') as f:
                                f.write(b"fake audio data")
                        mock_download.side_effect = fake_download

                        args = MagicMock(text="a", voice="lively-girl", format="mp3", instruction=None, speed=1.0, volume=1.0, sample_rate=24000, return_url=False, voice_label=None, pronunciation_map=None, stream_format="pcm", markdown_filter=False)
                        text_to_speech(args)


class TestVoiceSanitization(unittest.TestCase):
    def test_sanitize_voice_alphanumeric(self):
        self.assertEqual(sanitize_voice("lively-girl"), "lively-girl")

    def test_sanitize_voice_path_traversal(self):
        self.assertEqual(sanitize_voice("../../etc/passwd"), "passwd")

    def test_sanitize_voice_special_chars(self):
        self.assertEqual(sanitize_voice("voice;rm -rf /"), "voicerm-rf")

    def test_sanitize_voice_backslash(self):
        self.assertEqual(sanitize_voice("voice\\..\\.."), "voice")


class TestApiKeyValidation(unittest.TestCase):
    def test_missing_api_key(self):
        with patch.dict(os.environ, {}, clear=False):
            if "STEPFUN_API_KEY" in os.environ:
                del os.environ["STEPFUN_API_KEY"]
            with self.assertRaises(SystemExit):
                text_to_speech(MagicMock(text="test", voice="lively-girl", format="mp3", instruction=None, speed=1.0, volume=1.0, sample_rate=24000, return_url=False, voice_label=None, pronunciation_map=None, stream_format="pcm", markdown_filter=False))


class TestTTSIntegration(unittest.TestCase):
    def test_tts_success_audio(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"STEPFUN_API_KEY": "test", "OUTPUT_DIR": tmpdir}):
                with patch("urllib.request.urlopen") as mock_urlopen:
                    # Mock API response (JSON with URL)
                    api_response = MagicMock()
                    api_response.headers.get.return_value = "application/json"
                    api_response.read.return_value = json.dumps(
                        {"url": "https://cdn.aliyuncs.com/audio.mp3"}
                    ).encode()
                    api_response.__enter__ = MagicMock(return_value=api_response)
                    api_response.__exit__ = MagicMock(return_value=False)
                    mock_urlopen.return_value = api_response

                    # Mock download_url to write fake audio
                    with patch("stepfun_tts.download_url") as mock_download:
                        def fake_download(url, output_path, **kwargs):
                            with open(output_path, 'wb') as f:
                                f.write(b"fake audio data")
                        mock_download.side_effect = fake_download

                        args = MagicMock(text="Hello world", voice="lively-girl", format="mp3", instruction=None, speed=1.0, volume=1.0, sample_rate=24000, return_url=False, voice_label=None, pronunciation_map=None, stream_format="pcm", markdown_filter=False)
                        output_path = text_to_speech(args)

                        self.assertTrue(os.path.exists(output_path))
                        self.assertIn("tts_lively_girl_", output_path)
                        self.assertTrue(output_path.endswith(".mp3"))

    def test_tts_with_instruction(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"STEPFUN_API_KEY": "test", "OUTPUT_DIR": tmpdir}):
                with patch("urllib.request.urlopen") as mock_urlopen:
                    # Mock API response (JSON with URL)
                    api_response = MagicMock()
                    api_response.headers.get.return_value = "application/json"
                    api_response.read.return_value = json.dumps(
                        {"url": "https://cdn.aliyuncs.com/audio.mp3"}
                    ).encode()
                    api_response.__enter__ = MagicMock(return_value=api_response)
                    api_response.__exit__ = MagicMock(return_value=False)
                    mock_urlopen.return_value = api_response

                    # Mock download_url to write fake audio
                    with patch("stepfun_tts.download_url") as mock_download:
                        def fake_download(url, output_path, **kwargs):
                            with open(output_path, 'wb') as f:
                                f.write(b"fake audio data")
                        mock_download.side_effect = fake_download

                        args = MagicMock(
                            text="Hello world",
                            voice="lively-girl",
                            format="mp3",
                            instruction="happy, upbeat",
                            speed=1.0,
                            volume=1.0,
                            sample_rate=24000,
                            return_url=False,
                            voice_label=None,
                            pronunciation_map=None,
                            stream_format="pcm",
                            markdown_filter=False
                        )
                        output_path = text_to_speech(args)

                        self.assertTrue(os.path.exists(output_path))


class TestRealFileIO(unittest.TestCase):
    """Test with actual small audio file."""

    def _make_wav_bytes(self, duration_sec=0.1, sample_rate=16000):
        """Generate a minimal valid WAV file in memory."""
        num_samples = int(sample_rate * duration_sec)
        data = b""
        for i in range(num_samples):
            # 16-bit mono PCM, simple sine-like wave
            val = int(32767 * 0.1 * (i % 100) / 100)
            data += struct.pack('<h', val)
        
        # WAV header
        byte_rate = sample_rate * 2
        block_align = 2
        data_size = len(data)
        header = (
            b"RIFF"
            + struct.pack('<I', 36 + data_size)
            + b"WAVE"
            + b"fmt "
            + struct.pack('<I', 16)  # fmt chunk size
            + struct.pack('<H', 1)   # PCM
            + struct.pack('<H', 1)   # mono
            + struct.pack('<I', sample_rate)
            + struct.pack('<I', byte_rate)
            + struct.pack('<H', block_align)
            + struct.pack('<H', 16)  # 16-bit
            + b"data"
            + struct.pack('<I', data_size)
        )
        return header + data

    def test_write_real_wav_file(self):
        """Test writing a real small WAV file works."""
        wav_bytes = self._make_wav_bytes(duration_sec=0.05)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(wav_bytes)
            wav_path = f.name
        
        try:
            # Verify it's a valid WAV
            self.assertTrue(os.path.exists(wav_path))
            self.assertGreater(os.path.getsize(wav_path), 0)
            
            with open(wav_path, "rb") as f:
                header = f.read(4)
                self.assertEqual(header, b"RIFF")
        finally:
            os.unlink(wav_path)


class TestErrorPath(unittest.TestCase):
    """Test error handling paths."""

    def test_tts_http_error_non_json(self):
        """Test HTTPError with non-JSON body."""
        import io
        with patch.dict(os.environ, {"STEPFUN_API_KEY": "test", "OUTPUT_DIR": "/tmp"}):
            with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
                "https://api.stepfun.ai/tts", 500, "Server Error", {},
                io.BytesIO(b"Internal Server Error")
            )):
                with self.assertRaises(SystemExit):
                    text_to_speech(MagicMock(text="test", voice="lively-girl", format="mp3", instruction=None, speed=1.0, volume=1.0, sample_rate=24000, return_url=False, voice_label=None, pronunciation_map=None, stream_format="pcm", markdown_filter=False))

    def test_tts_url_error(self):
        """Test URLError (network failure)."""
        with patch.dict(os.environ, {"STEPFUN_API_KEY": "test", "OUTPUT_DIR": "/tmp"}):
            with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Network unreachable")):
                with self.assertRaises(SystemExit):
                    text_to_speech(MagicMock(text="test", voice="lively-girl", format="mp3", instruction=None, speed=1.0, volume=1.0, sample_rate=24000, return_url=False, voice_label=None, pronunciation_map=None, stream_format="pcm", markdown_filter=False))

    def test_tts_oversized_response_blocked(self):
        """Test oversized audio response is rejected."""
        mock_response = MagicMock()
        mock_response.headers.get.return_value = "audio/mpeg"
        mock_response.read.return_value = b"x" * (stepfun_tts.MAX_RESPONSE_SIZE + 1)
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            output = f.name
        
        try:
            with patch.dict(os.environ, {"STEPFUN_API_KEY": "test", "OUTPUT_DIR": "/tmp"}):
                with patch("stepfun_tts.get_output_path", return_value=output):
                    with patch("urllib.request.urlopen", return_value=mock_response):
                        with self.assertRaises(SystemExit):
                            text_to_speech(MagicMock(text="test", voice="lively-girl", format="mp3", instruction=None, speed=1.0, volume=1.0, sample_rate=24000, return_url=False, voice_label=None, pronunciation_map=None, stream_format="pcm", markdown_filter=False))
        finally:
            if os.path.exists(output):
                os.unlink(output)

    def test_tts_json_response_no_url(self):
        """Test JSON response without url field."""
        mock_response = MagicMock()
        mock_response.headers.get.return_value = "application/json"
        mock_response.read.return_value = b'{"error": "something"}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        
        with patch.dict(os.environ, {"STEPFUN_API_KEY": "test", "OUTPUT_DIR": "/tmp"}):
            with patch("urllib.request.urlopen", return_value=mock_response):
                with self.assertRaises(SystemExit):
                    text_to_speech(MagicMock(text="test", voice="lively-girl", format="mp3", instruction=None, speed=1.0, volume=1.0, sample_rate=24000, return_url=False, voice_label=None, pronunciation_map=None, stream_format="pcm", markdown_filter=False))

    def test_tts_download_url_ssrf_blocked(self):
        """Test SSRF blocks non-https URLs in JSON response."""
        mock_response = MagicMock()
        mock_response.headers.get.return_value = "application/json"
        mock_response.read.return_value = b'{"url": "http://evil.com/audio.mp3"}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        
        with patch.dict(os.environ, {"STEPFUN_API_KEY": "test", "OUTPUT_DIR": "/tmp"}):
            with patch("urllib.request.urlopen", return_value=mock_response):
                with self.assertRaises(SystemExit):
                    text_to_speech(MagicMock(text="test", voice="lively-girl", format="mp3", instruction=None, speed=1.0, volume=1.0, sample_rate=24000, return_url=False, voice_label=None, pronunciation_map=None, stream_format="pcm", markdown_filter=False))


if __name__ == "__main__":
    unittest.main()
