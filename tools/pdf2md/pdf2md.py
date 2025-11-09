import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
from pathlib import Path
import threading
try:
    import pdfplumber
except ImportError:
    pdfplumber = None


class PDF2MDConverter:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF to Markdown Converter")
        self.root.geometry("700x500")
        self.root.resizable(False, False)

        # Variables
        self.input_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.conversion_running = False

        self.setup_ui()

    def setup_ui(self):
        # Title
        title_label = tk.Label(
            self.root,
            text="PDF to Markdown Converter",
            font=("Arial", 16, "bold")
        )
        title_label.pack(pady=20)

        # Input file section
        input_frame = tk.LabelFrame(self.root, text="Input PDF File", padx=10, pady=10)
        input_frame.pack(padx=20, pady=10, fill="x")

        input_entry = tk.Entry(input_frame, textvariable=self.input_path, width=50)
        input_entry.pack(side="left", padx=5)

        input_button = tk.Button(
            input_frame,
            text="Browse...",
            command=self.browse_input,
            width=10
        )
        input_button.pack(side="left", padx=5)

        # Output file section
        output_frame = tk.LabelFrame(self.root, text="Output Markdown File", padx=10, pady=10)
        output_frame.pack(padx=20, pady=10, fill="x")

        output_entry = tk.Entry(output_frame, textvariable=self.output_path, width=50)
        output_entry.pack(side="left", padx=5)

        output_button = tk.Button(
            output_frame,
            text="Browse...",
            command=self.browse_output,
            width=10
        )
        output_button.pack(side="left", padx=5)

        # Progress section
        progress_frame = tk.LabelFrame(self.root, text="Conversion Progress", padx=10, pady=10)
        progress_frame.pack(padx=20, pady=10, fill="x")

        self.progress_bar = ttk.Progressbar(
            progress_frame,
            mode='determinate',
            length=600
        )
        self.progress_bar.pack(pady=5)

        self.progress_label = tk.Label(progress_frame, text="Ready to convert", font=("Arial", 9))
        self.progress_label.pack(pady=5)

        # Size comparison section
        size_frame = tk.LabelFrame(self.root, text="Size Comparison", padx=10, pady=10)
        size_frame.pack(padx=20, pady=10, fill="x")

        self.size_label = tk.Label(
            size_frame,
            text="No conversion yet",
            font=("Arial", 10),
            justify="left"
        )
        self.size_label.pack(anchor="w")

        # Convert button
        self.convert_button = tk.Button(
            self.root,
            text="Convert to Markdown",
            command=self.start_conversion,
            font=("Arial", 12, "bold"),
            bg="#4CAF50",
            fg="white",
            height=2,
            width=20
        )
        self.convert_button.pack(pady=20)

    def browse_input(self):
        filename = filedialog.askopenfilename(
            title="Select PDF File",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if filename:
            self.input_path.set(filename)
            # Auto-suggest output path
            if not self.output_path.get():
                output = str(Path(filename).with_suffix('.md'))
                self.output_path.set(output)

    def browse_output(self):
        filename = filedialog.asksaveasfilename(
            title="Save Markdown File As",
            defaultextension=".md",
            filetypes=[("Markdown files", "*.md"), ("All files", "*.*")]
        )
        if filename:
            self.output_path.set(filename)

    def format_size(self, size_bytes):
        """Convert bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"

    def start_conversion(self):
        if self.conversion_running:
            messagebox.showwarning("Busy", "Conversion already in progress")
            return

        input_file = self.input_path.get()
        output_file = self.output_path.get()

        # Validation
        if not input_file:
            messagebox.showerror("Error", "Please select an input PDF file")
            return

        if not output_file:
            messagebox.showerror("Error", "Please select an output location")
            return

        if not os.path.exists(input_file):
            messagebox.showerror("Error", "Input PDF file does not exist")
            return

        if pdfplumber is None:
            messagebox.showerror(
                "Error",
                "pdfplumber library not installed.\n\nPlease run: pip install pdfplumber"
            )
            return

        # Start conversion in a separate thread to keep UI responsive
        thread = threading.Thread(target=self.convert_pdf, args=(input_file, output_file))
        thread.daemon = True
        thread.start()

    def convert_pdf(self, input_file, output_file):
        self.conversion_running = True
        self.convert_button.config(state="disabled")

        try:
            # Get input file size
            input_size = os.path.getsize(input_file)

            # Update progress
            self.update_progress(0, "Opening PDF file...")

            # Extract text from PDF
            all_text = []

            with pdfplumber.open(input_file) as pdf:
                total_pages = len(pdf.pages)

                for i, page in enumerate(pdf.pages):
                    # Update progress
                    progress = int((i / total_pages) * 80)  # 0-80%
                    self.update_progress(
                        progress,
                        f"Extracting text from page {i+1}/{total_pages}..."
                    )

                    # Extract text
                    text = page.extract_text()
                    if text:
                        all_text.append(f"# Page {i+1}\n\n{text}\n\n")

            # Update progress
            self.update_progress(85, "Writing markdown file...")

            # Write to markdown file
            markdown_content = "".join(all_text)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(markdown_content)

            # Get output file size
            output_size = os.path.getsize(output_file)

            # Calculate size reduction
            reduction = ((input_size - output_size) / input_size) * 100 if input_size > 0 else 0

            # Update progress
            self.update_progress(100, "Conversion complete!")

            # Update size comparison
            size_info = (
                f"PDF Size: {self.format_size(input_size)}\n"
                f"Markdown Size: {self.format_size(output_size)}\n"
            )

            if reduction > 0:
                size_info += f"Reduction: {reduction:.1f}% smaller"
            elif reduction < 0:
                size_info += f"Increase: {abs(reduction):.1f}% larger"
            else:
                size_info += "No size change"

            self.root.after(0, lambda: self.size_label.config(text=size_info))

            # Show success message
            self.root.after(0, lambda: messagebox.showinfo(
                "Success",
                f"PDF converted successfully!\n\nSaved to: {output_file}"
            ))

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror(
                "Error",
                f"An error occurred during conversion:\n\n{str(e)}"
            ))
            self.update_progress(0, "Error occurred")

        finally:
            self.conversion_running = False
            self.root.after(0, lambda: self.convert_button.config(state="normal"))

    def update_progress(self, value, text):
        """Update progress bar and label from any thread"""
        self.root.after(0, lambda: self.progress_bar.config(value=value))
        self.root.after(0, lambda: self.progress_label.config(text=text))


def main():
    root = tk.Tk()
    app = PDF2MDConverter(root)
    root.mainloop()


if __name__ == "__main__":
    main()
