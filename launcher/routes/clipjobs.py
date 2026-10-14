"""Persistent background YouTube clips and direct shared-drive saves."""

import json
import os
import re
import tempfile
import threading
import time
import uuid
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file
from ytclipper import extract_media_sources, extract_video_id, iter_youtube_clip, validate_time_range

from ..storage import check_storage, shared_folder
from .ytclipper import _content_disposition

bp = Blueprint("clipjobs", __name__)
_worker_lock = threading.Lock()


def job_root():
    configured = current_app.config.get("CLIP_JOB_ROOT")
    root = Path(configured) if configured else Path(tempfile.gettempdir()) / "akatz-clip-jobs"
    if current_app.config.get("SHARED_ROOT"):
        root = shared_folder(root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def write_job(root, job):
    path = root / f"{job['id']}.json"
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(job, ensure_ascii=False))
    temp.replace(path)


def read_job(job_id):
    if not isinstance(job_id, str) or not re.fullmatch(r"[a-f0-9]{32}", job_id):
        return None
    try:
        return json.loads((job_root() / f"{job_id}.json").read_text())
    except FileNotFoundError:
        return None


def cleanup_browser_jobs(root):
    """Expire only this app's completed temporary browser downloads after a day."""
    for manifest in root.glob("*.json"):
        try:
            job = json.loads(manifest.read_text())
            if job['state'] in {"complete", "error"} and job['destination'] == "browser" and time.time() - job['created'] > 86400:
                path = Path(job.get("path", ""))
                if path.parent == root and path.name.startswith(job['id'] + "-"):
                    path.unlink(missing_ok=True)
                manifest.unlink()
        except (OSError, ValueError, KeyError):
            current_app.logger.warning("Could not expire clip job %s", manifest.name)


def recover_jobs(app):
    with app.app_context():
        root = job_root()
        for manifest in root.glob("*.json"):
            job = json.loads(manifest.read_text())
            if job['state'] == "processing":
                job.update(state="error", error="Server restarted before the clip finished. Please create it again.")
                write_job(root, job)


@bp.get("/api/ytclipper/storage")
def storage_options():
    return jsonify(shared_enabled=bool(current_app.config.get("SHARED_ROOT")),
                   shared_root=current_app.config.get("SHARED_ROOT"),
                   default_folder="Projects/Akatz-Utils/clips")


@bp.get("/api/ytclipper/folders")
def folders():
    try:
        check_storage(0)
        path = shared_folder(request.args.get("path", ""))
        if not path.is_dir():
            return jsonify(error="Folder does not exist yet; you can create it when saving"), 400
        root = Path(current_app.config["SHARED_ROOT"]).resolve()
        children = []
        for item in sorted(path.iterdir(), key=lambda p: p.name.casefold()):
            if not item.name.startswith(".") and item.is_dir() and item.resolve().is_relative_to(root):
                children.append({"name": item.name, "path": str(item)})
        return jsonify(path=str(path), parent=str(path.parent) if path != root else None, folders=children)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except (RuntimeError, OSError) as error:
        return jsonify(error=str(error)), 503


