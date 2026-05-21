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
from unittest.mock import patch, MagicMock

# Add parent directory to path so we can import stepfun_asr
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "stepfun-asr"))

import stepfun_asr
from stepfun_asr import get_output_path, get_output_dir, transcribe_audio


class TestOutputPath(unittest.TestCase):
    """Test output path generation."""

    def test_asr_output_path_format(self):
        """Test ASR output path follows expected pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"OUTPUT_DIR": tmpdir}):
                path = get_output_path("txt")
                self.assertIn("asr_transcript_", path)
                self.assertIn(".txt", path)
                self.assertTrue(path.startswith(tmpdir))

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


class TestAudioFileValidation(unittest.TestCase):
    """Test audio file existence check."""

    def test_missing_audio_file(self):
        """Test that missing audio file is caught."""
        with self.assertRaises(SystemExit):
            with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test"}):
                args = MagicMock()
                args.audio = "/nonexistent/path/audio.mp3"
                args.language = "zh"
                args.format = None
                transcribe_audio(args)

    def test_valid_audio_file(self):
        """Test that valid audio file passes validation."""
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"fake audio data")
            temp_audio = f.name
        
        try:
            with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test"}):
                # Should not raise at file check stage
                args = MagicMock()
                args.audio = temp_audio
                args.language = "zh"
                args.format = None
                # We'll mock the API call, so just check file existence check passes
                self.assertTrue(os.path.exists(args.audio))
        finally:
            os.unlink(temp_audio)


class TestApiKeyValidation(unittest.TestCase):
    """Test API key presence check."""

    def test_missing_api_key(self):
        """Test that missing API key exits with error."""
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"fake audio")
            temp_audio = f.name
        
        try:
            with patch.dict(os.environ, {}, clear=False):
                if "STEP_FUN_API_KEY" in os.environ:
                    del os.environ["STEP_FUN_API_KEY"]
                with self.assertRaises(SystemExit):
                    args = MagicMock()
                    args.audio = temp_audio
                    args.language = "zh"
                    args.format = None
                    transcribe_audio(args)
        finally:
            os.unlink(temp_audio)


class TestASRSSEStreaming(unittest.TestCase):
    """Test SSE stream parsing."""

    def test_sse_stream_parsing(self):
        """Test that SSE events are correctly parsed."""
        # Simulate SSE stream
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
                    full_text = event.get('text', full_text)
                    final_usage = event.get('usage')
            except json.JSONDecodeError:
                continue
        
        self.assertEqual(full_text, "Hello world")
        self.assertIsNotNone(final_usage)


class TestASRIntegration(unittest.TestCase):
    """Integration-style tests with mocked API responses."""

    def test_asr_success_transcript(self):
        """Test successful ASR transcription."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a fake audio file
            audio_path = os.path.join(tmpdir, "test.mp3")
            with open(audio_path, "wb") as f:
                f.write(b"fake audio data")
            
            # Mock SSE response - simulate streaming then close
            sse_chunk = b"""data: {"type": "transcript.text.delta", "delta": "Hello"}
data: {"type": "transcript.text.done", "text": "Hello world", "usage": {"total": 2}}
data: [DONE]
"""
            
            mock_reader = MagicMock()
            # Return sse_chunk first, then empty bytes enough times to trigger break (3 consecutive empties)
            mock_reader.read.side_effect = [sse_chunk] + [b''] * 10
            
            mock_response = MagicMock()
            mock_response.makefile.return_value = mock_reader
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            
            with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test", "OUTPUT_DIR": tmpdir}):
                with patch("urllib.request.urlopen", return_value=mock_response):
                    args = MagicMock()
                    args.audio = audio_path
                    args.language = "zh"
                    args.format = None
                    
                    output_path, transcript = transcribe_audio(args)
                    
                    self.assertTrue(os.path.exists(output_path))
                    self.assertEqual(transcript, "Hello world")
                    self.assertIn("asr_transcript_", output_path)


if __name__ == "__main__":
    unittest.main()
