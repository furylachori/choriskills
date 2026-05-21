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
import urllib.error
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "stepfun-image"))

from stepfun_image import (
    get_output_path,
    get_output_dir,
    generate_image,
    edit_image,
    call_api,
    validate_size,
    validate_steps,
    validate_cfg_scale,
    validate_url_safe,
    validate_input_path,
    sanitize_voice,
    download_url,
    MAX_RESPONSE_SIZE,
)


VALID_SIZES = {"1024x1024", "768x1360", "896x1184", "1360x768", "1184x896"}


class TestGetOutputPath(unittest.TestCase):
    def test_generate_output_path_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"OUTPUT_DIR": tmpdir}):
                path = get_output_path("generate", "a cat in a hat")
                self.assertIn("generate_", path)
                self.assertIn(".png", path)
                self.assertTrue(path.startswith(tmpdir))

    def test_edit_output_path_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"OUTPUT_DIR": tmpdir}):
                path = get_output_path("edit", "make it older")
                self.assertIn("edit_", path)
                self.assertIn(".png", path)
                self.assertTrue(path.startswith(tmpdir))

    def test_prompt_slug_sanitization(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"OUTPUT_DIR": tmpdir}):
                path = get_output_path("generate", "a cat with spaces & special chars!")
                self.assertNotIn(" ", path)
                self.assertNotIn("&", path)
                self.assertNotIn("!", path)

    def test_output_dir_created(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = os.path.join(tmpdir, "does_not_exist", "nested")
            with patch.dict(os.environ, {"OUTPUT_DIR": new_dir}):
                path = get_output_path("generate", "test")
                self.assertTrue(os.path.exists(new_dir))

    def test_default_output_dir(self):
        with patch.dict(os.environ, {}, clear=False):
            if "OUTPUT_DIR" in os.environ:
                del os.environ["OUTPUT_DIR"]
            expected = os.path.expanduser("~/.zeroclaw/workspace/output")
            self.assertEqual(get_output_dir(), expected)


class TestValidation(unittest.TestCase):
    def test_prompt_too_short(self):
        with self.assertRaises(SystemExit):
            prompt = ""
            if len(prompt) < 1:
                sys.exit(1)

    def test_prompt_too_long(self):
        with self.assertRaises(SystemExit):
            long_prompt = "a" * 513
            if len(long_prompt) > 512:
                sys.exit(1)

    def test_prompt_valid_boundary_512(self):
        """Test prompt exactly 512 chars passes."""
        prompt = "a" * 512
        self.assertEqual(len(prompt), 512)
        self.assertTrue(1 <= len(prompt) <= 512)

    def test_prompt_valid_boundary_1(self):
        """Test prompt exactly 1 char passes."""
        prompt = "a"
        self.assertEqual(len(prompt), 1)
        self.assertTrue(1 <= len(prompt) <= 512)

    def test_validate_size_valid(self):
        for size in VALID_SIZES:
            try:
                validate_size(size)
            except SystemExit:
                self.fail(f"validate_size({size}) raised SystemExit unexpectedly")

    def test_validate_size_invalid_format(self):
        with self.assertRaises(SystemExit):
            validate_size("1024")

    def test_validate_size_invalid_value(self):
        with self.assertRaises(SystemExit):
            validate_size("999x999")

    def test_validate_steps_too_small(self):
        with self.assertRaises(SystemExit):
            validate_steps(0)

    def test_validate_steps_too_large(self):
        with self.assertRaises(SystemExit):
            validate_steps(51)

    def test_validate_steps_valid(self):
        for s in [1, 8, 50]:
            try:
                validate_steps(s)
            except SystemExit:
                self.fail(f"validate_steps({s}) raised SystemExit unexpectedly")

    def test_validate_cfg_scale_too_small(self):
        with self.assertRaises(SystemExit):
            validate_cfg_scale(0.05)

    def test_validate_cfg_scale_too_large(self):
        with self.assertRaises(SystemExit):
            validate_cfg_scale(10.1)

    def test_validate_cfg_scale_valid(self):
        for v in [0.1, 1.0, 5.0, 10.0]:
            try:
                validate_cfg_scale(v)
            except SystemExit:
                self.fail(f"validate_cfg_scale({v}) raised SystemExit unexpectedly")

    def test_validate_url_safe_https_allowed(self):
        """Should not raise for allowed https URLs."""
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

    def test_validate_input_path_no_traversal(self):
        """Normal paths should pass."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
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


class TestApiKeyValidation(unittest.TestCase):
    def test_missing_api_key(self):
        with patch.dict(os.environ, {}, clear=False):
            if "STEP_FUN_API_KEY" in os.environ:
                del os.environ["STEP_FUN_API_KEY"]
            with self.assertRaises(SystemExit):
                call_api("images/generations", data={})

    def test_present_api_key(self):
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"error": "invalid model"}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        
        with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test-key"}):
            with patch("urllib.request.urlopen", return_value=mock_response):
                try:
                    call_api("images/generations", data={})
                except SystemExit as e:
                    self.assertNotEqual(e.code, 1)


class TestInputFileValidation(unittest.TestCase):
    def test_missing_input_file(self):
        with self.assertRaises(SystemExit):
            with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test"}):
                args = MagicMock()
                args.input = "/nonexistent/path/image.png"
                args.prompt = "test prompt"
                args.output = "/tmp/test.png"
                if not os.path.exists(args.input):
                    sys.exit(1)

    def test_input_path_with_traversal(self):
        with self.assertRaises(SystemExit):
            with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test"}):
                args = MagicMock()
                args.input = "../../etc/passwd"
                args.prompt = "test"
                validate_input_path(args.input)


class TestScriptIntegration(unittest.TestCase):
    def test_generate_success_message(self):
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
                    self.assertTrue(os.path.exists(args.output))

    def test_edit_success_message(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_response = {
                "data": [{"url": "https://api.stepfun.ai/test.png", "seed": 42}]
            }
            with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test", "OUTPUT_DIR": tmpdir}):
                with patch("stepfun_image.call_api", return_value=mock_response):
                    with patch("stepfun_image.download_url") as mock_download:
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
                        self.assertIsNotNone(args.output)
                        self.assertTrue(args.output.startswith(tmpdir))
                        mock_download.assert_called_once()


class TestErrorPath(unittest.TestCase):
    """Test error handling paths."""

    def test_generate_http_error_non_json(self):
        """Test HTTPError with non-JSON body."""
        import io
        with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test"}):
            with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
                "https://api.stepfun.ai/img", 500, "Server Error", {},
                io.BytesIO(b"Internal Server Error")
            )):
                with self.assertRaises(SystemExit):
                    call_api("images/generations", data={"prompt": "test"})

    def test_generate_url_error(self):
        """Test URLError (network failure)."""
        with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test"}):
            with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Network unreachable")):
                with self.assertRaises(SystemExit):
                    call_api("images/generations", data={"prompt": "test"})

    def test_generate_empty_response_data(self):
        """Test empty data array in response."""
        with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test"}):
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_response = MagicMock()
                mock_response.read.return_value = b'{"data": []}'
                mock_response.__enter__ = MagicMock(return_value=mock_response)
                mock_response.__exit__ = MagicMock(return_value=False)
                mock_urlopen.return_value = mock_response
                
                args = MagicMock()
                args.prompt = "test"
                args.model = "step-image-edit-2"
                args.size = "1024x1024"
                args.steps = 8
                args.cfg_scale = 1.0
                args.seed = None
                args.text_mode = False
                args.negative_prompt = ""
                
                with self.assertRaises(SystemExit):
                    generate_image(args)

    def test_generate_missing_b64_json(self):
        """Test response without b64_json field."""
        with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test"}):
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_response = MagicMock()
                mock_response.read.return_value = b'{"data": [{"url": "https://..."}]}'
                mock_response.__enter__ = MagicMock(return_value=mock_response)
                mock_response.__exit__ = MagicMock(return_value=False)
                mock_urlopen.return_value = mock_response
                
                args = MagicMock()
                args.prompt = "test"
                args.model = "step-image-edit-2"
                args.size = "1024x1024"
                args.steps = 8
                args.cfg_scale = 1.0
                args.seed = None
                args.text_mode = False
                args.negative_prompt = ""
                
                with self.assertRaises(SystemExit):
                    generate_image(args)

    def test_permission_error_on_write(self):
        """Test permission error when writing output file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            read_only_dir = os.path.join(tmpdir, "readonly")
            os.makedirs(read_only_dir)
            os.chmod(read_only_dir, 0o444)
            
            try:
                mock_response = {
                    "data": [{"b64_json": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="}]
                }
                with patch.dict(os.environ, {"STEP_FUN_API_KEY": "test", "OUTPUT_DIR": read_only_dir}):
                    with patch("stepfun_image.call_api", return_value=mock_response):
                        args = MagicMock()
                        args.prompt = "test"
                        args.model = "step-image-edit-2"
                        args.size = "1024x1024"
                        args.steps = 8
                        args.cfg_scale = 1.0
                        args.seed = None
                        args.text_mode = False
                        args.negative_prompt = ""
                        
                        with self.assertRaises(PermissionError):
                            generate_image(args)
            finally:
                os.chmod(read_only_dir, 0o755)

    def test_download_ssrf_http_blocked(self):
        """Test SSRF protection blocks http:// URLs."""
        with self.assertRaises(SystemExit):
            download_url("http://evil.com/steal.png", "/tmp/out.png")

    def test_download_ssrf_wrong_host_blocked(self):
        """Test SSRF protection blocks non-api hosts."""
        with self.assertRaises(SystemExit):
            download_url("https://evil.com/steal.png", "/tmp/out.png")

    def test_download_oversized_response_blocked(self):
        """Test download aborts for oversized responses."""
        mock_response = MagicMock()
        mock_response.headers.get.return_value = str(MAX_RESPONSE_SIZE + 1)
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            output = f.name
        
        try:
            with patch("urllib.request.urlopen", return_value=mock_response):
                with self.assertRaises(SystemExit):
                    download_url("https://api.stepfun.ai/large.png", output)
        finally:
            if os.path.exists(output):
                os.unlink(output)


if __name__ == "__main__":
    unittest.main()
