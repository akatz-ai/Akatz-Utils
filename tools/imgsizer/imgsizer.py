#!/usr/bin/env python3
"""
Image Resizer - A GUI utility for resizing and compressing images.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageOps
import os
import io
from pathlib import Path
import threading
from typing import Optional, Tuple, Any, Union

class ImageResizer:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Image Resizer")
        self.root.geometry("900x700")
        
        # State variables
        self.original_image: Optional[Image.Image] = None
        self.current_image: Optional[Image.Image] = None
        self.image_path: Optional[str] = None
        self.aspect_ratio: float = 1.0
        self.updating_sliders: bool = False
        self.photo: Optional[ImageTk.PhotoImage] = None
        
        # Variables for controls
        self.width_var: tk.IntVar = tk.IntVar(value=100)
        self.height_var: tk.IntVar = tk.IntVar(value=100)
        self.quality_var: tk.IntVar = tk.IntVar(value=85)
        self.filesize_var: tk.IntVar = tk.IntVar(value=1024)  # KB
        self.aspect_locked: tk.BooleanVar = tk.BooleanVar(value=True)
        self.resize_mode: tk.StringVar = tk.StringVar(value="stretch")

        # UI widgets (initialized in setup_ui)
        self.file_label: ttk.Label
        self.info_label: ttk.Label
        self.canvas: tk.Canvas
        self.width_slider: ttk.Scale
        self.height_slider: ttk.Scale
        self.width_label: ttk.Label
        self.height_label: ttk.Label
        self.quality_slider: ttk.Scale
        self.quality_label: ttk.Label
        self.size_slider: ttk.Scale
        self.size_label: ttk.Label
        self.mode_frame: ttk.Frame
        self.stats_label: ttk.Label

        self.setup_ui()
        
    def setup_ui(self) -> None:
        """Set up the user interface."""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # Top section - File selection
        file_frame = ttk.LabelFrame(main_frame, text="Image Selection", padding="10")
        file_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.file_label = ttk.Label(file_frame, text="No image selected")
        self.file_label.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(file_frame, text="Browse...", command=self.browse_image).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_frame, text="Save As...", command=self.save_image).pack(side=tk.LEFT, padx=5)
        
        # Info labels
        self.info_label = ttk.Label(file_frame, text="", foreground="blue")
        self.info_label.pack(side=tk.RIGHT, padx=10)
        
        # Left panel - Image preview
        preview_frame = ttk.LabelFrame(main_frame, text="Preview", padding="10")
        preview_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Canvas for image display
        self.canvas = tk.Canvas(preview_frame, bg="gray90", width=400, height=400)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Right panel - Controls
        controls_frame = ttk.LabelFrame(main_frame, text="Resize Controls", padding="10")
        controls_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Dimensions section
        dim_frame = ttk.LabelFrame(controls_frame, text="Dimensions", padding="10")
        dim_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Width control
        ttk.Label(dim_frame, text="Width:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.width_slider = ttk.Scale(dim_frame, from_=10, to=5000, orient=tk.HORIZONTAL, 
                                     variable=self.width_var, command=self.on_width_change)
        self.width_slider.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        self.width_label = ttk.Label(dim_frame, text="100 px")
        self.width_label.grid(row=0, column=2)
        
        # Height control
        ttk.Label(dim_frame, text="Height:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(5, 0))
        self.height_slider = ttk.Scale(dim_frame, from_=10, to=5000, orient=tk.HORIZONTAL,
                                      variable=self.height_var, command=self.on_height_change)
        self.height_slider.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(0, 10), pady=(5, 0))
        self.height_label = ttk.Label(dim_frame, text="100 px")
        self.height_label.grid(row=1, column=2, pady=(5, 0))
        
        dim_frame.columnconfigure(1, weight=1)
        
        # Aspect ratio controls
        aspect_frame = ttk.Frame(dim_frame)
        aspect_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        
        self.aspect_check = ttk.Checkbutton(aspect_frame, text="Lock Aspect Ratio", 
                                           variable=self.aspect_locked, command=self.on_aspect_toggle)
        self.aspect_check.pack(side=tk.LEFT)
        
        # Resize mode (only visible when aspect is unlocked)
        self.mode_frame = ttk.Frame(aspect_frame)
        self.mode_frame.pack(side=tk.LEFT, padx=(20, 0))
        ttk.Label(self.mode_frame, text="Mode:").pack(side=tk.LEFT, padx=(0, 5))
        self.stretch_radio = ttk.Radiobutton(self.mode_frame, text="Stretch", 
                                            variable=self.resize_mode, value="stretch",
                                            command=self.update_preview)
        self.stretch_radio.pack(side=tk.LEFT, padx=5)
        self.crop_radio = ttk.Radiobutton(self.mode_frame, text="Crop", 
                                         variable=self.resize_mode, value="crop",
                                         command=self.update_preview)
        self.crop_radio.pack(side=tk.LEFT, padx=5)
        self.mode_frame.pack_forget()  # Initially hidden
        
        # Quality/Compression section
        quality_frame = ttk.LabelFrame(controls_frame, text="Compression", padding="10")
        quality_frame.pack(fill=tk.X, pady=(0, 10))
        
        # JPEG Quality
        ttk.Label(quality_frame, text="JPEG Quality:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.quality_slider = ttk.Scale(quality_frame, from_=10, to=100, orient=tk.HORIZONTAL,
                                       variable=self.quality_var, command=self.on_quality_change)
        self.quality_slider.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        self.quality_label = ttk.Label(quality_frame, text="85%")
        self.quality_label.grid(row=0, column=2)
        
        quality_frame.columnconfigure(1, weight=1)
        
        # Target file size section
        size_frame = ttk.LabelFrame(controls_frame, text="Target File Size", padding="10")
        size_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(size_frame, text="Max Size:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.size_slider = ttk.Scale(size_frame, from_=50, to=10240, orient=tk.HORIZONTAL,
                                    variable=self.filesize_var, command=self.on_filesize_change)
        self.size_slider.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        self.size_label = ttk.Label(size_frame, text="1024 KB")
        self.size_label.grid(row=0, column=2)
        
        ttk.Button(size_frame, text="Auto-Adjust to Target", 
                  command=self.auto_adjust_to_size).grid(row=1, column=0, columnspan=3, pady=(10, 0))
        
        size_frame.columnconfigure(1, weight=1)
        
        # Current stats
        stats_frame = ttk.LabelFrame(controls_frame, text="Current Stats", padding="10")
        stats_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.stats_label = ttk.Label(stats_frame, text="No image loaded", font=("", 9))
        self.stats_label.pack()
        
        # Quick presets
        presets_frame = ttk.LabelFrame(controls_frame, text="Quick Presets", padding="10")
        presets_frame.pack(fill=tk.X)
        
        preset_buttons = [
            ("Web (1920×1080)", lambda: self.apply_preset(1920, 1080, 85)),
            ("Email (800×600)", lambda: self.apply_preset(800, 600, 70)),
            ("Thumbnail (150×150)", lambda: self.apply_preset(150, 150, 80)),
            ("Social Media (1200×630)", lambda: self.apply_preset(1200, 630, 85)),
        ]
        
        for i, (text, cmd) in enumerate(preset_buttons):
            row = i // 2
            col = i % 2
            ttk.Button(presets_frame, text=text, command=cmd).grid(row=row, column=col, 
                                                                   padx=5, pady=2, sticky=(tk.W, tk.E))
        presets_frame.columnconfigure(0, weight=1)
        presets_frame.columnconfigure(1, weight=1)
        
    def browse_image(self) -> None:
        """Open file dialog to select an image."""
        filetypes = [
            ("Image files", "*.jpg *.jpeg *.png *.gif *.bmp *.webp *.tiff"),
            ("All files", "*.*")
        ]
        
        filename = filedialog.askopenfilename(
            title="Select an image",
            filetypes=filetypes
        )
        
        if filename:
            self.load_image(filename)
            
    def load_image(self, filepath: str) -> None:
        """Load an image from the given filepath."""
        try:
            self.original_image = Image.open(filepath)
            # Convert RGBA to RGB if necessary
            if self.original_image.mode == 'RGBA':
                background = Image.new('RGB', self.original_image.size, (255, 255, 255))
                background.paste(self.original_image, mask=self.original_image.split()[3])
                self.original_image = background
            elif self.original_image.mode not in ('RGB', 'L'):
                self.original_image = self.original_image.convert('RGB')
                
            self.image_path = filepath
            self.file_label.config(text=os.path.basename(filepath))
            
            # Set initial slider values
            self.width_var.set(self.original_image.width)
            self.height_var.set(self.original_image.height)
            self.aspect_ratio = self.original_image.width / self.original_image.height
            
            # Update slider ranges
            self.width_slider.config(to=max(5000, self.original_image.width * 2))
            self.height_slider.config(to=max(5000, self.original_image.height * 2))
            
            self.update_preview()
            self.update_info()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load image: {str(e)}")
            
    def on_width_change(self, value: Union[str, float]) -> None:
        """Handle width slider change."""
        if self.updating_sliders:
            return
            
        width = int(float(value))
        self.width_label.config(text=f"{width} px")
        
        if self.aspect_locked.get() and self.original_image:
            self.updating_sliders = True
            height = int(width / self.aspect_ratio)
            self.height_var.set(height)
            self.height_label.config(text=f"{height} px")
            self.updating_sliders = False
            
        self.update_preview()
        
    def on_height_change(self, value: Union[str, float]) -> None:
        """Handle height slider change."""
        if self.updating_sliders:
            return
            
        height = int(float(value))
        self.height_label.config(text=f"{height} px")
        
        if self.aspect_locked.get() and self.original_image:
            self.updating_sliders = True
            width = int(height * self.aspect_ratio)
            self.width_var.set(width)
            self.width_label.config(text=f"{width} px")
            self.updating_sliders = False
            
        self.update_preview()
        
    def on_quality_change(self, value: Union[str, float]) -> None:
        """Handle quality slider change."""
        quality = int(float(value))
        self.quality_label.config(text=f"{quality}%")
        self.update_preview()
        
    def on_filesize_change(self, value: Union[str, float]) -> None:
        """Handle file size slider change."""
        size_kb = int(float(value))
        if size_kb >= 1024:
            self.size_label.config(text=f"{size_kb/1024:.1f} MB")
        else:
            self.size_label.config(text=f"{size_kb} KB")
            
    def on_aspect_toggle(self) -> None:
        """Handle aspect ratio lock toggle."""
        if self.aspect_locked.get():
            self.mode_frame.pack_forget()
            if self.original_image:
                # Recalculate height based on current width
                width = self.width_var.get()
                height = int(width / self.aspect_ratio)
                self.height_var.set(height)
                self.height_label.config(text=f"{height} px")
        else:
            self.mode_frame.pack(side=tk.LEFT, padx=(20, 0))
            
        self.update_preview()
        
    def update_preview(self) -> None:
        """Update the preview canvas with the resized image."""
        if not self.original_image:
            return
            
        # Get target dimensions
        target_width = self.width_var.get()
        target_height = self.height_var.get()
        
        # Resize the image
        if self.aspect_locked.get() or self.resize_mode.get() == "stretch":
            # Simple resize
            self.current_image = self.original_image.resize((target_width, target_height), 
                                                            Image.Resampling.LANCZOS)
        else:
            # Crop mode - resize to fit then crop
            self.current_image = ImageOps.fit(self.original_image, (target_width, target_height),
                                             Image.Resampling.LANCZOS)
        
        # Update canvas
        self.display_image()
        
        # Update stats
        self.update_stats()
        
    def display_image(self) -> None:
        """Display the current image on the canvas."""
        if not self.current_image:
            return
            
        # Get canvas dimensions
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width <= 1:  # Canvas not yet rendered
            self.root.after(100, self.display_image)
            return
            
        # Calculate scaling to fit in canvas
        img_width, img_height = self.current_image.size
        scale = min(canvas_width / img_width, canvas_height / img_height, 1.0)
        
        display_width = int(img_width * scale)
        display_height = int(img_height * scale)
        
        # Resize for display
        display_image = self.current_image.resize((display_width, display_height), 
                                                  Image.Resampling.LANCZOS)
        
        # Convert to PhotoImage
        self.photo = ImageTk.PhotoImage(display_image)
        
        # Clear canvas and display
        self.canvas.delete("all")
        x = (canvas_width - display_width) // 2
        y = (canvas_height - display_height) // 2
        self.canvas.create_image(x, y, anchor=tk.NW, image=self.photo)
        
    def update_stats(self) -> None:
        """Update the statistics label."""
        if not self.current_image:
            return
            
        # Calculate approximate file size
        buffer = io.BytesIO()
        quality = self.quality_var.get()
        self.current_image.save(buffer, format="JPEG", quality=quality, optimize=True)
        size_bytes = buffer.tell()
        
        size_kb = size_bytes / 1024
        if size_kb >= 1024:
            size_str = f"{size_kb/1024:.2f} MB"
        else:
            size_str = f"{size_kb:.1f} KB"
            
        stats_text = (f"Dimensions: {self.current_image.width}×{self.current_image.height} px\n"
                     f"Estimated size: {size_str}\n"
                     f"Quality: {quality}%")
        
        self.stats_label.config(text=stats_text)
        
        # Update info label with warning if over target
        target_kb = self.filesize_var.get()
        if size_kb > target_kb:
            self.info_label.config(text=f"⚠ Over target by {size_kb - target_kb:.1f} KB", 
                                 foreground="red")
        else:
            self.info_label.config(text=f"✓ Under target by {target_kb - size_kb:.1f} KB", 
                                 foreground="green")
        
    def update_info(self) -> None:
        """Update the info label with original image information."""
        if self.original_image and self.image_path:
            file_size = os.path.getsize(self.image_path) / 1024
            if file_size >= 1024:
                size_str = f"{file_size/1024:.2f} MB"
            else:
                size_str = f"{file_size:.1f} KB"
            info_text = f"Original: {self.original_image.width}×{self.original_image.height} px, {size_str}"
            self.file_label.config(text=f"{os.path.basename(self.image_path)} ({info_text})")
            
    def auto_adjust_to_size(self) -> None:
        """Automatically adjust quality and dimensions to meet target file size."""
        if not self.current_image:
            messagebox.showwarning("No Image", "Please load an image first")
            return
            
        target_kb = self.filesize_var.get()
        target_bytes = target_kb * 1024
        
        # First try adjusting quality
        best_quality = 100
        best_scale = 1.0
        
        for quality in range(100, 10, -5):
            buffer = io.BytesIO()
            self.current_image.save(buffer, format="JPEG", quality=quality, optimize=True)
            size = buffer.tell()
            
            if size <= target_bytes:
                best_quality = quality
                break
        else:
            # Need to reduce dimensions too
            best_quality = 30  # Minimum acceptable quality
            
            # Binary search for best scale
            low, high = 0.1, 1.0
            while high - low > 0.01:
                scale = (low + high) / 2
                test_width = int(self.current_image.width * scale)
                test_height = int(self.current_image.height * scale)
                
                test_img = self.current_image.resize((test_width, test_height), 
                                                     Image.Resampling.LANCZOS)
                buffer = io.BytesIO()
                test_img.save(buffer, format="JPEG", quality=best_quality, optimize=True)
                
                if buffer.tell() <= target_bytes:
                    low = scale
                    best_scale = scale
                else:
                    high = scale
                    
        # Apply best settings
        self.quality_var.set(best_quality)
        self.quality_label.config(text=f"{best_quality}%")
        
        if best_scale < 1.0:
            new_width = int(self.original_image.width * best_scale)
            new_height = int(self.original_image.height * best_scale)
            self.width_var.set(new_width)
            self.height_var.set(new_height)
            self.width_label.config(text=f"{new_width} px")
            self.height_label.config(text=f"{new_height} px")
            
        self.update_preview()
        
    def apply_preset(self, width: int, height: int, quality: int) -> None:
        """Apply a preset configuration."""
        if not self.original_image:
            messagebox.showwarning("No Image", "Please load an image first")
            return
            
        self.width_var.set(width)
        self.height_var.set(height)
        self.quality_var.set(quality)
        
        self.width_label.config(text=f"{width} px")
        self.height_label.config(text=f"{height} px")
        self.quality_label.config(text=f"{quality}%")
        
        # Update aspect ratio if locked
        if self.aspect_locked.get():
            self.aspect_ratio = width / height
            
        self.update_preview()
        
    def save_image(self) -> None:
        """Save the resized image."""
        if not self.current_image:
            messagebox.showwarning("No Image", "Please load an image first")
            return
            
        # Determine default extension
        default_ext = ".jpg"
        if self.image_path:
            default_ext = Path(self.image_path).suffix or ".jpg"
            
        filetypes = [
            ("JPEG files", "*.jpg *.jpeg"),
            ("PNG files", "*.png"),
            ("All files", "*.*")
        ]
        
        filename = filedialog.asksaveasfilename(
            title="Save resized image",
            defaultextension=default_ext,
            filetypes=filetypes
        )
        
        if filename:
            try:
                # Determine format from extension
                ext = Path(filename).suffix.lower()
                if ext in ['.jpg', '.jpeg']:
                    self.current_image.save(filename, "JPEG", quality=self.quality_var.get(), 
                                          optimize=True)
                elif ext == '.png':
                    self.current_image.save(filename, "PNG", optimize=True)
                else:
                    # Default to JPEG
                    self.current_image.save(filename, "JPEG", quality=self.quality_var.get(), 
                                          optimize=True)
                                          
                messagebox.showinfo("Success", f"Image saved to {filename}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save image: {str(e)}")


def main() -> None:
    """Main entry point for the application."""
    root = tk.Tk()
    app = ImageResizer(root)

    # Handle window resize
    def on_resize(event: Optional[tk.Event[Any]] = None) -> None:
        app.display_image()
    
    root.bind("<Configure>", on_resize)
    
    # Center window on screen
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f'{width}x{height}+{x}+{y}')
    
    root.mainloop()


if __name__ == "__main__":
    main()