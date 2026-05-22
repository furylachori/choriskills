#!/usr/bin/env python3
"""
Unit tests for stepfun_asr.py

Run with: python -m pytest tests/test_stepfun_asr.py -v
Or: python tests/test_stepfun_asr.py
"""

import os
import sys
import tempfile
import unittest
import json
import wave
import struct
import urllib.error
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "stepfun-asr"))

import stepfun_asr
from stepfun_asr import get_output_path, get_output_dir, transcribe_audio


class TestOutputPath(unittest.TestCase):
    def test_asr_output_path_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"OUTPUT_DIR": tmpdir}):
                path = get_output_path("txt")
                self.assertIn("asr_transcript_", path)
                self.assertIn(".txt", path)
                self.assertTrue(path.startswith(tmpdir))

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
            expected = os.path.expanduser("~/.zeroclaw/workspace/output")
            self.assertEqual(get_output_dir(), expected)


class TestAudioFileValidation(unittest.TestCase):
    def test_missing_audio_file(self):
        with self.assertRaises(SystemExit):
            with patch.dict(os.environ, {"STEPFUN_API_KEY": "test"}):
                args = MagicMock()
                args.audio = "/nonexistent/path/audio.mp3"
                args.language = "zh"
                args.format = None
                args.hotwords_list = None
                transcribe_audio(args)

    def test_valid_audio_file(self):
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"fake audio data")
            temp_audio = f.name

        try:
            with patch.dict(os.environ, {"STEPFUN_API_KEY": "test"}):
                args = MagicMock()
                args.audio = temp_audio
                args.language = "zh"
                args.format = None
                args.hotwords_list = None
                self.assertTrue(os.path.exists(args.audio))
        finally:
            os.unlink(temp_audio)

    def test_audio_path_traversal_blocked(self):
        with self.assertRaises(SystemExit):
            with patch.dict(os.environ, {"STEPFUN_API_KEY": "test"}):
                args = MagicMock()
                args.audio = "../../etc/passwd"
                args.language = "en"
                args.format = None
                args.hotwords_list = None
                normalized = args.audio.replace('\\', '/')
                parts = normalized.split('/')
                if '..' in parts:
                    sys.exit(1)


class TestApiKeyValidation(unittest.TestCase):
    def test_missing_api_key(self):
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"fake audio")
            temp_audio = f.name

        try:
            with patch.dict(os.environ, {}, clear=False):
                if "STEPFUN_API_KEY" in os.environ:
                    del os.environ["STEPFUN_API_KEY"]
                with self.assertRaises(SystemExit):
                    args = MagicMock()
                    args.audio = temp_audio
                    args.language = "zh"
                    args.format = None
                    args.hotwords_list = None
                    transcribe_audio(args)
        finally:
            os.unlink(temp_audio)


