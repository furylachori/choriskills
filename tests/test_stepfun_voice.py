#!/usr/bin/env python3
"""
Unit tests for stepfun_voice.py

Run with: python -m pytest tests/test_stepfun_voice.py -v
Or: python tests/test_stepfun_voice.py
"""

import os
import sys
import tempfile
import unittest
import json
import base64
import urllib.error
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "stepfun-voice-cloning"))

import stepfun_voice
from stepfun_voice import (
    get_output_dir,
    get_output_path,
    validate_url_safe,
    validate_input_path,
    validate_audio_file,
    upload_audio_file,
    clone_voice,
    preview_voice,
    call_api,
    MAX_RESPONSE_SIZE,
)


class TestOutputPath(unittest.TestCase):
    def test_upload_output_path_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"OUTPUT_DIR": tmpdir}):
                path = get_output_path("upload")
                self.assertIn("upload_", path)
                self.assertTrue(path.startswith(tmpdir))

    def test_clone_output_path_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"OUTPUT_DIR": tmpdir}):
                path = get_output_path("voice_clone")
                self.assertIn("voice_clone_", path)
                self.assertTrue(path.startswith(tmpdir))

    def test_preview_output_path_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"OUTPUT_DIR": tmpdir}):
                path = get_output_path("voice_preview", "wav")
                self.assertIn("voice_preview_", path)
                self.assertTrue(path.endswith(".wav"))
                self.assertTrue(path.startswith(tmpdir))

    def test_output_dir_created(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = os.path.join(tmpdir, "does_not_exist", "nested")
            with patch.dict(os.environ, {"OUTPUT_DIR": new_dir}):
                path = get_output_path("test")
                self.assertTrue(os.path.exists(new_dir))

    def test_default_output_dir(self):
        with patch.dict(os.environ, {}, clear=False):
            if "OUTPUT_DIR" in os.environ:
                del os.environ["OUTPUT_DIR"]
            expected = os.path.expanduser("~/.zeroclaw/workspace/output")
            self.assertEqual(get_output_dir(), expected)


class TestValidation(unittest.TestCase):
    def test_validate_url_safe_https_allowed(self):
        try:
            validate_url_safe("https://api.stepfun.ai/path")
        except SystemExit:
            self.fail("validate_url_safe should allow api.stepfun.ai https URLs")

    def test_validate_url_safe_http_blocked(self):
        with self.assertRaises(SystemExit):
            validate_url_safe("http://api.stepfun.ai/path")

    def test_validate_url_safe_file_blocked(self):
        with self.assertRaises(SystemExit):
            validate_url_safe("file:///etc/passwd")

    def test_validate_url_safe_other_host_blocked(self):
        with self.assertRaises(SystemExit):
            validate_url_safe("https://evil.com/steal")

    def test_validate_url_safe_aliyuncs_allowed(self):
        """Aliyun OSS hostnames should be allowed for downloads."""
        try:
            validate_url_safe("https://oss.aliyuncs.com/bucket/key")
        except SystemExit:
            self.fail("validate_url_safe should allow *.aliyuncs.com URLs")

    def test_validate_input_path_no_traversal(self):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(b"fake")
            path = f.name
        try:
            validate_input_path(path)
        except SystemExit:
            self.fail("validate_input_path should allow normal paths")
        finally:
            os.unlink(path)

    def test_validate_input_path_traversal_blocked(self):
        with self.assertRaises(SystemExit):
            validate_input_path("/tmp/../etc/passwd")

    def test_validate_audio_file_missing(self):
        with self.assertRaises(SystemExit):
            validate_audio_file("/nonexistent/audio.wav")

    def test_validate_audio_file_traversal(self):
        with self.assertRaises(SystemExit):
            validate_audio_file("../../../etc/passwd")

    def test_validate_audio_file_too_large(self):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(b"x" * (MAX_RESPONSE_SIZE + 1))
            path = f.name
        try:
            with self.assertRaises(SystemExit):
                validate_audio_file(path)
        finally:
            os.unlink(path)

    def test_validate_audio_file_invalid_extension(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"fake audio")
            path = f.name
        try:
            with self.assertRaises(SystemExit):
                validate_audio_file(path)
        finally:
            os.unlink(path)

    def test_validate_audio_file_valid_wav(self):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(b"RIFF" + b"\x00" * 100)
            path = f.name
        try:
            # Should not raise
            validate_audio_file(path)
        finally:
            os.unlink(path)

    def test_validate_audio_file_valid_mp3(self):
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"ID3" + b"\x00" * 100)
            path = f.name
        try:
            # Should not raise
            validate_audio_file(path)
        finally:
            os.unlink(path)


