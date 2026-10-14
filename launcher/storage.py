"""Shared-drive checks and destinations for the hub deployment."""

import os
import subprocess
import uuid
from pathlib import Path
from urllib.parse import unquote

from flask import current_app


def check_storage(expected_gib=2):
    if not current_app.config.get("SHARED_ROOT"):
        return
    try:
        result = subprocess.run(
            ["hub-storage", "check", "--target", "shared", "--expected-gib", str(expected_gib)],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError("Shared storage could not be verified; no processing started") from error
    if result.returncode:
        raise RuntimeError("Shared storage unavailable or insufficient space; no processing started")


def shared_folder(value):
    root = current_app.config.get("SHARED_ROOT")
    if not root:
        raise ValueError("Shared-drive saving is not enabled on this server")
    root = Path(root).resolve()
    path = Path(str(value)).expanduser()
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    if not path.is_relative_to(root):
        raise ValueError("Choose a folder inside the shared drive")
    return path


def configure_storage(app):
    app.config["SHARED_ROOT"] = os.environ.get("AKATZ_SHARED_ROOT", "")
    app.config["CLIP_JOB_ROOT"] = os.environ.get("AKATZ_CLIP_JOB_ROOT", "")
    if app.config["SHARED_ROOT"]:
        with app.app_context():
            check_storage()
            scratch = shared_folder(os.environ.get("TMPDIR", ""))
            if scratch == Path(app.config["SHARED_ROOT"]).resolve():
                raise RuntimeError("Set TMPDIR to a dedicated shared-drive scratch folder")
            scratch.mkdir(parents=True, exist_ok=True)

    @app.before_request
    def verify_processing_storage():
        from flask import jsonify, request
        # Cancelling releases resources and must work even when the drive is
        # below its reserve. It does not begin processing or create media.
        if request.endpoint == "clipjobs.cancel_job":
            return
        if request.path.startswith("/api/"):
            try:
                check_storage(2 if request.method == "POST" else 0)
                if request.headers.get("X-Akatz-Save-Folder"):
                    shared_folder(unquote(request.headers["X-Akatz-Save-Folder"]))
            except ValueError as error:
                return jsonify(error=str(error)), 400
            except RuntimeError as error:
                return jsonify(error=str(error)), 503

    @app.after_request
    def save_export(response):
        from flask import jsonify, request
        from werkzeug.http import parse_options_header
        folder = request.headers.get("X-Akatz-Save-Folder")
        if not folder or response.status_code != 200:
            return response
        allowed = request.path in {"/api/imgsizer/export", "/api/frameclipper/frame"} or request.path.startswith(("/api/vid2gif/download/", "/api/pdf2md/download/"))
        if request.method != "POST" or not allowed:
            return response
        partial = None
        try:
            check_storage(2)
            target_dir = shared_folder(unquote(folder))
            target_dir.mkdir(parents=True, exist_ok=True)
            _, options = parse_options_header(response.headers.get("Content-Disposition", ""))
            filename = Path(options.get("filename", "export")).name
            filename = filename.replace("\\", "_").encode()[:220].decode(errors="ignore")
            if filename in {"", ".", ".."}:
                filename = "export"
            target = target_dir / filename
            token = uuid.uuid4().hex
            partial = target_dir / f".akatz-{token}.partial"
            size = 0
            with partial.open("xb") as output:
                for chunk in response.response:
                    if isinstance(chunk, str):
                        chunk = chunk.encode()
                    size += len(chunk)
                    if size > 2 * 1024**3:
                        raise RuntimeError("Export exceeded its 2 GiB storage budget")
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            try:
                os.link(partial, target)
            except FileExistsError:
                target = target.with_name(f"{target.stem}-{token}{target.suffix}")
                os.link(partial, target)
            return jsonify(path=str(target), bytes=size)
        except (OSError, RuntimeError, ValueError) as error:
            return jsonify(error=f"Could not save export: {error}"), 503
        finally:
            response.close()
            if partial is not None:
                partial.unlink(missing_ok=True)
