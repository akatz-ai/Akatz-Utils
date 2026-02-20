"""PDF2MD Flask routes with SSE progress."""

from __future__ import annotations

import json
import os
import queue
import tempfile
import threading
import uuid

from flask import Blueprint, request, jsonify, render_template, Response, send_file

from pdf2md import convert_pdf, format_size

bp = Blueprint("pdf2md", __name__)

# In-memory task store
_tasks: dict[str, dict] = {}


@bp.route("/pdf2md")
def pdf2md_page():
    return render_template("pdf2md.html")


@bp.route("/api/pdf2md/convert", methods=["POST"])
def pdf2md_convert():
    """Upload a PDF and start conversion. Returns task_id."""
    f = request.files.get("file")
    if not f:
        return jsonify(error="No file provided"), 400

    # Save to temp file
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    f.save(tmp)
    tmp.close()

    task_id = uuid.uuid4().hex[:12]
    q: queue.Queue = queue.Queue()

    _tasks[task_id] = {
        "queue": q,
        "input_path": tmp.name,
        "input_size": os.path.getsize(tmp.name),
        "filename": f.filename or "document.pdf",
        "result": None,
        "error": None,
    }

    def run():
        try:
            def progress_cb(current, total, msg):
                q.put({"page": current, "total": total, "status": msg})

            md_text = convert_pdf(tmp.name, progress_callback=progress_cb)
            _tasks[task_id]["result"] = md_text
            q.put({"done": True, "output_size": len(md_text.encode("utf-8"))})
        except Exception as e:
            _tasks[task_id]["error"] = str(e)
            q.put({"error": str(e)})
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    threading.Thread(target=run, daemon=True).start()
    return jsonify(task_id=task_id)


@bp.route("/api/pdf2md/progress/<task_id>")
def pdf2md_progress(task_id):
    """SSE stream for conversion progress."""
    if task_id not in _tasks:
        return jsonify(error="Invalid task_id"), 404

    def generate():
        q = _tasks[task_id]["queue"]
        while True:
            try:
                msg = q.get(timeout=30)
                yield f"data: {json.dumps(msg)}\n\n"
                if "done" in msg or "error" in msg:
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'keepalive': True})}\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@bp.route("/api/pdf2md/download/<task_id>")
def pdf2md_download(task_id):
    """Download the converted markdown file."""
    if task_id not in _tasks:
        return jsonify(error="Invalid task_id"), 404

    task = _tasks[task_id]
    if task["error"]:
        return jsonify(error=task["error"]), 500
    if task["result"] is None:
        return jsonify(error="Conversion not complete"), 425

    filename = task["filename"].rsplit(".", 1)[0] + ".md"
    md_bytes = task["result"].encode("utf-8")

    from io import BytesIO
    return send_file(BytesIO(md_bytes), mimetype="text/markdown",
                     as_attachment=True, download_name=filename)


@bp.route("/api/pdf2md/preview/<task_id>")
def pdf2md_preview(task_id):
    """Return the markdown content for inline preview."""
    if task_id not in _tasks:
        return jsonify(error="Invalid task_id"), 404

    task = _tasks[task_id]
    if task["result"] is None:
        return jsonify(error="Conversion not complete"), 425

    input_size = task["input_size"]
    output_size = len(task["result"].encode("utf-8"))
    reduction = ((input_size - output_size) / input_size * 100) if input_size > 0 else 0

    return jsonify(
        markdown=task["result"],
        input_size=format_size(input_size),
        output_size=format_size(output_size),
        reduction=round(reduction, 1),
    )
