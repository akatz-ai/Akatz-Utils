# PDF to Markdown Converter

A simple GUI application for Windows that converts PDF files to Markdown format for efficient LLM processing.

## Features

- **User-Friendly GUI**: Built with tkinter for easy use
- **File Browser**: Browse and select PDF files and output locations
- **Progress Tracking**: Real-time progress bar showing conversion status
- **Size Comparison**: Displays file size reduction/increase after conversion
- **Multi-threaded**: Keeps UI responsive during conversion

## Installation

### Option 1: Install as a Command-Line Tool (Recommended)

Using `uv` (requires [uv](https://docs.astral.sh/uv/) to be installed):

```powershell
# From the pdf2md directory
uv tool install .

# Or install from anywhere using the full path
uv tool install <path-to-pdf2md>
```

After installation, you can run the tool from anywhere:
```powershell
pdf2md
```

### Option 2: Run Locally

```powershell
# Install dependencies
uv sync

# Run the application
uv run python -m pdf2md
```

Or with Python directly:
```powershell
python -m pdf2md
```

## Usage

### Starting the Application

If installed as a command-line tool:
```powershell
pdf2md
```

Or run locally:
```powershell
python -m pdf2md
```

### Converting a PDF

1. Click "Browse..." next to "Input PDF File" and select your PDF
2. Click "Browse..." next to "Output Markdown File" to choose where to save the .md file (auto-suggested based on input)
3. Click "Convert to Markdown"
4. Wait for the progress bar to complete
5. View the size comparison to see data reduction

## How It Works

The application uses `pdfplumber` to extract text content from PDF files page by page. Each page is converted to a markdown section with a header indicating the page number. The resulting markdown file is optimized for LLM processing.

## Requirements

- Python 3.7+
- pdfplumber
- Pillow (dependency of pdfplumber)
- tkinter (usually included with Python)

## Notes

- The conversion extracts text content only; images and complex formatting are not preserved
- The size comparison shows the difference between the original PDF and the extracted text markdown
- Conversion runs in a background thread to keep the UI responsive
