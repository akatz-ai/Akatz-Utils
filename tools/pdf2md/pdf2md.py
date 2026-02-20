"""PDF to Markdown converter - Pure processing functions (no GUI)."""

from __future__ import annotations

import os
from typing import Callable, Optional

try:
    import pdfplumber
except ImportError:
    pdfplumber = None


def format_size(size_bytes: float) -> str:
    """Convert bytes to human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def convert_pdf(
    input_path: str,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> str:
    """Convert a PDF file to markdown text.

    Args:
        input_path: Path to the input PDF file.
        progress_callback: Optional callback(current_page, total_pages, status_msg).

    Returns:
        The markdown content as a string.

    Raises:
        RuntimeError: If pdfplumber is not installed.
        FileNotFoundError: If input_path does not exist.
    """
    if pdfplumber is None:
        raise RuntimeError("pdfplumber is not installed")

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"PDF file not found: {input_path}")

    all_text: list[str] = []

    with pdfplumber.open(input_path) as pdf:
        total_pages = len(pdf.pages)

        for i, page in enumerate(pdf.pages):
            if progress_callback:
                progress_callback(i, total_pages, f"Extracting page {i + 1}/{total_pages}")

            text = page.extract_text()
            if text:
                all_text.append(f"# Page {i + 1}\n\n{text}\n\n")

    if progress_callback:
        progress_callback(total_pages, total_pages, "Conversion complete")

    return "".join(all_text)
