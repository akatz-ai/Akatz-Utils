import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
from pathlib import Path
import threading
from moviepy import VideoFileClip
from PIL import Image
import tempfile


class VideoToGifConverter:
    def __init__(self, root):
        self.root = root
        self.root.title("Video to GIF Converter")
        self.root.geometry("600x550")
        self.root.resizable(False, False)

        self.input_file = tk.StringVar()
        self.output_file = tk.StringVar()
        self.gif_duration = tk.StringVar(value="5")
        self.target_size_mb = tk.StringVar(value="5")
        self.output_width = tk.StringVar(value="")
        self.output_height = tk.StringVar(value="")
        self.aspect_mode = tk.StringVar(value="maintain")
        self.use_original_dimensions = tk.BooleanVar(value=True)

        self.create_widgets()

    def create_widgets(self):
        # Main frame with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Input file section
        ttk.Label(main_frame, text="Input Video:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=(0, 5))

        input_frame = ttk.Frame(main_frame)
        input_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))

        ttk.Entry(input_frame, textvariable=self.input_file, width=50).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(input_frame, text="Browse...", command=self.browse_input).grid(row=0, column=1)

        # Output file section
        ttk.Label(main_frame, text="Output GIF:", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky=tk.W, pady=(0, 5))

        output_frame = ttk.Frame(main_frame)
        output_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))

        ttk.Entry(output_frame, textvariable=self.output_file, width=50).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(output_frame, text="Browse...", command=self.browse_output).grid(row=0, column=1)

        # Options section
        ttk.Label(main_frame, text="Conversion Options:", font=('Arial', 10, 'bold')).grid(row=4, column=0, sticky=tk.W, pady=(0, 10))

        options_frame = ttk.Frame(main_frame)
        options_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))

        # Duration
        ttk.Label(options_frame, text="GIF Duration (seconds):").grid(row=0, column=0, sticky=tk.W, pady=5)
        duration_spinbox = ttk.Spinbox(options_frame, from_=1, to=60, textvariable=self.gif_duration, width=10)
        duration_spinbox.grid(row=0, column=1, sticky=tk.W, padx=(5, 0), pady=5)

        # Target size
        ttk.Label(options_frame, text="Target Size (MB):").grid(row=1, column=0, sticky=tk.W, pady=5)
        size_spinbox = ttk.Spinbox(options_frame, from_=0.5, to=50, increment=0.5, textvariable=self.target_size_mb, width=10)
        size_spinbox.grid(row=1, column=1, sticky=tk.W, padx=(5, 0), pady=5)

        # Dimensions section
        ttk.Label(main_frame, text="Output Dimensions:", font=('Arial', 10, 'bold')).grid(row=6, column=0, sticky=tk.W, pady=(0, 10))

        dimensions_frame = ttk.Frame(main_frame)
        dimensions_frame.grid(row=7, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))

        # Original dimensions checkbox
        ttk.Checkbutton(dimensions_frame, text="Use original dimensions",
                       variable=self.use_original_dimensions,
                       command=self.toggle_dimensions).grid(row=0, column=0, columnspan=4, sticky=tk.W, pady=5)

        # Width
        self.width_label = ttk.Label(dimensions_frame, text="Width (px):")
        self.width_label.grid(row=1, column=0, sticky=tk.W, pady=5)
        self.width_entry = ttk.Entry(dimensions_frame, textvariable=self.output_width, width=10)
        self.width_entry.grid(row=1, column=1, sticky=tk.W, padx=(5, 15), pady=5)

        # Height
        self.height_label = ttk.Label(dimensions_frame, text="Height (px):")
        self.height_label.grid(row=1, column=2, sticky=tk.W, pady=5)
        self.height_entry = ttk.Entry(dimensions_frame, textvariable=self.output_height, width=10)
        self.height_entry.grid(row=1, column=3, sticky=tk.W, padx=(5, 0), pady=5)

        # Aspect ratio mode
        self.aspect_label = ttk.Label(dimensions_frame, text="Aspect Ratio Mode:")
        self.aspect_label.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=5)

        aspect_modes = [
            ("Maintain aspect ratio", "maintain"),
            ("Crop to fit", "crop"),
            ("Fill/Stretch", "fill")
        ]

        aspect_frame = ttk.Frame(dimensions_frame)
        aspect_frame.grid(row=3, column=0, columnspan=4, sticky=tk.W, pady=5)

        for i, (text, value) in enumerate(aspect_modes):
            self.aspect_radio = ttk.Radiobutton(aspect_frame, text=text, variable=self.aspect_mode, value=value)
            self.aspect_radio.grid(row=0, column=i, sticky=tk.W, padx=(0, 10))

        # Convert button
        self.convert_button = ttk.Button(main_frame, text="Convert to GIF", command=self.start_conversion)
        self.convert_button.grid(row=8, column=0, columnspan=2, pady=15)

        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate', length=400)
        self.progress.grid(row=9, column=0, columnspan=2, pady=(0, 5))

        # Status label
        self.status_label = ttk.Label(main_frame, text="Ready", foreground="blue")
        self.status_label.grid(row=10, column=0, columnspan=2)

        # Initialize dimension fields state
        self.toggle_dimensions()

    def toggle_dimensions(self):
        """Enable/disable dimension fields based on checkbox"""
        if self.use_original_dimensions.get():
            self.width_entry.config(state='disabled')
            self.height_entry.config(state='disabled')
            self.width_label.config(state='disabled')
            self.height_label.config(state='disabled')
            self.aspect_label.config(state='disabled')
            for child in self.aspect_label.master.winfo_children():
                if isinstance(child, ttk.Frame):
                    for radio in child.winfo_children():
                        if isinstance(radio, ttk.Radiobutton):
                            radio.config(state='disabled')
        else:
            self.width_entry.config(state='normal')
            self.height_entry.config(state='normal')
            self.width_label.config(state='normal')
            self.height_label.config(state='normal')
            self.aspect_label.config(state='normal')
            for child in self.aspect_label.master.winfo_children():
                if isinstance(child, ttk.Frame):
                    for radio in child.winfo_children():
                        if isinstance(radio, ttk.Radiobutton):
                            radio.config(state='normal')

    def browse_input(self):
        """Open file dialog to select input video"""
        filename = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=[
                ("Video files", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.webm"),
                ("All files", "*.*")
            ]
        )
        if filename:
            self.input_file.set(filename)
            # Auto-suggest output filename
            if not self.output_file.get():
                input_path = Path(filename)
                suggested_output = input_path.parent / f"{input_path.stem}.gif"
                self.output_file.set(str(suggested_output))

    def browse_output(self):
        """Open file dialog to select output location"""
        filename = filedialog.asksaveasfilename(
            title="Save GIF As",
            defaultextension=".gif",
            filetypes=[("GIF files", "*.gif"), ("All files", "*.*")]
        )
        if filename:
            self.output_file.set(filename)

    def validate_inputs(self):
        """Validate user inputs before conversion"""
        if not self.input_file.get():
            messagebox.showerror("Error", "Please select an input video file.")
            return False

        if not os.path.exists(self.input_file.get()):
            messagebox.showerror("Error", "Input video file does not exist.")
            return False

        if not self.output_file.get():
            messagebox.showerror("Error", "Please select an output location for the GIF.")
            return False

        try:
            duration = float(self.gif_duration.get())
            if duration <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Error", "GIF duration must be a positive number.")
            return False

        try:
            size = float(self.target_size_mb.get())
            if size <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Error", "Target size must be a positive number.")
            return False

        if not self.use_original_dimensions.get():
            width = self.output_width.get()
            height = self.output_height.get()

            if not width and not height:
                messagebox.showerror("Error", "Please specify at least width or height.")
                return False

            try:
                if width and int(width) <= 0:
                    raise ValueError()
                if height and int(height) <= 0:
                    raise ValueError()
            except ValueError:
                messagebox.showerror("Error", "Width and height must be positive integers.")
                return False

        return True

    def start_conversion(self):
        """Start conversion in a separate thread"""
        if not self.validate_inputs():
            return

        # Disable convert button and start progress
        self.convert_button.config(state='disabled')
        self.progress.start()
        self.status_label.config(text="Converting...", foreground="blue")

        # Run conversion in separate thread to keep GUI responsive
        thread = threading.Thread(target=self.convert_video)
        thread.daemon = True
        thread.start()

    def convert_video(self):
        """Convert video to GIF with specified options"""
        try:
            input_path = self.input_file.get()
            output_path = self.output_file.get()
            duration = float(self.gif_duration.get())
            target_size_mb = float(self.target_size_mb.get())

            # Load video
            self.update_status("Loading video...")
            video = VideoFileClip(input_path)

            # Get duration to use (min of requested duration and video duration)
            clip_duration = min(duration, video.duration)
            video = video.subclipped(0, clip_duration)

            # Handle dimensions
            if not self.use_original_dimensions.get():
                width = self.output_width.get()
                height = self.output_height.get()
                aspect_mode = self.aspect_mode.get()

                width = int(width) if width else None
                height = int(height) if height else None

                if aspect_mode == "maintain":
                    # Resize maintaining aspect ratio
                    if width and height:
                        video = video.resized(height=height)
                        if video.w > width:
                            video = video.resized(width=width)
                    elif width:
                        video = video.resized(width=width)
                    elif height:
                        video = video.resized(height=height)
                elif aspect_mode == "crop":
                    # Crop to fit exact dimensions
                    if width and height:
                        video = video.resized(newsize=(width, height))
                elif aspect_mode == "fill":
                    # Stretch to fill exact dimensions
                    if width and height:
                        video = video.resized(newsize=(width, height))
                    elif width:
                        video = video.resized(width=width)
                    elif height:
                        video = video.resized(height=height)

            # Calculate fps to achieve target file size
            self.update_status("Calculating optimal settings...")

            # Start with a reasonable fps
            target_fps = 10

            # Create temporary GIF to check size
            with tempfile.NamedTemporaryFile(suffix='.gif', delete=False) as tmp_file:
                tmp_path = tmp_file.name

            self.update_status("Creating GIF...")
            video.write_gif(tmp_path, fps=target_fps, logger=None)

            # Check file size and adjust if needed
            file_size_mb = os.path.getsize(tmp_path) / (1024 * 1024)

            if file_size_mb > target_size_mb:
                # Need to reduce quality
                self.update_status("Optimizing file size...")

                # Try reducing fps
                fps_reduction_factor = (target_size_mb / file_size_mb) ** 0.5
                new_fps = max(1, int(target_fps * fps_reduction_factor))

                os.unlink(tmp_path)
                video.write_gif(tmp_path, fps=new_fps, logger=None)

            # Move temporary file to final destination
            import shutil
            shutil.move(tmp_path, output_path)

            video.close()

            final_size_mb = os.path.getsize(output_path) / (1024 * 1024)

            self.root.after(0, lambda size=final_size_mb: self.conversion_complete(size))

        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda msg=error_msg: self.conversion_error(msg))

    def update_status(self, message):
        """Update status label from worker thread"""
        self.root.after(0, lambda msg=message: self.status_label.config(text=msg))

    def conversion_complete(self, file_size_mb):
        """Handle successful conversion"""
        self.progress.stop()
        self.convert_button.config(state='normal')
        self.status_label.config(text=f"Conversion complete! (Size: {file_size_mb:.2f} MB)", foreground="green")
        messagebox.showinfo("Success", f"GIF created successfully!\n\nFinal size: {file_size_mb:.2f} MB")

    def conversion_error(self, error_message):
        """Handle conversion error"""
        self.progress.stop()
        self.convert_button.config(state='normal')
        self.status_label.config(text="Error during conversion", foreground="red")
        messagebox.showerror("Conversion Error", f"An error occurred:\n\n{error_message}")


def main():
    root = tk.Tk()
    app = VideoToGifConverter(root)
    root.mainloop()


if __name__ == "__main__":
    main()
