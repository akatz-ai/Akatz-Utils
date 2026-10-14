"""YouTube clip extraction utilities."""

from __future__ import annotations

import math
import os
import re
import subprocess
import tempfile
import threading
from collections.abc import Iterator
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Literal

import yt_dlp
from .chunked import ChunkedInputs

ClipFormat = Literal["mp3", "flac", "mp4"]
MediaKind = Literal["audio", "video", "combined", "unknown"]

CHUNK_SIZE = 8192
MAX_CLIP_DURATION = 21600
MIN_CLIP_DURATION = 0.5
YOUTUBE_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?.*v=|shorts/)|youtu\.be/)([a-zA-Z0-9_-]{11})"
)


@dataclass(frozen=True)
class MediaInput:
    """A direct media URL and input-scoped ffmpeg metadata."""

    url: str
    headers: dict[str, str]
    kind: MediaKind = "unknown"


def extract_video_id(url: str) -> str:
    """Return a YouTube video id from supported YouTube URLs."""
    match = YOUTUBE_RE.search(url)
    if not match:
        raise ValueError("Invalid YouTube URL")
    return match.group(1)


def validate_time_range(start: float, end: float) -> None:
    """Validate a requested clip range."""
    if not math.isfinite(start) or not math.isfinite(end):
        raise ValueError("Enter finite start and end times")
    if start < 0:
        raise ValueError("Start time must be non-negative")
    if end <= start:
        raise ValueError("End time must be after start time")

    duration = end - start
    if duration < MIN_CLIP_DURATION:
        raise ValueError(f"Clip must be at least {MIN_CLIP_DURATION}s")
    if duration > MAX_CLIP_DURATION:
        raise ValueError("Clip must be at most 6 hours")


def sanitize_title(title: str) -> str:
    """Sanitize a video title for use as a download filename."""
    return re.sub(r'[\\/:*?"<>|]', "", title).strip() or "clip"


def _headers_for(
    format_info: dict,
    fallback_headers: dict[str, str],
) -> dict[str, str]:
    return dict(format_info.get("http_headers") or fallback_headers)


def _kind_for(format_info: dict) -> MediaKind:
    has_video = format_info.get("vcodec") not in {None, "none"}
    has_audio = format_info.get("acodec") not in {None, "none"}
    if has_video and has_audio:
        return "combined"
    if has_video:
        return "video"
    if has_audio:
        return "audio"
    return "unknown"


def _media_inputs_from_info(info: dict, fmt: ClipFormat) -> list[MediaInput]:
    fallback_headers = dict(info.get("http_headers") or {})

    if fmt == "mp4":
        requested_formats = info.get("requested_formats") or []
        media_inputs = [
            MediaInput(
                format_info["url"],
                _headers_for(format_info, fallback_headers),
                _kind_for(format_info),
            )
            for format_info in requested_formats
            if format_info.get("url") and _kind_for(format_info) != "unknown"
        ]
        if media_inputs:
            return media_inputs

    if not info.get("url"):
        raise ValueError("Could not resolve a downloadable media URL")

    return [MediaInput(info["url"], fallback_headers, _kind_for(info))]


def extract_media_sources(
    youtube_url: str,
    fmt: ClipFormat,
    *,
    player_client: str | None = None,
) -> tuple[list[MediaInput], str]:
    """Extract source stream URLs and a sanitized title."""
    yt_format = "bestaudio/best"
    if fmt == "mp4":
        yt_format = (
            "bestvideo[vcodec!=none]+bestaudio[acodec!=none]/"
            "best[vcodec!=none][acodec!=none]/best"
        )

    opts = {
        "format": yt_format,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "js_runtimes": {"node": {}, "deno": {}},
        "cachedir": os.path.join(tempfile.gettempdir(), "akatz-ytdlp-cache"),
        "socket_timeout": 30,
    }
    if player_client is not None:
        opts["extractor_args"] = {
            "youtube": {"player_client": [player_client]},
        }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
    except yt_dlp.DownloadError as primary_error:
        # Some videos currently expose only a direct Android-client format.
        # Keep the normal client selection first because it generally provides
        # better quality, then retry this specific availability failure with
        # the Android client (which avoids the Android VR proof-token path).
        if (
            player_client is not None
            or "This video is not available" not in str(primary_error)
        ):
            raise

        fallback_opts = {
            **opts,
            "extractor_args": {"youtube": {"player_client": ["android"]}},
        }
        with yt_dlp.YoutubeDL(fallback_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)

    if info is None:
        raise ValueError("Could not load YouTube metadata")

    if info.get("is_live"):
        raise ValueError("Live streams are not supported")

    return (
        _media_inputs_from_info(info, fmt),
        sanitize_title(info.get("title", "clip")),
    )