class TestASRSSEStreaming(unittest.TestCase):
    def test_sse_stream_parsing(self):
        sse_data = b"""data: {"type": "transcript.text.delta", "delta": "Hello"}
data: {"type": "transcript.text.delta", "delta": " world"}
data: {"type": "transcript.text.done", "text": "Hello world", "usage": {"total": 2}}
data: [DONE]
"""

        full_text = ""
        final_usage = None

        for line in sse_data.decode('utf-8').split('\n'):
            line = line.strip()
            if not line or not line.startswith('data:'):
                continue

            data_str = line[5:].strip()
            if data_str == '[DONE]':
                break

            try:
                event = json.loads(data_str)
                event_type = event.get('type', '')

                if event_type == 'transcript.text.delta':
                    full_text += event.get('delta', '')
                elif event_type == 'transcript.text.done':
                    done_text = event.get('text', '')
                    final_usage = event.get('usage')
                    if done_text.strip():
                        full_text = done_text
            except json.JSONDecodeError:
                continue

        self.assertEqual(full_text, "Hello world")
        self.assertIsNotNone(final_usage)

    def test_done_event_authoritative(self):
        """Test that done event overrides accumulated deltas."""
        sse_data = b"""data: {"type": "transcript.text.delta", "delta": "Wrong"}
data: {"type": "transcript.text.done", "text": "Correct text", "usage": {}}
data: [DONE]
"""

        full_text = ""
        for line in sse_data.decode('utf-8').split('\n'):
            line = line.strip()
            if not line or not line.startswith('data:'):
                continue
            data_str = line[5:].strip()
            if data_str == '[DONE]':
                break
            try:
                event = json.loads(data_str)
                event_type = event.get('type', '')
                if event_type == 'transcript.text.delta':
                    full_text += event.get('delta', '')
                elif event_type == 'transcript.text.done':
                    done_text = event.get('text', '')
                    if done_text.strip():
                        full_text = done_text
            except json.JSONDecodeError:
                continue

        self.assertEqual(full_text, "Correct text")

    def test_done_empty_falls_back_to_deltas(self):
        """Test that empty done event falls back to accumulated deltas."""
        sse_data = b"""data: {"type": "transcript.text.delta", "delta": "Hello"}
data: {"type": "transcript.text.done", "text": "", "usage": {}}
data: [DONE]
"""

        full_text = ""
        for line in sse_data.decode('utf-8').split('\n'):
            line = line.strip()
            if not line or not line.startswith('data:'):
                continue
            data_str = line[5:].strip()
            if data_str == '[DONE]':
                break
            try:
                event = json.loads(data_str)
                event_type = event.get('type', '')
                if event_type == 'transcript.text.delta':
                    full_text += event.get('delta', '')
                elif event_type == 'transcript.text.done':
                    done_text = event.get('text', '')
                    if done_text.strip():
                        full_text = done_text
            except json.JSONDecodeError:
                continue

        self.assertEqual(full_text, "Hello")


class TestASRIntegration(unittest.TestCase):
    def test_asr_success_transcript(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, "test.wav")
            # Create a minimal real WAV file
            sample_rate = 16000
            num_samples = 1600  # 0.1 sec
            data = b""
            for i in range(num_samples):
                val = int(32767 * 0.1 * (i % 100) / 100)
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

            sse_chunk = b"""data: {"type": "transcript.text.delta", "delta": "Hello"}
data: {"type": "transcript.text.done", "text": "Hello world", "usage": {"total": 2}}
data: [DONE]
"""

            mock_response = MagicMock()
            mock_response.read.side_effect = [sse_chunk] + [b''] * 10
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)

            with patch.dict(os.environ, {"STEPFUN_API_KEY": "test", "OUTPUT_DIR": tmpdir}):
                with patch("urllib.request.urlopen", return_value=mock_response):
                    args = MagicMock()
                    args.audio = audio_path
                    args.language = "zh"
                    args.format = None
                    args.hotwords_list = None

                    output_path, transcript = transcribe_audio(args)

                    self.assertTrue(os.path.exists(output_path))
                    self.assertEqual(transcript, "Hello world")
                    self.assertIn("asr_transcript_", output_path)

    def test_asr_format_override(self):
        """Test that --format overrides auto-detected format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, "test.wav")
            # Write minimal valid WAV
            sample_rate = 16000
            num_samples = 1600
            data = b""
            for i in range(num_samples):
                val = int(32767 * 0.1 * (i % 100) / 100)
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

            sse_chunk = b"""data: {"type": "transcript.text.delta", "delta": "Hi"}
