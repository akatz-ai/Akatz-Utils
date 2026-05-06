"""YouTube audio clipping utilities."""

from .ytclipper import (
    AudioFormat,
    extract_audio_url,
    extract_video_id,
    iter_clip,
    sanitize_title,
    validate_time_range,
)

__version__ = "0.1.0"
__all__ = [
    "AudioFormat",
    "extract_audio_url",
    "extract_video_id",
    "iter_clip",
    "sanitize_title",
    "validate_time_range",
]