def extract_video_metadata(youtube_url: str) -> dict[str, str | float]:
    """Return the title and duration without relying on YouTube's embed player."""
    opts = {
        "format": "bestvideo[vcodec!=none]+bestaudio[acodec!=none]/best[vcodec!=none][acodec!=none]/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "js_runtimes": {"node": {}, "deno": {}},
        "cachedir": os.path.join(tempfile.gettempdir(), "akatz-ytdlp-cache"),
        "socket_timeout": 30,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
    except yt_dlp.DownloadError as primary_error:
        if "This video is not available" not in str(primary_error):
            raise
        opts["extractor_args"] = {"youtube": {"player_client": ["android"]}}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)

    if not info or info.get("is_live"):
        raise ValueError("Could not load video metadata")
    duration = info.get("duration")
    if not isinstance(duration, (int, float)) or duration <= 0:
        raise ValueError("Video duration is unavailable")
    return {"title": info.get("title") or "Video", "duration": duration}


def extract_media_url(
    youtube_url: str,
    fmt: ClipFormat,
) -> tuple[str, str, dict[str, str]]:
    """Extract the first source stream URL, sanitized title, and HTTP headers."""
    media_inputs, title = extract_media_sources(youtube_url, fmt)
    source = media_inputs[0]
    return source.url, title, source.headers


def _coerce_media_inputs(
    media: str | list[MediaInput],
    headers: dict[str, str] | None = None,
) -> list[MediaInput]:
    if isinstance(media, str):
        return [MediaInput(media, headers or {}, "combined")]
    return media


def _headers_args(headers: dict[str, str]) -> list[str]:
    if not headers:
        return []

    header_str = "".join(f"{key}: {value}\r\n" for key, value in headers.items())
    return ["-headers", header_str]


def _first_input_with(media_inputs: list[MediaInput], kind: MediaKind) -> int | None:
    for index, media_input in enumerate(media_inputs):
        if media_input.kind in {kind, "combined", "unknown"}:
            return index
    return None


def _build_ffmpeg_args(
    media: str | list[MediaInput],
    start: float,
    duration: float,
    fmt: ClipFormat,
    headers: dict[str, str] | None = None,
    *, copy_video: bool = False,
) -> list[str]:
    media_inputs = _coerce_media_inputs(media, headers)
    args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin"]

    for media_input in media_inputs:
        args += _headers_args(media_input.headers)
        args += ["-rw_timeout", "30000000", "-threads", os.environ.get("AKATZ_FFMPEG_THREADS", "0"),
                 "-ss", str(start), "-i", media_input.url]

    args += ["-t", str(duration)]
    if fmt == "mp3":
        args += ["-vn", "-acodec", "libmp3lame", "-q:a", "2", "-f", "mp3"]
    elif fmt == "flac":
        args += ["-vn", "-acodec", "flac", "-f", "flac"]
    else:
        video_input_index = _first_input_with(media_inputs, "video")
        if video_input_index is None:
            raise ValueError("Selected media has no video stream")

        audio_input_index = _first_input_with(media_inputs, "audio")
        args += [
            "-map", f"{video_input_index}:v:0",
        ]
        if audio_input_index is not None:
            args += ["-map", f"{audio_input_index}:a:0?"]

        if copy_video:
            args += ["-c:v", "copy", "-avoid_negative_ts", "make_zero"]
        else:
            args += ["-c:v", "libx264", "-preset", os.environ.get("AKATZ_FFMPEG_PRESET", "medium"),
                     "-crf", "18", "-pix_fmt", "yuv420p"]
        args += [
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "frag_keyframe+empty_moov",
            "-f", "mp4",
        ]
    args += ["-threads", os.environ.get("AKATZ_FFMPEG_THREADS", "0"), "pipe:1"]
    return args


