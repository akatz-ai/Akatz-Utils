"""Regression checks for failures during clip encoding."""

import tempfile
import unittest
from unittest.mock import patch

from flask import Flask
from launcher.routes.ytclipper import bp


class ClipDownloadTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.register_blueprint(bp)
        self.app.testing = True
        self.client = self.app.test_client()
        self.extraction = patch(
            "launcher.routes.ytclipper.extract_media_sources",
            return_value=([], "Clip 🎬"),
        )
        self.extraction.start()
        self.addCleanup(self.extraction.stop)
        self.payload = {
            "url": "https://youtu.be/Z8OgpJ4u7ZQ", "start": 303, "end": 338,
            "format": "mp4",
        }

    def test_success_returns_complete_attachment_and_closes_file(self):
        clip = tempfile.TemporaryFile(mode="w+b")
        self.addCleanup(clip.close)
        with patch("launcher.routes.ytclipper.tempfile.TemporaryFile", return_value=clip), patch(
            "launcher.routes.ytclipper.iter_youtube_clip", return_value=iter([b"first", b"second"]),
        ):
            response = self.client.post("/api/ytclipper/clip", json=self.payload)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, b"firstsecond")
            self.assertEqual(response.content_length, 11)
            self.assertEqual(response.mimetype, "video/mp4")
            self.assertIn("filename*=UTF-8''", response.headers["Content-Disposition"])
            response.close()
            self.assertTrue(clip.closed)

    def test_dns_failure_returns_readable_json_and_closes_file(self):
        def failing_encoder():
            raise RuntimeError("ffmpeg failed: Failed to resolve hostname media.example: System error")
            yield

        self.assert_encoding_failure(failing_encoder(), "Could not resolve YouTube's media server")

    def test_failure_after_output_does_not_download_a_partial_file(self):
        def failing_encoder():
            yield b"partial MP4"
            raise RuntimeError("ffmpeg failed after writing output")

        self.assert_encoding_failure(failing_encoder(), "Could not create the clip")

    def test_empty_output_returns_json_error(self):
        self.assert_encoding_failure(iter([]), "Could not create the clip")

    def assert_encoding_failure(self, chunks, message):
        clip = tempfile.TemporaryFile(mode="w+b")
        self.addCleanup(clip.close)
        with patch("launcher.routes.ytclipper.tempfile.TemporaryFile", return_value=clip), patch(
            "launcher.routes.ytclipper.iter_youtube_clip", return_value=chunks,
        ), self.assertLogs(self.app.logger, level="ERROR"):
            response = self.client.post("/api/ytclipper/clip", json=self.payload)
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.mimetype, "application/json")
        self.assertIn(message, response.json["error"])
        self.assertNotIn("Content-Disposition", response.headers)
        self.assertTrue(clip.closed)


if __name__ == "__main__":
    unittest.main()
