"""YouTube Clipper Flask routes."""

from __future__ import annotations

from typing import cast

from flask import Blueprint, Response, jsonify, render_template, request, stream_with_context

from ytclipper import ClipFormat, extract_media_url, extract_video_id, iter_clip, validate_time_range

bp = Blueprint("ytclipper", __name__)


@bp.route("/ytclipper")
def ytclipper_page():
    return render_template("ytclipper.html")


@bp.route("/api/ytclipper/clip", methods=["POST"])
def ytclipper_clip():
    """Create and stream a clip from a YouTube URL."""
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
        media_url, title, http_headers = extract_media_url(url, fmt)
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

    return Response(
        stream_with_context(iter_clip(media_url, start, duration, fmt, http_headers)),
        mimetype=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