def iter_clip(
    media: str | list[MediaInput],
    start: float,
    duration: float,
    fmt: ClipFormat,
    headers: dict[str, str] | None = None,
    *, copy_video: bool = False, cancel_event: threading.Event | None = None,
) -> Iterator[bytes]:
    """Run ffmpeg and yield encoded clip chunks."""
    # A pipe can fill with errors while stdout is being consumed, deadlocking
    # a long encode. Keep stderr in disk-backed scratch instead.
    if cancel_event is not None and cancel_event.is_set():
        raise InterruptedError("Clip cancelled")
    errors = tempfile.TemporaryFile()
    try:
        proc = subprocess.Popen(
            _build_ffmpeg_args(media, start, duration, fmt, headers, copy_video=copy_video),
            stdout=subprocess.PIPE,
            stderr=errors,
        )
    except Exception:
        errors.close()
        raise
    assert proc.stdout is not None
    finished = threading.Event()
    watcher = None
    if cancel_event is not None:
        def stop_on_cancel():
            while not finished.wait(0.1):
                if cancel_event.is_set():
                    try:
                        proc.kill()
                    except ProcessLookupError:
                        pass
                    return
        watcher = threading.Thread(target=stop_on_cancel, daemon=True)
        watcher.start()

    try:
        while True:
            chunk = proc.stdout.read(CHUNK_SIZE)
            if cancel_event is not None and cancel_event.is_set():
                raise InterruptedError("Clip cancelled")
            if not chunk:
                break
            yield chunk

        returncode = proc.wait()
        if cancel_event is not None and cancel_event.is_set():
            raise InterruptedError("Clip cancelled")
        if returncode != 0:
            errors.seek(0)
            stderr = errors.read(16384).decode(errors="replace")
            raise RuntimeError(f"ffmpeg failed: {stderr}")
    finally:
        finished.set()
        if watcher is not None:
            watcher.join()
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        proc.stdout.close()
        errors.close()


def iter_youtube_clip(
    youtube_url: str,
    media: list[MediaInput],
    start: float,
    duration: float,
    fmt: ClipFormat,
    *, copy_video: bool = False, cancel_event: threading.Event | None = None,
) -> Iterator[bytes]:
    """Encode a clip, recovering from unopened Google media URLs when possible."""
    current_media = media
    emitted_output = False

    # A fresh default extraction usually preserves the requested quality. The
    # Android client is the final fallback because it is broadly accessible but
    # can expose only a lower-resolution combined stream for some videos.
    retry_clients: tuple[str | None, ...] = (None, "android")

    for attempt in range(len(retry_clients) + 1):
        if cancel_event is not None and cancel_event.is_set():
            raise InterruptedError("Clip cancelled")
        if attempt:
            current_media, _ = extract_media_sources(
                youtube_url,
                fmt,
                player_client=retry_clients[attempt - 1],
            )

        try:
            inputs = ChunkedInputs(current_media, cancel_event) if copy_video and fmt == "mp4" else nullcontext(current_media)
            with inputs as download_media:
                for chunk in iter_clip(download_media, start, duration, fmt, copy_video=copy_video, cancel_event=cancel_event):
                    emitted_output = True
                    yield chunk
            return
        except RuntimeError as error:
            access_denied = (
                "403 Forbidden" in str(error)
                or "access denied" in str(error).lower()
            )
            if emitted_output or not access_denied or attempt == len(retry_clients):
                raise
