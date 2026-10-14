"""Range correctness, seeking, cancellation and bounded source downloads."""

import re
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

from ytclipper import MediaInput
from ytclipper.chunked import ChunkedInputs, RANGE_SIZE


class ChunkedMediaTests(unittest.TestCase):
    def setUp(self):
        self.payload = bytes(range(256)) * (RANGE_SIZE // 256 * 5)
        self.ranges = []
        self.ignore_ranges = False
        self.bad_range = False
        self.fail_once = False
        owner = self

        class Origin(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def log_message(self, *args):
                pass

            def handle(self):
                try:
                    super().handle()
                except (ConnectionResetError, BrokenPipeError):
                    pass

            def do_GET(self):
                if self.headers.get('X-Media-Header') != 'preserved':
                    self.send_error(403)
                    return
                bounds = re.fullmatch(r'bytes=(\d+)-(\d+)', self.headers.get('Range', ''))
                if not bounds:
                    self.send_error(400)
                    return
                start, end = map(int, bounds.groups())
                owner.ranges.append((start, end))
                if owner.fail_once:
                    owner.fail_once = False
                    self.send_error(503)
                    return
                if owner.ignore_ranges:
                    self.send_response(200)
                    self.send_header('Content-Length', str(len(owner.payload)))
                    self.end_headers()
                    return
                end = min(end, len(owner.payload) - 1)
                body = owner.payload[start:end+1]
                self.send_response(206)
                self.send_header('Content-Range', f'bytes {start + int(owner.bad_range)}-{end}/{len(owner.payload)}')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        self.origin = ThreadingHTTPServer(('127.0.0.1', 0), Origin)
        self.origin.daemon_threads = True
        self.thread = threading.Thread(target=self.origin.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_origin)
        self.media = [MediaInput(f'http://127.0.0.1:{self.origin.server_port}/video', {'X-Media-Header': 'preserved'}, 'video')]

    def close_origin(self):
        self.origin.shutdown()
        self.origin.server_close()
        self.thread.join()

    def test_full_stream_matches_and_every_upstream_request_is_bounded(self):
        self.fail_once = True
        with ChunkedInputs(self.media) as inputs:
            response = requests.get(inputs[0].url, timeout=5)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, self.payload)
        self.assertGreater(len(self.ranges), 5)
        self.assertTrue(all(end-start+1 <= RANGE_SIZE for start, end in self.ranges))

    def test_seek_range_suffix_and_head_do_not_fetch_entire_source(self):
        with ChunkedInputs(self.media) as inputs:
            url = inputs[0].url
            response = requests.head(url, timeout=5)
            self.assertEqual(int(response.headers['Content-Length']), len(self.payload))
            response = requests.get(url, headers={'Range': 'bytes=3145728-3162111'}, timeout=5)
            self.assertEqual(response.status_code, 206)
            self.assertEqual(response.content, self.payload[3145728:3162112])
            response = requests.get(url, headers={'Range': 'bytes=-128'}, timeout=5)
            self.assertEqual(response.content, self.payload[-128:])
            response = requests.get(url, headers={'Range': f'bytes={len(self.payload)}-'}, timeout=5)
            self.assertEqual(response.status_code, 416)
        self.assertLess(sum(end-start+1 for start,end in self.ranges), len(self.payload))

    def test_ignored_ranges_fall_back_without_reading_a_large_body(self):
        self.ignore_ranges = True
        with ChunkedInputs(self.media) as inputs:
            self.assertIs(inputs, self.media)
        self.assertEqual(len(self.ranges), 1)

    def test_incorrect_range_is_rejected(self):
        self.bad_range = True
        with self.assertRaisesRegex(RuntimeError, 'incorrect media range'):
            with ChunkedInputs(self.media):
                pass

    def test_later_source_failure_cannot_be_mistaken_for_success(self):
        with self.assertRaisesRegex(RuntimeError, 'incorrect media range'):
            with ChunkedInputs(self.media) as inputs:
                self.bad_range = True
                with self.assertRaises(requests.RequestException):
                    requests.get(inputs[0].url, headers={'Range': f'bytes={RANGE_SIZE}-'}, timeout=5)

    def test_stop_download_after_small_selection_bounds_lookahead(self):
        proxy = ChunkedInputs(self.media)
        with proxy as inputs:
            with requests.get(inputs[0].url, stream=True, timeout=5) as response:
                next(response.iter_content(1024))
        self.assertLessEqual(sum(end-start+1 for start,end in self.ranges), RANGE_SIZE * 4)
        self.assertTrue(all(not worker.is_alive() for worker in proxy.executor._threads))

    def test_cancel_and_context_cleanup_stop_download_threads(self):
        cancel = threading.Event()
        proxy = ChunkedInputs(self.media, cancel)
        with proxy as inputs:
            cancel.set()
            with self.assertRaises(InterruptedError):
                proxy.fetch(proxy.sources[0], RANGE_SIZE, RANGE_SIZE*2-1)
        self.assertFalse(proxy.thread.is_alive())
        self.assertTrue(all(not worker.is_alive() for worker in proxy.executor._threads))

    def test_playlist_inputs_use_original_streaming_path(self):
        media = [MediaInput('https://example.test/video.m3u8', {}, 'combined')]
        with ChunkedInputs(media) as inputs:
            self.assertIs(inputs, media)
