# ImgSizer - Image Resizing Utility

A simple GUI tool for resizing and compressing images, perfect for preparing images for upload to sites with file size restrictions.

## Features

- 📏 **Resize images** with manual width/height control
- 🔒 **Lock aspect ratio** to maintain proportions
- ✂️ **Crop or stretch** when changing aspect ratios
- 📊 **Compress images** with adjustable JPEG quality
- 🎯 **Target file size** with automatic optimization
- 🚀 **Quick presets** for common sizes (web, email, thumbnail, social media)
- 👀 **Live preview** of changes
- 📈 **Real-time stats** showing dimensions and file size

## Installation

### Install as UV tool (recommended)

```bash
# Clone or download the project, then from the project directory:
uv tool install -e .

# Or install directly with uvx for one-time use:
uvx imgsizer
```

### Traditional installation

```bash
# Using pip
pip install pillow

# Then run directly
python imgsizer.py
```

## Usage

1. Launch the application:
   ```bash
   imgsizer
   ```

2. Click "Browse..." to select an image

3. Adjust settings:
   - Use dimension sliders to resize
   - Toggle "Lock Aspect Ratio" to maintain proportions
   - Adjust JPEG quality for compression
   - Use "Auto-Adjust to Target" to automatically meet file size requirements

4. Click "Save As..." to save your resized image

## Supported Formats

- **Input**: JPG, JPEG, PNG, GIF, BMP, WebP, TIFF
- **Output**: JPG/JPEG (recommended for size control), PNG

## Tips

- For maximum compression, use JPEG format with quality 70-85%
- The "Auto-Adjust to Target" feature will find optimal settings for your target file size
- Use presets for common use cases like web images or email attachments
- When aspect ratio is unlocked, choose between:
  - **Stretch**: Distorts image to fit exact dimensions
  - **Crop**: Maintains image quality but removes edges

## Requirements

- Python 3.8+
- Pillow (PIL) library
- tkinter (included with Python on Windows)

## License

MIT License - feel free to modify and distribute as needed.