"""ImgSizer Flask routes."""

from __future__ import annotations

import uuid
from io import BytesIO

from flask import Blueprint, request, jsonify, render_template, send_file

from imgsizer import load_image, resize_image, estimate_size, auto_adjust, export_image

bp = Blueprint("imgsizer", __name__)

# In-memory store: file_id -> {"image": PIL.Image, "filename": str, "original_size": int}
_uploads: dict[str, dict] = {}


@bp.route("/imgsizer")
def imgsizer_page():
    return render_template("imgsizer.html")


@bp.route("/api/imgsizer/upload", methods=["POST"])
def imgsizer_upload():
    """Upload an image. Returns file_id + metadata."""
    f = request.files.get("file")
    if not f:
        return jsonify(error="No file provided"), 400

    raw = f.read()
    try:
        img = load_image(BytesIO(raw))
    except Exception as e:
        return jsonify(error=f"Failed to load image: {e}"), 400

    file_id = uuid.uuid4().hex[:12]
    _uploads[file_id] = {
        "image": img,
        "filename": f.filename or "image.jpg",
        "original_bytes": len(raw),
    }

    return jsonify(
        file_id=file_id,
        filename=f.filename,
        width=img.width,
        height=img.height,
        original_bytes=len(raw),
    )


@bp.route("/api/imgsizer/preview", methods=["POST"])
def imgsizer_preview():
    """Return a resized JPEG preview."""
    data = request.get_json(silent=True) or {}
    file_id = data.get("file_id")
    if not file_id or file_id not in _uploads:
        return jsonify(error="Invalid file_id"), 400

    img = _uploads[file_id]["image"]
    width = int(data.get("width", img.width))
    height = int(data.get("height", img.height))
    quality = int(data.get("quality", 85))
    mode = data.get("mode", "stretch")

    resized = resize_image(img, width, height, mode)
    est = estimate_size(resized, quality)
    preview_bytes = export_image(resized, "JPEG", min(quality, 80))

    buf = BytesIO(preview_bytes)
    return send_file(buf, mimetype="image/jpeg", download_name="preview.jpg"), 200, {
        "X-Estimated-Bytes": str(est),
        "X-Width": str(resized.width),
        "X-Height": str(resized.height),
    }


@bp.route("/api/imgsizer/export", methods=["POST"])
def imgsizer_export():
    """Export the processed image as a file download."""
    data = request.get_json(silent=True) or {}
    file_id = data.get("file_id")
    if not file_id or file_id not in _uploads:
        return jsonify(error="Invalid file_id"), 400

    img = _uploads[file_id]["image"]
    filename = _uploads[file_id]["filename"]
    width = int(data.get("width", img.width))
    height = int(data.get("height", img.height))
    quality = int(data.get("quality", 85))
    mode = data.get("mode", "stretch")
    fmt = data.get("format", "JPEG").upper()

    resized = resize_image(img, width, height, mode)
    img_bytes = export_image(resized, fmt, quality)

    ext = ".png" if fmt == "PNG" else ".jpg"
    out_name = filename.rsplit(".", 1)[0] + f"_resized{ext}"
    mime = "image/png" if fmt == "PNG" else "image/jpeg"

    return send_file(BytesIO(img_bytes), mimetype=mime, as_attachment=True, download_name=out_name)


@bp.route("/api/imgsizer/auto-adjust", methods=["POST"])
def imgsizer_auto_adjust():
    """Find optimal quality/scale for target size."""
    data = request.get_json(silent=True) or {}
    file_id = data.get("file_id")
    if not file_id or file_id not in _uploads:
        return jsonify(error="Invalid file_id"), 400

    img = _uploads[file_id]["image"]
    width = int(data.get("width", img.width))
    height = int(data.get("height", img.height))
    mode = data.get("mode", "stretch")
    target_kb = int(data.get("target_kb", 1024))

    resized = resize_image(img, width, height, mode)
    quality, scale = auto_adjust(resized, target_kb * 1024)

    new_width = int(width * scale)
    new_height = int(height * scale)

    return jsonify(quality=quality, scale=round(scale, 3), width=new_width, height=new_height)
