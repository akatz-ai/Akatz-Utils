"""Extract still frames from uploaded MP4 files or YouTube videos."""

from __future__ import annotations

import math
import os
import json
import subprocess
import tempfile
import threading
import time
import uuid
from fractions import Fraction
from io import BytesIO
from pathlib import Path

import yt_dlp
from flask import Blueprint, jsonify, render_template, request, send_file
from ytclipper import extract_video_id
from werkzeug.utils import secure_filename

bp = Blueprint("frameclipper", __name__)

_upload_dir = tempfile.TemporaryDirectory(prefix="akatz-frameclipper-")
_uploads: dict[str, dict] = {}
_uploads_lock = threading.Lock()
_upload_ttl = 60 * 60
_youtube_cache: dict[tuple[str, str | None], tuple[float, dict]] = {}
_youtube_lock = threading.Lock()
_youtube_cache_ttl = 120


def _probe_local(path: str) -> dict:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=index,codec_type,width,height,avg_frame_rate",
         "-of", "json", path],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    info = json.loads(result.stdout)
    stream = next((item for item in info.get("streams", []) if item.get("codec_type") == "video"), None)
    if not stream:
        raise ValueError("This file has no video stream")
    duration = float(info.get("format", {}).get("duration") or 0)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Could not determine video duration")
    rate = stream.get("avg_frame_rate") or "0/1"
    fps = float(Fraction(rate)) if rate != "0/0" else 0
    return {
        "duration": duration,
        "fps": fps if math.isfinite(fps) and fps > 0 else 0,
        "width": stream["width"],
        "height": stream["height"],
    }


def _youtube_info(url: str, client: str | None = None) -> tuple[dict, dict]:
    opts = {
        "format": "bestvideo[vcodec!=none]/best[vcodec!=none]",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "js_runtimes": {"node": {}, "deno": {}},
        "cachedir": os.path.join(tempfile.gettempdir(), "akatz-ytdlp-cache"),
        "socket_timeout": 30,
    }
    if client:
        opts["extractor_args"] = {"youtube": {"player_client": [client]}}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info or info.get("is_live"):
        raise ValueError("This video cannot be used for frame capture")
    chosen = info.get("requested_formats") or [info]
    video = next((item for item in chosen if item.get("vcodec") not in (None, "none") and item.get("url")), None)
    if not video:
        raise ValueError("No downloadable video stream is available")
    return info, video


def _youtube_details(url: str, client: str | None = None, *, refresh: bool = False) -> dict:
    url = f"https://www.youtube.com/watch?v={extract_video_id(url)}"
    cache_key = (url, client)
    with _youtube_lock:
        cached = _youtube_cache.get(cache_key)
        if not refresh and cached and time.monotonic() - cached[0] < _youtube_cache_ttl:
            return dict(cached[1])
    try:
        info, video = _youtube_info(url, client)
    except yt_dlp.DownloadError as error:
        if client is not None or "This video is not available" not in str(error):
            raise
        info, video = _youtube_info(url, "android")
    duration = float(info.get("duration") or 0)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Could not determine video duration")
    details = {
        "title": info.get("title") or "YouTube video",
        "duration": duration,
        "fps": float(video.get("fps") or info.get("fps") or 0),
        "width": video.get("width") or info.get("width"),
        "height": video.get("height") or info.get("height"),
        "source_url": video["url"],
        "headers": video.get("http_headers") or info.get("http_headers") or {},
    }
    with _youtube_lock:
        stale = [key for key, (saved_at, _) in _youtube_cache.items()
                 if time.monotonic() - saved_at >= _youtube_cache_ttl]
        for key in stale:
            del _youtube_cache[key]
        _youtube_cache[cache_key] = (time.monotonic(), details)
    return dict(details)


def _cleanup_uploads() -> None:
    now = time.monotonic()
    with _uploads_lock:
        expired = [key for key, item in _uploads.items() if now - item["accessed"] > _upload_ttl]
        for key in expired:
            item = _uploads.pop(key)
            Path(item["path"]).unlink(missing_ok=True)


def _get_upload(upload_id: str) -> dict:
    _cleanup_uploads()
    with _uploads_lock:
        item = _uploads.get(upload_id)
        if not item:
            raise ValueError("Upload expired. Please upload the video again")
        item["accessed"] = time.monotonic()
        return dict(item)