class TestApiKeyValidation(unittest.TestCase):
    def test_missing_api_key_upload(self):
        with patch.dict(os.environ, {}, clear=False):
            if "STEP_FUN_API_KEY" in os.environ:
                del os.environ["STEP_FUN_API_KEY"]
            with self.assertRaises(SystemExit):
                call_api("files", data={"purpose": "storage"})

    def test_missing_api_key_clone(self):
        with patch.dict(os.environ, {}, clear=False):
            if "STEP_FUN_API_KEY" in os.environ:
                del os.environ["STEP_FUN_API_KEY"]
            with self.assertRaises(SystemExit):
                call_api("audio/voices", data={"file_id": "file-test"})


class TestUploadAudioFile(unittest.TestCase):
    def test_upload_success(self):
        mock_response = {
            "id": "file-abc123",
            "object": "file",
            "bytes": 245760,
            "filename": "reference.wav",
            "purpose": "storage",
            "status": "processed"
        }

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(b"fake wav data")
            audio_path = f.name

        try:
            with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test"}):
                with patch("stepfun_voice.call_api", return_value=mock_response) as mock_call:
                    args = MagicMock()
                    args.audio = audio_path
                    args.verbose = False

                    file_id = upload_audio_file(args)

                    self.assertEqual(file_id, "file-abc123")
                    mock_call.assert_called_once()
                    call_args = mock_call.call_args
                    self.assertEqual(call_args[0][0], "files")
                    self.assertEqual(call_args[1]["data"]["purpose"], "storage")
                    self.assertIn("file", call_args[1]["files"])
        finally:
            os.unlink(audio_path)

    def test_upload_nonexistent_file(self):
        with self.assertRaises(SystemExit):
            with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test"}):
                args = MagicMock()
                args.audio = "/nonexistent/path/audio.wav"
                args.verbose = False
                upload_audio_file(args)


class TestCloneVoice(unittest.TestCase):
    def test_clone_with_audio_file(self):
        mock_upload_response = {"id": "file-abc123", "filename": "ref.wav"}
        mock_clone_response = {
            "id": "voice-xyz789",
            "object": "audio.voice",
            "duplicated": False
        }

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(b"fake wav data")
            audio_path = f.name

        try:
            with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test"}):
                with patch("stepfun_voice.call_api", side_effect=[mock_upload_response, mock_clone_response]) as mock_call:
                    args = MagicMock()
                    args.audio = audio_path
                    args.file_id = None
                    args.model = "step-tts-2"
                    args.text = "Hello world"
                    args.sample_text = "Test"
                    args.verbose = False

                    voice_id = clone_voice(args)

                    self.assertEqual(voice_id, "voice-xyz789")
                    self.assertEqual(mock_call.call_count, 2)
                    # First call is upload
                    first_call = mock_call.call_args_list[0]
                    self.assertEqual(first_call[0][0], "files")
                    # Second call is clone
                    second_call = mock_call.call_args_list[1]
                    self.assertEqual(second_call[0][0], "audio/voices")
                    self.assertEqual(second_call[1]["data"]["file_id"], "file-abc123")
        finally:
            os.unlink(audio_path)

    def test_clone_with_file_id(self):
        mock_response = {
            "id": "voice-xyz789",
            "object": "audio.voice",
            "duplicated": False
        }

        with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test"}):
            with patch("stepfun_voice.call_api", return_value=mock_response) as mock_call:
                args = MagicMock()
                args.audio = None
                args.file_id = "file-abc123"
                args.model = "step-tts-mini"
                args.text = None
                args.sample_text = None
                args.verbose = False

                voice_id = clone_voice(args)

                self.assertEqual(voice_id, "voice-xyz789")
                mock_call.assert_called_once()
                call_args = mock_call.call_args
                self.assertEqual(call_args[1]["data"]["file_id"], "file-abc123")
                self.assertEqual(call_args[1]["data"]["model"], "step-tts-mini")

    def test_clone_no_audio_or_file_id(self):
        with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test"}):
            args = MagicMock()
            args.audio = None
            args.file_id = None
            args.verbose = False
            with self.assertRaises(SystemExit):
                clone_voice(args)

    def test_clone_missing_id_in_response(self):
        with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test"}):
            with patch("stepfun_voice.upload_audio_file", return_value="file-abc123"):
                with patch("stepfun_voice.call_api", return_value={"object": "audio.voice"}):
                    args = MagicMock()
                    args.audio = "/tmp/test.wav"
                    args.file_id = None
                    args.model = "step-tts-2"
                    args.text = None
                    args.sample_text = None
                    args.verbose = False
                    with self.assertRaises(SystemExit):
                        clone_voice(args)


