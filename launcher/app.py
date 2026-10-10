"""Flask application factory and tool registry."""

from __future__ import annotations

from flask import Flask

# Tool registry: id -> metadata
TOOLS = [
    {
        "id": "imgsizer",
        "name": "Image Resizer",
        "description": "Resize and compress images with live preview and quality control",
        "icon": "crop",
    },
    {
        "id": "pdf2md",
        "name": "PDF to Markdown",
        "description": "Convert PDF files to Markdown format for efficient LLM processing",
        "icon": "file-text",
    },
    {
        "id": "vid2gif",
        "name": "Video to GIF",
        "description": "Convert video files to GIF with customizable size, duration, and dimensions",
        "icon": "film",
    },
    {
        "id": "ytclipper",
        "name": "YouTube Clipper",
        "description": "Trim YouTube videos and export MP3, FLAC, or MP4 clips",
        "icon": "youtube",
    },
    {
        "id": "frameclipper",
        "name": "Frame Clipper",
        "description": "Capture a full-resolution JPG or PNG from a video frame",
        "icon": "frame",
    },
]


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500 MB upload limit

    # Register hub route
    from flask import render_template

    @app.route("/")
    def hub():
        return render_template("hub.html", tools=TOOLS)

    # Register tool blueprints
    from .routes.imgsizer import bp as imgsizer_bp
    from .routes.pdf2md import bp as pdf2md_bp
    from .routes.vid2gif import bp as vid2gif_bp
    from .routes.ytclipper import bp as ytclipper_bp
    from .routes.frameclipper import bp as frameclipper_bp

    app.register_blueprint(imgsizer_bp)
    app.register_blueprint(pdf2md_bp)
    app.register_blueprint(vid2gif_bp)
    app.register_blueprint(ytclipper_bp)
    app.register_blueprint(frameclipper_bp)

    return app
