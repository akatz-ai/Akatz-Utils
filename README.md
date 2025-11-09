# Akatz Utils

A collection of utility tools for common tasks, managed as a Python monorepo using UV workspaces.

## Tools Included

- **PDF to Markdown** (`pdf2md`) - Convert PDF files to Markdown format for efficient LLM processing
- **Video to GIF** (`vid2gif`) - Convert video files to GIF with customizable size, duration, and dimensions
- **Image Resizer** (`imgsizer`) - Resize and compress images with preview and quality control

## Installation

### Prerequisites

- Python 3.8 or higher
- [uv](https://docs.astral.sh/uv/) package manager

### Quick Start

Clone the repository and install the launcher:

```bash
git clone https://github.com/yourusername/akatz-utils.git
cd akatz-utils
uv tool install launcher
```

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
uv tool install tools/pdf2md
uv tool install tools/vid2gif
uv tool install tools/imgsizer
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
├── pyproject.toml          # Workspace configuration
├── launcher/               # GUI launcher package
│   ├── launcher.py
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
uv run --package pdf2md python -m pdf2md

# Build all packages
uv build --all
```

### Adding a New Tool

1. Create a new directory under `tools/`
2. Add a `pyproject.toml` with proper metadata
3. Implement your tool with a `main()` function
4. Add the tool to `launcher/launcher.py` in the `tools` list
5. Add workspace dependency in `launcher/pyproject.toml`

## License

MIT
