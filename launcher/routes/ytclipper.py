"""YouTube Clipper Flask routes."""

from __future__ import annotations

import re
import tempfile
import unicodedata
from typing import cast
from urllib.parse import quote

from flask import Blueprint, current_app, jsonify, render_template, request, send_file

from ytclipper import (
    ClipFormat,
    extract_media_sources,
    extract_video_id,
    extract_video_metadata,
    iter_youtube_clip,
    validate_time_range,
)

bp = Blueprint("ytclipper", __name__)


def _content_disposition(filename: str) -> str:
    """Build a browser-compatible attachment header for a Unicode filename."""
    # Werkzeug writes response headers as latin-1. Keep the legacy filename
    # parameter ASCII-only, and carry the actual UTF-8 name in RFC 5987's
    # filename* parameter.
    fallback = unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode()
    fallback = re.sub(r"[\x00-\x1f\x7f]", "", fallback).strip() or "clip"
    encoded = quote(filename, safe="")
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{encoded}"


@bp.route("/ytclipper")
def ytclipper_page():
    return render_template("ytclipper.html")


@bp.route("/api/ytclipper/metadata", methods=["POST"])
def ytclipper_metadata():
    """Load video timing even when YouTube blocks the embedded preview."""
    data = request.get_json(silent=True) or {}
    url = str(data.get("url", "")).strip()
    try:
        extract_video_id(url)
        return jsonify(extract_video_metadata(url))
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except Exception as error:
        return jsonify(error=f"Failed to load video: {error}"), 502


@bp.route("/api/ytclipper/clip", methods=["POST"])
def ytclipper_clip():
    """Create a complete clip before sending the download response."""
    data = request.get_json(silent=True) or {}
    url = str(data.get("url", "")).strip()
    fmt = cast(ClipFormat, data.get("format", "mp3"))

    if fmt not in {"mp3", "flac", "mp4"}:
        return jsonify(error="Unsupported format"), 400

    try:
        start = float(data.get("start", 0))
        end = float(data.get("end", 0))
        extract_video_id(url)
        validate_time_range(start, end)
        media_sources, title = extract_media_sources(url, fmt)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    except Exception as e:
        return jsonify(error=f"Failed to extract media: {e}"), 502

    duration = end - start
    media_types = {
        "mp3": "audio/mpeg",
        "flac": "audio/flac",
        "mp4": "video/mp4",
    }
    media_type = media_types[fmt]
    filename = f"{title}.{fmt}"

    # Encoding can fail before or after producing output. Finish it first so
    # failures can still return JSON instead of a 500 or a truncated download.
    # TemporaryFile keeps larger clips off the Python heap; send_file's file
    # wrapper closes it when the response finishes (including disconnects).
    clip = tempfile.TemporaryFile(mode="w+b")
    try:
        for chunk in iter_youtube_clip(url, media_sources, start, duration, fmt):
            clip.write(chunk)
        size = clip.tell()
        if not size:
            raise RuntimeError("FFmpeg produced an empty clip")
        clip.seek(0)
        response = send_file(
            clip, mimetype=media_type, as_attachment=True, download_name=filename,
        )
        response.headers["Content-Disposition"] = _content_disposition(filename)
        response.content_length = size
        return response
    except Exception as error:
        clip.close()
        current_app.logger.exception("YouTube clip generation failed")
        if "Failed to resolve hostname" in str(error):
            message = "Could not resolve YouTube's media server. Check the FFmpeg installation and DNS settings."
        elif "403 Forbidden" in str(error) or "access denied" in str(error).lower():
            message = "YouTube refused access to the video stream. Please try again."
        else:
            message = "Could not create the clip. Please try again or check the server logs."
        return jsonify(error=message), 502