class TestPreviewVoice(unittest.TestCase):
    def test_preview_success(self):
        # Generate fake WAV audio data
        wav_header = b"RIFF" + b"\x00" * 40 + b"WAVE"
        mock_response = {
            "sample_audio": base64.b64encode(wav_header + b"audio data").decode(),
            "request_id": "req-abc123"
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test", "OUTPUT_DIR": tmpdir}):
                with patch("stepfun_voice.call_api", return_value=mock_response) as mock_call:
                    args = MagicMock()
                    args.file_id = "file-abc123"
                    args.text = "Hello world"
                    args.model = "step-tts-2"
                    args.transcript = None
                    args.instruction = None
                    args.speed = None
                    args.volume = None
                    args.verbose = False

                    output_path = preview_voice(args)

                    self.assertTrue(os.path.exists(output_path))
                    self.assertTrue(output_path.endswith(".wav"))
                    mock_call.assert_called_once()
                    call_args = mock_call.call_args
                    self.assertEqual(call_args[0][0], "audio/voices/preview")
                    self.assertEqual(call_args[1]["data"]["file_id"], "file-abc123")
                    self.assertEqual(call_args[1]["data"]["sample_text"], "Hello world")

    def test_preview_with_all_params(self):
        wav_header = b"RIFF" + b"\x00" * 40 + b"WAVE"
        mock_response = {
            "sample_audio": base64.b64encode(wav_header + b"audio data").decode(),
            "request_id": "req-abc123"
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test", "OUTPUT_DIR": tmpdir}):
                with patch("stepfun_voice.call_api", return_value=mock_response) as mock_call:
                    args = MagicMock()
                    args.file_id = "file-abc123"
                    args.text = "Test preview"
                    args.model = "step-tts-mini"
                    args.transcript = "Test transcript"
                    args.instruction = "happy tone"
                    args.speed = 1.2
                    args.volume = 0.8
                    args.verbose = False

                    preview_voice(args)

                    call_args = mock_call.call_args
                    data = call_args[1]["data"]
                    self.assertEqual(data["file_id"], "file-abc123")
                    self.assertEqual(data["sample_text"], "Test preview")
                    self.assertEqual(data["text"], "Test transcript")
                    self.assertEqual(data["instruction"], "happy tone")
                    self.assertEqual(data["speed"], 1.2)
                    self.assertEqual(data["volume"], 0.8)

    def test_preview_missing_file_id(self):
        with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test"}):
            args = MagicMock()
            args.file_id = None
            args.text = "Hello"
            args.verbose = False
            with self.assertRaises(SystemExit):
                preview_voice(args)

    def test_preview_missing_text(self):
        with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test"}):
            args = MagicMock()
            args.file_id = "file-abc123"
            args.text = None
            args.verbose = False
            with self.assertRaises(SystemExit):
                preview_voice(args)

    def test_preview_no_audio_in_response(self):
        with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test"}):
            with patch("stepfun_voice.call_api", return_value={"request_id": "req-123"}):
                args = MagicMock()
                args.file_id = "file-abc123"
                args.text = "Hello"
                args.verbose = False
                with self.assertRaises(SystemExit):
                    preview_voice(args)


class TestErrorPaths(unittest.TestCase):
    def test_upload_http_error(self):
        import io
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(b"fake audio")
            audio_path = f.name
        try:
            with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test"}):
                with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
                    "https://api.stepfun.ai/files", 500, "Server Error", {},
                    io.BytesIO(b"Internal Server Error")
                )):
                    args = MagicMock()
                    args.audio = audio_path
                    args.verbose = False
                    with self.assertRaises(SystemExit):
                        upload_audio_file(args)
        finally:
            os.unlink(audio_path)

    def test_upload_url_error(self):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(b"fake audio")
            audio_path = f.name
        try:
            with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test"}):
                with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Network unreachable")):
                    args = MagicMock()
                    args.audio = audio_path
                    args.verbose = False
                    with self.assertRaises(SystemExit):
                        upload_audio_file(args)
        finally:
            os.unlink(audio_path)


if __name__ == "__main__":
    unittest.main()