def _request_time(data: dict, duration: float, fps: float) -> float:
    try:
        timestamp = float(data.get("time", 0))
    except (TypeError, ValueError) as error:
        raise ValueError("Enter a valid frame time") from error
    if not math.isfinite(timestamp) or timestamp < 0:
        raise ValueError("Enter a valid frame time")
    # The duration marks the end of the video, not a decodable frame.
    last_frame = max(0, duration - (0.5 / fps if fps > 0 else 0.05))
    return min(timestamp, last_frame)


def _extract_frame(source: str, timestamp: float, fmt: str, headers: dict | None = None) -> bytes:
    args = ["ffmpeg", "-hide_banner", "-loglevel", "error"]
    if headers:
        args += ["-headers", "".join(f"{name}: {value}\r\n" for name, value in headers.items())]
    args += ["-ss", f"{timestamp:.6f}", "-i", source, "-map", "0:v:0", "-frames:v", "1"]
    if fmt == "png":
        args += ["-f", "image2pipe", "-vcodec", "png", "pipe:1"]
    else:
        args += ["-q:v", "2", "-f", "image2pipe", "-vcodec", "mjpeg", "pipe:1"]
    result = subprocess.run(args, capture_output=True, timeout=90)
    if result.returncode or not result.stdout:
        error = result.stderr.decode(errors="replace")
        if "403 Forbidden" in error or "access denied" in error.lower():
            raise PermissionError("Video stream access was denied")
        raise ValueError("Could not capture a frame at this time")
    return result.stdout


@bp.route("/frameclipper")
def frameclipper_page():
    return render_template("frameclipper.html")


@bp.route("/api/frameclipper/upload", methods=["POST"])
def frameclipper_upload():
    file = request.files.get("file")
    if not file or not (file.filename or "").lower().endswith(".mp4"):
        return jsonify(error="Choose an MP4 video file"), 400

    _cleanup_uploads()
    upload_id = uuid.uuid4().hex
    path = str(Path(_upload_dir.name) / f"{upload_id}.mp4")
    try:
        file.save(path)
        details = _probe_local(path)
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        Path(path).unlink(missing_ok=True)
        return jsonify(error=f"Could not read video: {error}"), 400

    title = Path(file.filename or "video.mp4").stem
    with _uploads_lock:
        _uploads[upload_id] = {"path": path, "title": title, "accessed": time.monotonic(), **details}
    return jsonify(source="upload", upload_id=upload_id, title=title, **details)


@bp.route("/api/frameclipper/youtube", methods=["POST"])
def frameclipper_youtube():
    url = str((request.get_json(silent=True) or {}).get("url", "")).strip()
    try:
        url = f"https://www.youtube.com/watch?v={extract_video_id(url)}"
        details = _youtube_details(url)
        return jsonify(source="youtube", url=url, **{key: details[key] for key in ("title", "duration", "fps", "width", "height")})
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except Exception as error:
        return jsonify(error=f"Could not load video: {error}"), 502


@bp.route("/api/frameclipper/frame", methods=["POST"])
def frameclipper_frame():
    data = request.get_json(silent=True) or {}
    fmt = data.get("format", "jpg")
    if fmt not in ("jpg", "png"):
        return jsonify(error="Choose JPG or PNG"), 400

    source = data.get("source")
    try:
        if source == "upload":
            item = _get_upload(str(data.get("upload_id", "")))
            stream_url, headers = item["path"], None
        elif source == "youtube":
            url = str(data.get("url", "")).strip()
            extract_video_id(url)
            item = _youtube_details(url)
            stream_url, headers = item["source_url"], item["headers"]
        else:
            return jsonify(error="Load a video first"), 400

        timestamp = _request_time(data, item["duration"], item["fps"])
        try:
            frame = _extract_frame(stream_url, timestamp, fmt, headers)
        except PermissionError:
            if source != "youtube":
                raise
            item = _youtube_details(url, refresh=True)
            try:
                frame = _extract_frame(item["source_url"], timestamp, fmt, item["headers"])
            except PermissionError:
                item = _youtube_details(url, "android", refresh=True)
                frame = _extract_frame(item["source_url"], timestamp, fmt, item["headers"])
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except (PermissionError, subprocess.SubprocessError, yt_dlp.DownloadError) as error:
        return jsonify(error=f"Frame capture failed: {error}"), 502

    mime = "image/png" if fmt == "png" else "image/jpeg"
    name = secure_filename(item["title"]) or "frame"
    frame_label = f"{timestamp:.3f}".replace(".", "-")
    response = send_file(
        BytesIO(frame), mimetype=mime,
        as_attachment=bool(data.get("download")),
        download_name=f"{name}-{frame_label}.{fmt}",
    )
    response.headers["Cache-Control"] = "no-store"
    return response
