#!/usr/bin/env python3
"""
Image Resizer - Pure image processing functions (no GUI).
"""

from __future__ import annotations

from PIL import Image, ImageOps
import io
from pathlib import Path
from typing import Optional, Tuple


def load_image(source) -> Image.Image:
    """Load an image from a file path or file-like object and normalize to RGB.

    Args:
        source: File path (str/Path) or file-like object (BytesIO, etc.)

    Returns:
        PIL Image in RGB mode.
    """
    img = Image.open(source)
    if img.mode == "RGBA":
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        return background
    elif img.mode not in ("RGB", "L"):
        return img.convert("RGB")
    return img


def resize_image(
    img: Image.Image,
    width: int,
    height: int,
    mode: str = "stretch",
) -> Image.Image:
    """Resize an image to target dimensions.

    Args:
        img: Source PIL Image.
        width: Target width in pixels.
        height: Target height in pixels.
        mode: "stretch" (default) or "crop".

    Returns:
        Resized PIL Image.
    """
    if mode == "crop":
        return ImageOps.fit(img, (width, height), Image.Resampling.LANCZOS)
    return img.resize((width, height), Image.Resampling.LANCZOS)


def estimate_size(img: Image.Image, quality: int = 85, fmt: str = "JPEG") -> int:
    """Estimate the file size in bytes for the given image and quality.

    Args:
        img: PIL Image.
        quality: JPEG quality (10-100).
        fmt: Output format ("JPEG" or "PNG").

    Returns:
        Estimated size in bytes.
    """
    buf = io.BytesIO()
    if fmt.upper() == "PNG":
        img.save(buf, format="PNG", optimize=True)
    else:
        img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.tell()


def auto_adjust(
    img: Image.Image,
    target_bytes: int,
) -> Tuple[int, float]:
    """Find optimal quality and scale to fit under target_bytes.

    Args:
        img: PIL Image (already at desired dimensions).
        target_bytes: Maximum file size in bytes.

    Returns:
        (quality, scale) tuple. scale=1.0 means dimensions unchanged.
    """
    # First try adjusting quality only
    for quality in range(100, 10, -5):
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        if buf.tell() <= target_bytes:
            return quality, 1.0

    # Need to reduce dimensions too
    best_quality = 30
    best_scale = 1.0

    low, high = 0.1, 1.0
    while high - low > 0.01:
        scale = (low + high) / 2
        test_w = int(img.width * scale)
        test_h = int(img.height * scale)
        test_img = img.resize((test_w, test_h), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        test_img.save(buf, format="JPEG", quality=best_quality, optimize=True)
        if buf.tell() <= target_bytes:
            low = scale
            best_scale = scale
        else:
            high = scale

    return best_quality, best_scale


def export_image(
    img: Image.Image,
    fmt: str = "JPEG",
    quality: int = 85,
) -> bytes:
    """Export an image to bytes.

    Args:
        img: PIL Image.
        fmt: "JPEG" or "PNG".
        quality: JPEG quality (ignored for PNG).

    Returns:
        Image bytes.
    """
    buf = io.BytesIO()
    if fmt.upper() == "PNG":
        img.save(buf, format="PNG", optimize=True)
    else:
        img.save(buf, format="JPEG", quality=quality, optimize=True)
    buf.seek(0)
    return buf.read()