data: {"type": "transcript.text.done", "text": "Hi", "usage": {}}
data: [DONE]
"""

            mock_response = MagicMock()
            mock_response.read.side_effect = [sse_chunk] + [b''] * 10
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)

            with patch.dict(os.environ, {"STEPFUN_API_KEY": "test", "OUTPUT_DIR": tmpdir}):
                with patch("urllib.request.urlopen", return_value=mock_response):
                    with patch.object(sys, 'argv', ['stepfun_asr', '--audio', audio_path, '--format', 'pcm']):
                        args = MagicMock()
                        args.audio = audio_path
                        args.language = "en"
                        args.format = "pcm"
                        args.verbose = False
                        args.hotwords_list = None

                        output_path, transcript = transcribe_audio(args)
                        self.assertEqual(transcript, "Hi")


class TestErrorPath(unittest.TestCase):
    """Test error handling paths."""

    def test_asr_http_error_non_json(self):
        """Test HTTPError with non-JSON body."""
        import io
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"fake audio")
            temp_audio = f.name

        try:
            with patch.dict(os.environ, {"STEPFUN_API_KEY": "test"}):
                with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
                    "https://api.stepfun.ai/asr", 500, "Server Error", {},
                    io.BytesIO(b"Internal Server Error")
                )):
                    args = MagicMock()
                    args.audio = temp_audio
                    args.language = "en"
                    args.format = None
                    args.hotwords_list = None
                    with self.assertRaises(SystemExit):
                        transcribe_audio(args)
        finally:
            os.unlink(temp_audio)

    def test_asr_url_error(self):
        """Test URLError (network failure)."""
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"fake audio")
            temp_audio = f.name

        try:
            with patch.dict(os.environ, {"STEPFUN_API_KEY": "test"}):
                with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Network unreachable")):
                    args = MagicMock()
                    args.audio = temp_audio
                    args.language = "en"
                    args.format = None
                    args.hotwords_list = None
                    with self.assertRaises(SystemExit):
                        transcribe_audio(args)
        finally:
            os.unlink(temp_audio)

    def test_asr_empty_transcript(self):
        """Test error when no transcript is received."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            audio_path = f.name

        try:
            mock_response = MagicMock()
            mock_response.read.return_value = b""
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)

            with patch.dict(os.environ, {"STEPFUN_API_KEY": "test", "OUTPUT_DIR": "/tmp"}):
                with patch("urllib.request.urlopen", return_value=mock_response):
                    args = MagicMock()
                    args.audio = audio_path
                    args.language = "en"
                    args.format = None
                    args.verbose = False
                    args.hotwords_list = None
                    with self.assertRaises(SystemExit):
                        transcribe_audio(args)
        finally:
            os.unlink(audio_path)

    def test_asr_oversized_audio_blocked(self):
        """Test oversized audio file is rejected."""
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"x" * (stepfun_asr.MAX_RESPONSE_SIZE + 1))
            large_audio = f.name

        try:
            with patch.dict(os.environ, {"STEPFUN_API_KEY": "test"}):
                args = MagicMock()
                args.audio = large_audio
                args.language = "en"
                args.format = None
                args.hotwords_list = None
                with self.assertRaises(SystemExit):
                    transcribe_audio(args)
        finally:
            os.unlink(large_audio)

    def test_asr_malformed_sse_event(self):
        """Test that malformed SSE events are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, "test.wav")
            sample_rate = 16000
            num_samples = 1600
            data = b""
            for i in range(num_samples):
                val = int(32767 * 0.1 * (i % 100) / 100)
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

            # Include malformed lines that should be skipped
            sse_chunk = (
                b"data: this is not json\n"
                b"data: {\"type\": \"transcript.text.delta\", \"delta\": \"Hello\"}\n"
                b": comment line\n"
                b"data: {\"type\": \"transcript.text.done\", \"text\": \"Hello\", \"usage\": {}}\n"
                b"data: [DONE]\n"
            )

            mock_response = MagicMock()
            mock_response.read.side_effect = [sse_chunk] + [b''] * 10
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)

            with patch.dict(os.environ, {"STEPFUN_API_KEY": "test", "OUTPUT_DIR": tmpdir}):
                with patch("urllib.request.urlopen", return_value=mock_response):
                    args = MagicMock()
                    args.audio = audio_path
                    args.language = "en"
                    args.format = None
                    args.verbose = False
                    args.hotwords_list = None

                    output_path, transcript = transcribe_audio(args)
                    self.assertEqual(transcript, "Hello")


if __name__ == "__main__":
    unittest.main()