@bp.post("/api/ytclipper/jobs")
def create_job():
    data = request.get_json(silent=True) or {}
    try:
        url = f"https://www.youtube.com/watch?v={extract_video_id(str(data.get('url', '')))}"
        start, end = float(data.get("start", 0)), float(data.get("end", 0))
        validate_time_range(start, end)
        fmt = data.get("format", "mp3")
        if fmt not in {"mp3", "flac", "mp4"}:
            raise ValueError("Unsupported format")
        copy_video = data.get("copy_video") is True and fmt == "mp4"
        destination = data.get("destination", "browser")
        if destination not in {"browser", "shared"}:
            raise ValueError("Choose browser download or shared-drive save")
        folder = shared_folder(data.get("folder", "")) if destination == "shared" else None
        name = str(data.get("filename", "")).strip()
        if name and (name in {".", ".."} or any(c in name for c in '/\\\x00') or any(ord(c) < 32 for c in name) or len(name.encode()) > 180):
            raise ValueError("Enter a filename without slashes, at most 180 bytes")
        # Conservative output budget: 100 Mbit/s MP4, 10 Mbit/s FLAC, 1 Mbit/s MP3.
        budget = max(2, (end - start) * {"mp4": 100, "flac": 10, "mp3": 1}[fmt] / 8 / 1024 + 1)
        check_storage(budget)
    except (ValueError, TypeError) as error:
        return jsonify(error=str(error)), 400
    except RuntimeError as error:
        return jsonify(error=str(error)), 503

    if not _worker_lock.acquire(blocking=False):
        return jsonify(error="A clip is already processing. Wait for it to finish, then try again."), 409
    try:
        root = job_root()
        cleanup_browser_jobs(root)
        job = dict(id=uuid.uuid4().hex, state="processing", destination=destination,
                   url=url, start=start, end=end, format=fmt, copy_video=copy_video, created=time.time(), bytes=0)
        write_job(root, job)
        app = current_app._get_current_object()

        def run():
            partial = None
            try:
                with app.app_context():
                    check_storage(budget)
                    sources, title = extract_media_sources(url, fmt)
                    filename = name or title
                    if filename.lower().endswith('.' + fmt):
                        filename = filename[:-(len(fmt) + 1)]
                    # Leave room for the extension and collision suffix on ext4/NFS.
                    filename = filename.encode()[:180].decode(errors="ignore").strip('. ') or "clip"
                    filename = filename + '.' + fmt
                    target_dir = shared_folder(folder) if folder is not None else root
                    target_dir.mkdir(parents=True, exist_ok=True)
                    if destination == "browser":
                        target = root / f"{job['id']}-{filename}"
                    else:
                        target = target_dir / filename
                    partial = target_dir / f".akatz-{job['id']}.partial"
                    last_update = time.monotonic()
                    with partial.open("xb") as output:
                        for chunk in iter_youtube_clip(url, sources, start, end - start, fmt, copy_video=copy_video):
                            output.write(chunk)
                            job['bytes'] += len(chunk)
                            if job['bytes'] > budget * 1024**3:
                                raise RuntimeError("Clip exceeded its storage budget; shorten the selection")
                            if time.monotonic() - last_update > 2:
                                write_job(root, job)
                                last_update = time.monotonic()
                        if not job['bytes']:
                            raise RuntimeError("FFmpeg produced an empty clip")
                        output.flush()
                        os.fsync(output.fileno())
                    # Publish atomically without overwriting existing user files.
                    for suffix in range(1000):
                        candidate = target if suffix == 0 else target.with_name(f"{target.stem}-{job['id'][:8]}-{suffix}{target.suffix}")
                        try:
                            os.link(partial, candidate)
                            break
                        except FileExistsError:
                            continue
                    else:
                        raise RuntimeError("Could not find an unused filename")
                    partial.unlink()
                    job.update(state="complete", path=str(candidate), filename=filename,
                               download_url=f"/api/ytclipper/jobs/{job['id']}/download")
                    write_job(root, job)
            except Exception as error:
                with app.app_context():
                    app.logger.exception("Clip job %s failed", job['id'])
                    job.update(state="error", error=f"Could not create clip: {error}")
                    write_job(root, job)
            finally:
                try:
                    if partial is not None:
                        partial.unlink(missing_ok=True)
                finally:
                    _worker_lock.release()

        threading.Thread(target=run, daemon=True).start()
        return jsonify(id=job['id']), 202
    except Exception:
        _worker_lock.release()
        raise


@bp.get("/api/ytclipper/jobs/<job_id>")
def job_status(job_id):
    job = read_job(job_id)
    return jsonify(job) if job else (jsonify(error="Clip job not found or expired"), 404)


@bp.get("/api/ytclipper/jobs/<job_id>/download")
def download_job(job_id):
    job = read_job(job_id)
    if not job:
        return jsonify(error="Clip job not found or expired"), 404
    if job['state'] != "complete":
        return jsonify(error=job.get('error', "Clip is still processing")), 425
    if current_app.config.get("SHARED_ROOT"):
        try:
            check_storage(0)
        except RuntimeError as error:
            return jsonify(error=str(error)), 503
    response = send_file(job['path'], as_attachment=True, download_name=job['filename'])
    response.headers['Content-Disposition'] = _content_disposition(job['filename'])
    return response
