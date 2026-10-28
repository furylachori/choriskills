"""Deterministic transport regressions; no provider requests or real credentials."""

import contextlib
import http.client
import io
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
from types import SimpleNamespace
import unittest
import urllib.error
import urllib.request
from unittest.mock import call, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "minimax-video"))
import minimax_video as video


class Response(io.BytesIO):
    def __init__(self, body, read_error=None):
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
        super().__init__(body)
        self.headers = {}
        self.read_error = read_error

    def read(self, *args):
        if self.read_error is not None:
            raise self.read_error
        return super().read(*args)


def http_error(code, headers=None, body=b"inert HTTP error"):
    return urllib.error.HTTPError(
        "https://api.minimax.io/v1/video_generation", code, "inert error",
        headers or {}, io.BytesIO(body),
    )


def generation_args(sync=False):
    return SimpleNamespace(
        prompt="inert test prompt", model="MiniMax-Hailuo-2.3", duration=None,
        resolution=None, prompt_optimizer=False, fast_pretreatment=False,
        input_image=None, sync=sync, verbose=False, timeout=7,
    )


class TestRetryBoundary(unittest.TestCase):
    def setUp(self):
        self.start_patch("minimax_video.API_KEY", "inert-test-key")
        self.start_patch("minimax_video.API_URL", "https://api.minimax.io/v1")
        self.transport = self.start_patch(
            "minimax_video.urllib.request.urlopen",
            side_effect=AssertionError("Unscripted inert request"),
        )
        self.start_patch(
            "minimax_video.urllib.request.build_opener",
            return_value=SimpleNamespace(open=self.transport),
        )
        self.start_patch(
            "socket.getaddrinfo",
            return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "",
                           ("93.184.216.34", 443))],
        )
        self.start_patch("socket.socket.connect", side_effect=AssertionError("No network"))
        self.sleep = self.start_patch("minimax_video.time.sleep")
        self.stdout = io.StringIO()
        self.stderr = io.StringIO()
        for capture in (contextlib.redirect_stdout(self.stdout),
                        contextlib.redirect_stderr(self.stderr)):
            capture.__enter__()
            self.addCleanup(capture.__exit__, None, None, None)

    def start_patch(self, *args, **kwargs):
        patcher = patch(*args, **kwargs)
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def reset_transport(self, effects):
        self.transport.reset_mock()
        self.transport.side_effect = effects
        self.sleep.reset_mock()
        self.stderr.seek(0)
        self.stderr.truncate()

    def assert_exit(self, code, function, *args, **kwargs):
        with self.assertRaises(SystemExit) as caught:
            function(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def assert_single_submission(self):
        self.assertEqual(self.transport.call_count, 1)
        self.assertEqual(self.transport.call_args.args[0].get_method(), "POST")
        self.sleep.assert_not_called()

    def assert_ambiguous_guidance(self):
        message = self.stderr.getvalue().lower()
        self.assertRegex(message, "unknown|uncertain")
        self.assertIn("resubmit", message)
        self.assertNotIn("try again", message)

    def test_submission_http_errors_are_not_replayed(self):
        for status in (429, 500, 502, 503, 504):
            with self.subTest(status=status):
                self.reset_transport(http_error(status))
                self.assert_exit(video.EXIT_API_ERROR, video.generate_video, generation_args())
                self.assert_single_submission()
                if status >= 500:
                    self.assert_ambiguous_guidance()

    def test_submission_transport_errors_are_not_replayed(self):
        failures = (
            urllib.error.URLError(ConnectionResetError("inert reset")),
            ConnectionResetError("inert reset"), socket.timeout("inert timeout"),
            urllib.error.URLError(socket.timeout("inert timeout")),
            http.client.RemoteDisconnected("inert disconnect"),
        )
        for failure in failures:
            with self.subTest(failure=repr(failure)):
                self.reset_transport(failure)
                self.assert_exit(video.EXIT_NETWORK_ERROR, video.generate_video, generation_args())
                self.assert_single_submission()
                self.assert_ambiguous_guidance()

    def test_submission_response_read_failures_are_not_replayed(self):
        for failure in (socket.timeout("inert timeout"), ConnectionResetError("inert reset"),
                        http.client.IncompleteRead(b"partial")):
            with self.subTest(failure=repr(failure)):
                self.reset_transport([Response(b"", read_error=failure)])
                self.assert_exit(video.EXIT_NETWORK_ERROR, video.generate_video, generation_args())
                self.assert_single_submission()
                self.assert_ambiguous_guidance()

    def test_submission_invalid_response_or_missing_task_id_is_ambiguous(self):
        for body in (b"not json", b"\xff", b"[]", b"null", {},
                     {"base_resp": None}, {"base_resp": []},
                     {"base_resp": {"status_code": 0}}):
            with self.subTest(body=body):
                self.reset_transport([Response(body)])
                self.assert_exit(video.EXIT_API_ERROR, video.generate_video, generation_args())
                self.assert_single_submission()
                self.assert_ambiguous_guidance()

    def test_async_success_keeps_task_id_on_stdout(self):
        self.transport.side_effect = [Response({
            "task_id": "known-task", "base_resp": {"status_code": 0},
        })]
        self.assert_exit(video.EXIT_OK, video.generate_video, generation_args())
        self.assert_single_submission()
        self.assertEqual(self.stdout.getvalue(),
                         "Task submitted: known-task\n"
                         "Status: https://api.minimax.io/v1/query/video_generation?task_id=known-task\n")

    def test_read_retry_helper_rejects_effectful_methods_before_io(self):
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                request = urllib.request.Request("https://api.minimax.io/v1/test", method=method)
                with self.assertRaises(ValueError):
                    video._urlopen_read_with_retry(request, timeout=7)
        self.transport.assert_not_called()
        self.sleep.assert_not_called()

    def test_head_requests_keep_bounded_safe_retries(self):
        response = Response(b"")
        self.transport.side_effect = [http_error(503), response]
        request = urllib.request.Request("https://api.minimax.io/v1/test", method="HEAD")
        self.assertIs(video._urlopen_read_with_retry(request, timeout=7), response)
        self.assertEqual(self.transport.call_count, 2)
        self.sleep.assert_called_once_with(1)

    def read_cases(self):
        return (
            (video.query_task, "known-task", {"status": "Processing"}, {"status": "Processing"}),
            (video.get_file_download_url, "known-file", {"file": {"download_url": "inert-url"}}, "inert-url"),
            (lambda value: video.call_api(value, method="GET"), "read-only", {"value": 1}, {"value": 1}),
        )

    def test_safe_reads_recover_from_transient_http_and_network_errors(self):
        for function, value, body, expected in self.read_cases():
            for status in (429, 500, 502, 503, 504, None):
                with self.subTest(reader=function.__name__, status=status):
                    failure = http_error(status) if status else urllib.error.URLError("inert reset")
                    self.reset_transport([failure, Response(body)])
                    self.assertEqual(function(value), expected)
                    self.assertEqual(self.transport.call_count, 2)
                    self.assertTrue(all(c.args[0].get_method() == "GET"
                                        for c in self.transport.call_args_list))
                    self.sleep.assert_called_once_with(1)

    def test_safe_reads_stop_after_three_attempts(self):
        for function, value, _, _ in self.read_cases():
            for kind in ("http", "network"):
                with self.subTest(reader=function.__name__, kind=kind):
                    failures = ([http_error(503) for _ in range(3)] if kind == "http" else
                                [urllib.error.URLError("inert reset") for _ in range(3)])
                    self.reset_transport(failures)
                    code = video.EXIT_API_ERROR if kind == "http" else video.EXIT_NETWORK_ERROR
                    self.assert_exit(code, function, value)
                    self.assertEqual(self.transport.call_count, 3)
                    self.assertEqual(self.sleep.call_args_list, [call(1), call(2)])

    def test_safe_read_retry_after_is_capped(self):
        self.transport.side_effect = [http_error(503, {"Retry-After": "999999"}),
                                      Response({"status": "Processing"})]
        video.query_task("known-task")
        self.sleep.assert_called_once_with(video.MAX_RETRY_AFTER)

    def test_safe_read_timeouts_still_stop_without_retry(self):
        for failure in (socket.timeout("inert timeout"),
                        urllib.error.URLError(socket.timeout("inert timeout"))):
            with self.subTest(failure=repr(failure)):
                self.reset_transport(failure)
                self.assert_exit(video.EXIT_NETWORK_ERROR, video.query_task, "known-task")
                self.assertEqual(self.transport.call_count, 1)
                self.sleep.assert_not_called()

    def test_download_and_validated_redirect_retain_get_retries(self):
        for redirected in (False, True):
            with self.subTest(redirected=redirected), tempfile.TemporaryDirectory() as directory:
                effects = [http_error(503), Response(b"inert-video-bytes")]
                if redirected:
                    effects.insert(0, http_error(302, {"Location": "https://cdn.minimax.io/inert.mp4"}))
                self.reset_transport(effects)
                output = Path(directory) / "video.mp4"
                video.download_url("https://cdn.minimax.io/source.mp4", str(output))
                self.assertEqual(output.read_bytes(), b"inert-video-bytes")
                self.assertEqual(self.transport.call_count, 3 if redirected else 2)
                self.assertTrue(all(c.args[0].get_method() == "GET"
                                    for c in self.transport.call_args_list))
                self.sleep.assert_called_once_with(1)

    def test_download_retry_exhaustion_leaves_no_output(self):
        self.transport.side_effect = [http_error(503) for _ in range(3)]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "video.mp4"
            self.assert_exit(video.EXIT_API_ERROR, video.download_url,
                             "https://cdn.minimax.io/inert.mp4", str(output))
            self.assertEqual(list(Path(directory).iterdir()), [])
        self.assertEqual(self.transport.call_count, 3)
        self.assertEqual(self.sleep.call_args_list, [call(1), call(2)])

    def test_known_task_survives_failed_sync_poll_and_recovers_without_new_post(self):
        self.transport.side_effect = [
            Response({"task_id": "known-task", "base_resp": {"status_code": 0}}),
            *[http_error(503) for _ in range(3)],
        ]
        self.assert_exit(video.EXIT_API_ERROR, video.generate_video, generation_args(sync=True))
        message = self.stderr.getvalue()
        self.assertIn("known-task", message)
        self.assertIn("retrieve --task-id known-task", message)
        self.assertLess(message.index("known-task"), message.index("Retrying"))
        self.assertEqual(self.stdout.getvalue(), "")

        self.transport.side_effect = [
            Response({"status": "Success", "file_id": "known-file"}),
            Response({"file": {"download_url": "https://cdn.minimax.io/inert.mp4"}}),
            Response(b"inert-video-bytes"),
        ]
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"OUTPUT_DIR": directory}):
            video.retrieve_video(SimpleNamespace(task_id="known-task", sync=False, verbose=False, timeout=7))
            output = Path(self.stdout.getvalue().strip())
            self.assertEqual(output.parent, Path(directory))
            self.assertEqual(output.read_bytes(), b"inert-video-bytes")
        requests = [c.args[0] for c in self.transport.call_args_list]
        self.assertEqual([request.get_method() for request in requests], ["POST"] + ["GET"] * 6)
        self.assertTrue(all("task_id=known-task" in request.full_url for request in requests[1:5]))

    def test_known_task_in_error_responses_remains_visible(self):
        body = {"task_id": "known-task", "base_resp": {"status_code": 1026}}
        responses = (Response(body), Response({"task_id": "known-task", "base_resp": None}),
                     Response({"task_id": "known-task"}),
                     http_error(500, body=json.dumps(body).encode()))
        for response in responses:
            with self.subTest(response=type(response).__name__):
                self.reset_transport([response])
                self.assert_exit(video.EXIT_API_ERROR, video.generate_video, generation_args())
                self.assert_single_submission()
                self.assertIn("Task ID: known-task", self.stderr.getvalue())
                self.assertIn("retrieve --task-id known-task", self.stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
