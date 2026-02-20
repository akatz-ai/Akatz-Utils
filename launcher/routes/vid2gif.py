"""Vid2GIF Flask routes with SSE progress."""

from __future__ import annotations

import json
import os
import queue
import tempfile
import threading
import uuid

from flask import Blueprint, request, jsonify, render_template, Response, send_file

from vid2gif import convert_video

bp = Blueprint("vid2gif", __name__)

_tasks: dict[str, dict] = {}


@bp.route("/vid2gif")
def vid2gif_page():
    return render_template("vid2gif.html")


@bp.route("/api/vid2gif/convert", methods=["POST"])
def vid2gif_convert():
    """Upload a video and start conversion. Returns task_id."""
    f = request.files.get("file")
    if not f:
        return jsonify(error="No file provided"), 400

    # Parse options from form data
    duration = float(request.form.get("duration", 5))
    target_size_mb = float(request.form.get("target_size_mb", 5))
    width = request.form.get("width")
    height = request.form.get("height")
    aspect_mode = request.form.get("aspect_mode", "maintain")

    width = int(width) if width else None
    height = int(height) if height else None

    # Save uploaded video to temp file
    suffix = os.path.splitext(f.filename or "video.mp4")[1]
    tmp_in = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    f.save(tmp_in)
    tmp_in.close()

    # Prepare output temp file
    tmp_out = tempfile.NamedTemporaryFile(suffix=".gif", delete=False)
    tmp_out.close()

    task_id = uuid.uuid4().hex[:12]
    q: queue.Queue = queue.Queue()

    _tasks[task_id] = {
        "queue": q,
        "output_path": tmp_out.name,
        "filename": (f.filename or "video").rsplit(".", 1)[0] + ".gif",
        "result_size": None,
        "error": None,
    }

    def run():
        try:
            def progress_cb(msg):
                q.put({"status": msg})

            final_size = convert_video(
                input_path=tmp_in.name,
                output_path=tmp_out.name,
                duration=duration,
                target_size_mb=target_size_mb,
                width=width,
                height=height,
                aspect_mode=aspect_mode,
                progress_callback=progress_cb,
            )
            _tasks[task_id]["result_size"] = final_size
            q.put({"done": True, "size_mb": round(final_size, 2)})
        except Exception as e:
            _tasks[task_id]["error"] = str(e)
            q.put({"error": str(e)})
        finally:
            try:
                os.unlink(tmp_in.name)
            except OSError:
                pass

    threading.Thread(target=run, daemon=True).start()
    return jsonify(task_id=task_id)


@bp.route("/api/vid2gif/progress/<task_id>")
def vid2gif_progress(task_id):
    """SSE stream for conversion progress."""
    if task_id not in _tasks:
        return jsonify(error="Invalid task_id"), 404

    def generate():
        q = _tasks[task_id]["queue"]
        while True:
            try:
                msg = q.get(timeout=60)
                yield f"data: {json.dumps(msg)}\n\n"
                if "done" in msg or "error" in msg:
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'keepalive': True})}\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@bp.route("/api/vid2gif/download/<task_id>")
def vid2gif_download(task_id):
    """Download the converted GIF."""
    if task_id not in _tasks:
        return jsonify(error="Invalid task_id"), 404

    task = _tasks[task_id]
    if task["error"]:
        return jsonify(error=task["error"]), 500
    if task["result_size"] is None:
        return jsonify(error="Conversion not complete"), 425

    return send_file(task["output_path"], mimetype="image/gif",
                     as_attachment=True, download_name=task["filename"])
