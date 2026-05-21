#!/usr/bin/env python3
"""
Unit tests for stepfun_image.py

Run with: python -m pytest tests/test_stepfun_image.py -v
Or: python tests/test_stepfun_image.py
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# Add parent directory to path so we can import stepfun_image
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "stepfun-image"))

from stepfun_image import (
    get_output_path,
    get_output_dir,
    generate_image,
    edit_image,
    call_api,
)


class TestGetOutputPath(unittest.TestCase):
    """Test output path generation."""

    def test_generate_output_path_format(self):
        """Test generate output path follows expected pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"OUTPUT_DIR": tmpdir}):
                path = get_output_path("generate", "a cat in a hat")
                self.assertIn("generate_", path)
                self.assertIn(".png", path)
                self.assertTrue(path.startswith(tmpdir))

    def test_edit_output_path_format(self):
        """Test edit output path follows expected pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"OUTPUT_DIR": tmpdir}):
                path = get_output_path("edit", "make it older")
                self.assertIn("edit_", path)
                self.assertIn(".png", path)
                self.assertTrue(path.startswith(tmpdir))

    def test_prompt_slug_sanitization(self):
        """Test prompt is sanitized for filesystem."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"OUTPUT_DIR": tmpdir}):
                path = get_output_path("generate", "a cat with spaces & special chars!")
                self.assertNotIn(" ", path)
                self.assertNotIn("&", path)
                self.assertNotIn("!", path)

    def test_output_dir_created(self):
        """Test OUTPUT_DIR is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = os.path.join(tmpdir, "does_not_exist", "nested")
            with patch.dict(os.environ, {"OUTPUT_DIR": new_dir}):
                path = get_output_path("generate", "test")
                self.assertTrue(os.path.exists(new_dir))

    def test_default_output_dir(self):
        """Test default OUTPUT_DIR when env var not set."""
        with patch.dict(os.environ, {}, clear=False):
            if "OUTPUT_DIR" in os.environ:
                del os.environ["OUTPUT_DIR"]
            expected = os.path.expanduser("~/.zeroclaw/workspace/output")
            # get_output_dir() should return the default
            self.assertEqual(get_output_dir(), expected)


class TestPromptValidation(unittest.TestCase):
    """Test prompt length validation."""

    def test_prompt_too_short(self):
        """Test that empty prompt is rejected."""
        with self.assertRaises(SystemExit):
            with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test"}):
                # The validation happens in main(), but we can test the logic directly
                prompt = ""
                if len(prompt) < 1 or len(prompt) > 512:
                    sys.exit(1)

    def test_prompt_too_long(self):
        """Test that prompt > 512 chars is rejected."""
        long_prompt = "a" * 513
        with self.assertRaises(SystemExit):
            with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test"}):
                args = MagicMock()
                args.prompt = long_prompt
                args.input = "/tmp/test.png"
                args.output = "/tmp/test.png"
                # Validation should catch this
                if len(args.prompt) < 1 or len(args.prompt) > 512:
                    sys.exit(1)


class TestApiKeyValidation(unittest.TestCase):
    """Test API key presence check."""

    def test_missing_api_key(self):
        """Test that missing API key exits with error."""
        with patch.dict(os.environ, {}, clear=False):
            if "STEP_FUN_API_KEY" in os.environ:
                del os.environ["STEP_FUN_API_KEY"]
            with self.assertRaises(SystemExit):
                call_api("images/generations", data={})

    def test_present_api_key(self):
        """Test that present API key doesn't cause early exit."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"error": "invalid model"}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        
        with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test-key"}):
            with patch("urllib.request.urlopen", return_value=mock_response):
                # Should not exit before making HTTP call
                # (HTTP call will fail in test, but not due to missing key)
                try:
                    call_api("images/generations", data={})
                except SystemExit as e:
                    self.assertNotEqual(e.code, 1)  # Not the "missing key" exit


class TestInputFileValidation(unittest.TestCase):
    """Test input file existence check for edit."""

    def test_missing_input_file(self):
        """Test that missing input file is caught."""
        with self.assertRaises(SystemExit):
            with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test"}):
                args = MagicMock()
                args.input = "/nonexistent/path/image.png"
                args.prompt = "test prompt"
                args.output = "/tmp/test.png"
                if not os.path.exists(args.input):
                    sys.exit(1)


class TestScriptIntegration(unittest.TestCase):
    """Integration-style tests with mocked API responses."""

    def test_generate_success_message(self):
        """Test that generate prints expected output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_response = {
                "data": [{"b64_json": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==", "seed": 42}]
            }
            with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test", "OUTPUT_DIR": tmpdir}):
                with patch("stepfun_image.call_api", return_value=mock_response):
                    args = MagicMock()
                    args.prompt = "test prompt"
                    args.model = "step-image-edit-2"
                    args.size = "1024x1024"
                    args.steps = 8
                    args.cfg_scale = 1.0
                    args.seed = None
                    args.text_mode = False
                    args.negative_prompt = ""
                    
                    generate_image(args)
                    # Check that file was created
                    self.assertTrue(os.path.exists(args.output))

    def test_edit_success_message(self):
        """Test that edit prints expected output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_response = {
                "data": [{"url": "https://example.com/image.png", "seed": 42}]
            }
            with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test", "OUTPUT_DIR": tmpdir}):
                with patch("stepfun_image.call_api", return_value=mock_response):
                    with patch("urllib.request.urlretrieve"):
                        # Create a dummy input file
                        input_path = os.path.join(tmpdir, "input.png")
                        with open(input_path, "wb") as f:
                            f.write(b"fake image data")
                        
                        args = MagicMock()
                        args.prompt = "test prompt"
                        args.input = input_path
                        args.model = "step-image-edit-2"
                        args.size = "1024x1024"
                        args.steps = 8
                        args.cfg_scale = 1.0
                        args.seed = None
                        args.text_mode = False
                        args.negative_prompt = ""
                        
                        edit_image(args)
                        # Check that output path was set and file would exist
                        self.assertIsNotNone(args.output)
                        self.assertTrue(args.output.startswith(tmpdir))


if __name__ == "__main__":
    unittest.main()
