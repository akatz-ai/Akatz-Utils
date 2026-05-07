"""YouTube clip extraction utilities."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Iterator
from typing import Literal

import yt_dlp

ClipFormat = Literal["mp3", "flac", "mp4"]

CHUNK_SIZE = 8192
MAX_CLIP_DURATION = 600
MIN_CLIP_DURATION = 0.5
YOUTUBE_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?.*v=|shorts/)|youtu\.be/)([a-zA-Z0-9_-]{11})"
)


def extract_video_id(url: str) -> str:
    """Return a YouTube video id from supported YouTube URLs."""
    match = YOUTUBE_RE.search(url)
    if not match:
        raise ValueError("Invalid YouTube URL")
    return match.group(1)


def validate_time_range(start: float, end: float) -> None:
    """Validate a requested clip range."""
    if start < 0:
        raise ValueError("Start time must be non-negative")
    if end <= start:
        raise ValueError("End time must be after start time")

    duration = end - start
    if duration < MIN_CLIP_DURATION:
        raise ValueError(f"Clip must be at least {MIN_CLIP_DURATION}s")
    if duration > MAX_CLIP_DURATION:
        raise ValueError("Clip must be at most 600s (10 minutes)")


def sanitize_title(title: str) -> str:
    """Sanitize a video title for use as a download filename."""
    return re.sub(r'[\\/:*?"<>|]', "", title).strip() or "clip"


def extract_media_url(
    youtube_url: str,
    fmt: ClipFormat,
) -> tuple[str, str, dict[str, str]]:
    """Extract a source stream URL, sanitized title, and HTTP headers."""
    yt_format = "bestaudio/best"
    if fmt == "mp4":
        yt_format = (
            "best[ext=mp4][vcodec!=none][acodec!=none]/"
            "best[vcodec!=none][acodec!=none]/best"
        )

    opts = {
        "format": yt_format,
        "extractor_args": {
            "youtube": {
                "player_client": ["web", "ios", "android"],
            },
        },
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(youtube_url, download=False)
        if info is None:
            raise ValueError("Could not load YouTube metadata")

    if info.get("is_live"):
        raise ValueError("Live streams are not supported")

    return (
        info["url"],
        sanitize_title(info.get("title", "clip")),
        info.get("http_headers", {}),
    )


def _build_ffmpeg_args(
    media_url: str,
    start: float,
    duration: float,
    fmt: ClipFormat,
    headers: dict[str, str] | None = None,
) -> list[str]:
    args = ["ffmpeg", "-hide_banner", "-loglevel", "error"]
    if headers:
        header_str = "".join(f"{key}: {value}\r\n" for key, value in headers.items())
        args += ["-headers", header_str]

    args += ["-ss", str(start), "-i", media_url, "-t", str(duration)]
    if fmt == "mp3":
        args += ["-vn", "-acodec", "libmp3lame", "-q:a", "2", "-f", "mp3"]
    elif fmt == "flac":
        args += ["-vn", "-acodec", "flac", "-f", "flac"]
    else:
        args += [
            "-map", "0:v:0",
            "-map", "0:a:0?",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "160k",
            "-movflags", "frag_keyframe+empty_moov",
            "-f", "mp4",
        ]
    args.append("pipe:1")
    return args


def iter_clip(
    media_url: str,
    start: float,
    duration: float,
    fmt: ClipFormat,
    headers: dict[str, str] | None = None,
) -> Iterator[bytes]:
    """Run ffmpeg and yield encoded clip chunks."""
    proc = subprocess.Popen(
        _build_ffmpeg_args(media_url, start, duration, fmt, headers),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.stdout is not None
    assert proc.stderr is not None

    try:
        while True:
            chunk = proc.stdout.read(CHUNK_SIZE)
            if not chunk:
                break
            yield chunk

        returncode = proc.wait()
        if returncode != 0:
            stderr = proc.stderr.read().decode(errors="replace")
            raise RuntimeError(f"ffmpeg failed: {stderr}")
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
