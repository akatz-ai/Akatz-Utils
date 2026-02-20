"""Video to GIF converter - Pure processing functions (no GUI)."""

from __future__ import annotations

import os
import shutil
import tempfile
from typing import Callable, Optional

from moviepy import VideoFileClip


def convert_video(
    input_path: str,
    output_path: str,
    duration: float = 5.0,
    target_size_mb: float = 5.0,
    width: Optional[int] = None,
    height: Optional[int] = None,
    aspect_mode: str = "maintain",
    progress_callback: Optional[Callable[[str], None]] = None,
) -> float:
    """Convert a video file to GIF.

    Args:
        input_path: Path to the input video file.
        output_path: Path for the output GIF file.
        duration: Maximum GIF duration in seconds.
        target_size_mb: Target file size in MB.
        width: Output width (None to keep original).
        height: Output height (None to keep original).
        aspect_mode: "maintain", "crop", or "fill".
        progress_callback: Optional callback(status_message).

    Returns:
        Final file size in MB.
    """
    def status(msg: str) -> None:
        if progress_callback:
            progress_callback(msg)

    status("Loading video...")
    video = VideoFileClip(input_path)

    try:
        clip_duration = min(duration, video.duration)
        video = video.subclipped(0, clip_duration)

        # Handle dimensions
        if width is not None or height is not None:
            if aspect_mode == "maintain":
                if width and height:
                    video = video.resized(height=height)
                    if video.w > width:
                        video = video.resized(width=width)
                elif width:
                    video = video.resized(width=width)
                elif height:
                    video = video.resized(height=height)
            elif aspect_mode == "crop":
                if width and height:
                    video = video.resized(newsize=(width, height))
            elif aspect_mode == "fill":
                if width and height:
                    video = video.resized(newsize=(width, height))
                elif width:
                    video = video.resized(width=width)
                elif height:
                    video = video.resized(height=height)

        status("Calculating optimal settings...")
        target_fps = 10

        with tempfile.NamedTemporaryFile(suffix=".gif", delete=False) as tmp_file:
            tmp_path = tmp_file.name

        status("Creating GIF...")
        video.write_gif(tmp_path, fps=target_fps, logger=None)

        file_size_mb = os.path.getsize(tmp_path) / (1024 * 1024)

        if file_size_mb > target_size_mb:
            status("Optimizing file size...")
            fps_reduction_factor = (target_size_mb / file_size_mb) ** 0.5
            new_fps = max(1, int(target_fps * fps_reduction_factor))
            os.unlink(tmp_path)
            video.write_gif(tmp_path, fps=new_fps, logger=None)

        shutil.move(tmp_path, output_path)
        final_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        status("Conversion complete")
        return final_size_mb

    finally:
        video.close()
