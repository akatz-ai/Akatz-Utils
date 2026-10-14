"""Seekable loopback media inputs backed by bounded upstream HTTP ranges."""

from __future__ import annotations

import re
import threading
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import requests

RANGE_SIZE = 2 * 1024 * 1024
PREFETCH = 2


class RangeUnsupported(Exception):
    """The source needs the original streaming downloader."""


class ChunkedInputs:
    """Serve FFmpeg's seeks using small, validated, cancellable range requests.

    Only requested ranges and two chunks of lookahead are fetched. Buffers are
    bounded; no full source files or local-disk download caches are created.
    """

    def __init__(self, media, cancel_event=None):
        self.media = media
        self.cancel = cancel_event
        self.stopped = threading.Event()
        self.sessions = []
        self.sessions_lock = threading.Lock()
        self.local = threading.local()
        self.errors = []
        self.sources = []
        self.server = None
        self.thread = None
        self.executor = None

    def check_cancelled(self, aborted=None):
        if self.stopped.is_set() or (self.cancel is not None and self.cancel.is_set()) or (aborted is not None and aborted.is_set()):
            raise InterruptedError("Clip cancelled")

    def session(self):
        if not hasattr(self.local, "session"):
            self.local.session = requests.Session()
            with self.sessions_lock:
                self.sessions.append(self.local.session)
        return self.local.session

    def fetch(self, source, start, end, aborted=None):
        self.check_cancelled(aborted)
        if start < len(source['prefix']) and end < len(source['prefix']):
            return source['prefix'][start:end + 1]
        headers = {**source['media'].headers, 'Accept-Encoding': 'identity', 'Range': f'bytes={start}-{end}'}
        for attempt in range(3):
            self.check_cancelled(aborted)
            try:
                with self.session().get(source['media'].url, headers=headers, stream=True, timeout=(3, 2)) as response:
                    if any(kind in response.headers.get('Content-Type', '').lower() for kind in ('mpegurl', 'dash+xml')):
                        raise RangeUnsupported("Playlist source requires the streaming downloader")
                    if response.status_code in {401, 403}:
                        raise RuntimeError("403 Forbidden fetching YouTube media")
                    if response.status_code == 200:
                        length = response.headers.get('Content-Length', '')
                        if start != 0 or not length.isdigit() or int(length) > end + 1:
                            raise RangeUnsupported("Source does not support bounded ranges")
                        total = int(length)
                        actual_end = total - 1
                    elif response.status_code == 206:
                        match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', response.headers.get('Content-Range', ''))
                        if not match:
                            raise RangeUnsupported("Source has no valid range length")
                        actual_start, actual_end, total = map(int, match.groups())
                        if actual_start != start or actual_end != min(end, total - 1):
                            raise RuntimeError("YouTube returned an incorrect media range")
                    else:
                        response.raise_for_status()
                    if source.get('size') is not None and total != source['size']:
                        raise RuntimeError("YouTube media changed during download")
                    if total <= 0 or response.headers.get('Content-Encoding', 'identity') != 'identity':
                        raise RangeUnsupported("Source cannot be served as a byte range")
                    data = bytearray()
                    for chunk in response.iter_content(64 * 1024):
                        self.check_cancelled(aborted)
                        data.extend(chunk)
                        if len(data) > end - start + 1:
                            raise RuntimeError("YouTube returned more than the requested range")
                    if len(data) != actual_end - start + 1:
                        raise RuntimeError("YouTube returned an incomplete media range")
                    source['size'] = total
                    return bytes(data)
            except requests.RequestException:
                self.check_cancelled(aborted)
                if attempt == 2:
                    raise RuntimeError("Could not download a YouTube media chunk") from None
                if self.stopped.wait(0.2):
                    self.check_cancelled(aborted)

    def __enter__(self):
        try:
            for media in self.media:
                if not media.url.startswith(('https://', 'http://')):
                    raise RangeUnsupported("Not an HTTP media input")
                if urlsplit(media.url).path.lower().endswith(('.m3u8', '.mpd')):
                    raise RangeUnsupported("Playlist source requires the streaming downloader")
                source = dict(media=media, prefix=b'', size=None)
                source['prefix'] = self.fetch(source, 0, RANGE_SIZE - 1)
                self.sources.append(source)
            self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix='clip-range')
            token = uuid.uuid4().hex
            owner = self

            class Handler(BaseHTTPRequestHandler):
                protocol_version = 'HTTP/1.1'

                def log_message(self, *args):
                    pass

                def handle(self):
                    try:
                        super().handle()
                    except (ConnectionResetError, BrokenPipeError):
                        pass

                def do_HEAD(self):
                    self.serve(head=True)

                def do_GET(self):
                    self.serve()

                def serve(self, head=False):
                    match = re.fullmatch('/' + token + r'/(\d+)', self.path)
                    if not match or int(match[1]) >= len(owner.sources):
                        self.send_error(404)
                        return
                    source = owner.sources[int(match[1])]
                    size = source['size']
                    start, end = 0, size - 1
                    ranged = self.headers.get('Range')
                    if ranged:
                        bounds = re.fullmatch(r'bytes=(\d*)-(\d*)', ranged)
                        if not bounds or not any(bounds.groups()):
                            self.send_error(416)
                            return
                        if bounds[1]:
                            start = int(bounds[1])
                            if bounds[2]:
                                end = min(end, int(bounds[2]))
                        else:
                            start = max(0, size - int(bounds[2]))
                        if start > end:
                            self.send_response(416)
                            self.send_header('Content-Range', f'bytes */{size}')
                            self.send_header('Content-Length', '0')
                            self.end_headers()
                            return
                    aborted = threading.Event()
                    pending = deque()
                    cursor = start

                    def schedule():
                        nonlocal cursor
                        owner.check_cancelled(aborted)
                        while not head and cursor <= end and len(pending) < PREFETCH:
                            limit = min(end, cursor + RANGE_SIZE - 1)
                            pending.append(owner.executor.submit(owner.fetch, source, cursor, limit, aborted))
                            cursor = limit + 1

                    try:
                        schedule()
                        # Validate the first chunk before committing response headers.
                        first = pending.popleft().result() if pending else None
                        self.send_response(206 if ranged else 200)
                        self.send_header('Accept-Ranges', 'bytes')
                        self.send_header('Content-Type', 'application/octet-stream')
                        self.send_header('Content-Length', str(end - start + 1))
                        if ranged:
                            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
                        self.end_headers()
                        if first is not None:
                            self.wfile.write(first)
                        schedule()
                        while pending:
                            owner.check_cancelled(aborted)
                            self.wfile.write(pending.popleft().result())
                            schedule()
                    except (BrokenPipeError, ConnectionResetError, InterruptedError):
                        self.close_connection = True
                    except Exception as error:
                        if not owner.stopped.is_set() and not aborted.is_set():
                            owner.errors.append(error)
                        self.close_connection = True
                    finally:
                        aborted.set()
                        for future in pending:
                            future.cancel()

            self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            self.server.daemon_threads = True
            self.server.block_on_close = False
            self.thread = threading.Thread(target=lambda: self.server.serve_forever(poll_interval=0.1), daemon=True)
            self.thread.start()
            port = self.server.server_address[1]
            return [replace(media, url=f'http://127.0.0.1:{port}/{token}/{index}', headers={}) for index, media in enumerate(self.media)]
        except RangeUnsupported:
            self.close()
            return self.media
        except Exception:
            self.close()
            raise

    def close(self):
        self.stopped.set()
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join()
        if self.executor is not None:
            self.executor.shutdown(wait=True, cancel_futures=True)
        for session in self.sessions:
            session.close()

    def __exit__(self, error_type, error, traceback):
        self.close()
        if self.errors and (error is None or isinstance(error, RuntimeError)):
            raise RuntimeError(str(self.errors[0])) from error
