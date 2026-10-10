# Akatz Utils

A collection of GUI utility tools for common tasks, managed as a Python monorepo using UV workspaces.

## Tools Included

- **PDF to Markdown** (`pdf2md`) - Convert PDF files to Markdown format for efficient LLM processing
- **Video to GIF** (`vid2gif`) - Convert video files to GIF with customizable size, duration, and dimensions
- **Image Resizer** (`imgsizer`) - Resize and compress images with preview and quality control

## Installation

### Prerequisites

- Python 3.9 or higher
- [uv](https://docs.astral.sh/uv/) package manager
- `ffmpeg` and `ffprobe` on `PATH`, with H.264 (`libx264`), AAC, MP3, and FLAC support

On Fedora, the system FFmpeg may lack `libx264`. Use a full build that can
also open HTTPS media URLs. The static FFmpeg bundled with `imageio-ffmpeg`
can fail DNS resolution with Fedora's systemd resolver even when local-file
conversions work. A Linux ARM64 `gpl-shared` build from
[BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds/releases) works on
the Fedora Asahi MacBook. Put its `bin` directory first on `PATH` and set
`IMAGEIO_FFMPEG_EXE` to its `ffmpeg` executable for MoviePy conversions.

### Quick Start

Clone the repository and install the launcher:

```bash
git clone https://github.com/akatz-ai/Akatz-Utils.git
cd Akatz-Utils
uv tool install ./launcher
```

> **Note:** Do not use `uv tool install launcher` (without `./`) — that installs an unrelated package from PyPI.

### Usage

Launch the GUI launcher from anywhere:

```bash
akatz-utils
```

The launcher will display all available tools. Click on any tool to launch it in a new window.

### Installing Individual Tools

If you prefer to install tools individually without the launcher:

```bash
# From the repository root
uv tool install ./tools/pdf2md
uv tool install ./tools/vid2gif
uv tool install ./tools/imgsizer
```

Then run them directly:

```bash
pdf2md
vid2gif
imgsizer
```

## Development

### Repository Structure

```
akatz-utils/
├── pyproject.toml          # UV workspace configuration
├── launcher/               # GUI launcher package
│   ├── __init__.py
│   ├── __main__.py
│   ├── launcher.py
│   ├── assets/
│   │   └── akatz_logo_small.png
│   └── pyproject.toml
└── tools/                  # Individual utility tools
    ├── pdf2md/
    ├── vid2gif/
    └── imgsizer/
```

### Working with the Workspace

The project uses UV workspaces to manage multiple packages in a monorepo:

```bash
# Sync all workspace dependencies
uv sync

# Run a specific tool in development
uv run --package pdf2md pdf2md

# Run the launcher in development
uv run --package akatz-utils-launcher akatz-utils
```

### Adding a New Tool

1. Create a new directory under `tools/`
2. Add a `pyproject.toml` with proper metadata and a `[project.scripts]` entry
3. Implement your tool with a `main()` function and a tkinter GUI
4. Add the tool to `launcher/launcher.py` in the `tools` list
5. Add the workspace dependency in `launcher/pyproject.toml` under `[project.dependencies]` and `[tool.uv.sources]`
6. Add it as a workspace member in the root `pyproject.toml`

## License

MIT
