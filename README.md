# Akatz Utils

A collection of GUI utility tools for common tasks, managed as a Python monorepo using UV workspaces.

## Tools Included

- **PDF to Markdown** (`pdf2md`) - Convert PDF files to Markdown format for efficient LLM processing
- **Video to GIF** (`vid2gif`) - Convert video files to GIF with customizable size, duration, and dimensions
- **Image Resizer** (`imgsizer`) - Resize and compress images with preview and quality control
- **YouTube Clipper** (`ytclipper`) - Export MP3, FLAC, or MP4 selections up to six hours
- **Frame Clipper** (`frameclipper`) - Capture a full-resolution image from a video

## Hub deployment and direct shared-drive exports

The hub deployment runs all conversions on `akatz-hub`. Open
`https://akatz-hub.tail9ecf7d.ts.net:9447/` from a device on the tailnet.
The HTTPS proxy is Tailscale Serve; the application binds only to loopback.

In YouTube Clipper, load a video, choose its start/end and format, then:

- **Download Clip** processes on the hub and downloads the completed file
  using the browser's normal download manager, without buffering it as a JS blob.
- **Save to Shared Drive** writes directly to the chosen folder on `/mnt/shared`.
  Type an absolute shared-drive path or one relative to `/mnt/shared`, or use
  **Browse folders**. New folders are created on save. An optional filename
  overrides the video title; name collisions get a suffix instead of overwriting.

Jobs run in the background. Returning to the page reconnects to the last job.
Only one YouTube clip encodes at a time, so repeated requests cannot exhaust
the hub. Jobs, status manifests, and browser-download outputs live under
`/mnt/shared/Projects/Akatz-Utils/browser-jobs`. Completed temporary browser
outputs expire after 24 hours when the next clip is started. Shared-drive saves
are retained. Interrupted jobs report an error after service restart; they do
not silently restart. Incomplete files from a machine crash may need review.

Image Resizer, PDF to Markdown, Video to GIF, and Frame Clipper also offer
**Save exports directly to shared drive** with an editable destination folder.
When enabled, the existing export/download button saves on the server and
shows the saved path. Uploaded source files still travel from the browser to
the hub; YouTube clips fetch their source on the hub.

The deployment checks `hub-storage check --target shared --expected-gib N`
before processing, with a larger duration-based budget for YouTube clips.
It refuses work when shared storage cannot be verified. All file scratch uses
`/mnt/shared/Projects/Akatz-Utils/scratch` through `TMPDIR`. No media falls back
to local hub storage. Other tool exports are bounded to 2 GiB each.

To install a clean hub checkout (preserve any existing modified checkout):

```bash
mkdir -p ~/dev/services
git clone https://github.com/akatz-ai/Akatz-Utils.git ~/dev/services/akatz-utils
cd ~/dev/services/akatz-utils
hub-storage check --target shared --expected-gib 2
hub-storage check --target local --expected-gib 0.01
# Verify the separate SSD mount and capacity before the runtime install:
findmnt /mnt/hub-ssd
df -h /mnt/hub-ssd
mkdir -p /mnt/shared/Projects/Akatz-Utils/{scratch,browser-jobs,clips,exports}
mkdir -p /mnt/hub-ssd/akatz-utils
ln -s /mnt/hub-ssd/akatz-utils/.venv .venv
UV_CACHE_DIR=/mnt/shared/Projects/Akatz-Utils/install-cache uv sync --all-packages --no-dev --python /usr/bin/python3
mkdir -p ~/.config/systemd/user
cp deploy/akatz-utils-hub.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now akatz-utils-hub.service
tailscale serve --bg --https=9447 http://127.0.0.1:5000
```

The Python runtime is stored on the verified `/mnt/hub-ssd` ext4 filesystem
and linked as `.venv` in the checkout; install downloads/cache use shared storage.
The service uses system FFmpeg with `libx264`, a `veryfast` encoding preset,
and four threads. It uses CPU encoding; actual speed depends on the video's
resolution, codec, duration, and YouTube connection. It does not use a GPU
worker or start training runtimes. The existing modified `~/akatz-utils`
checkout is preserved separately. Service status and logs:

```bash
systemctl --user status akatz-utils-hub
journalctl --user -u akatz-utils-hub -n 50
```

To update, wait until no clip is processing, pull the checkout, run
`uv sync --all-packages --no-dev`, and restart only `akatz-utils-hub`.

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
