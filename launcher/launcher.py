"""
Akatz Utils Launcher - A GUI launcher for utility tools
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import sys
from pathlib import Path
from typing import List, Dict, Callable
import importlib


class ToolInfo:
    """Information about a utility tool"""
    def __init__(self, name: str, module_name: str, description: str, main_func: str = "main"):
        self.name = name
        self.module_name = module_name
        self.description = description
        self.main_func = main_func


class UtilsLauncher:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Akatz Utils Launcher")
        self.root.geometry("700x500")
        self.root.resizable(False, False)

        # Define available tools
        self.tools: List[ToolInfo] = [
            ToolInfo(
                name="PDF to Markdown",
                module_name="pdf2md",
                description="Convert PDF files to Markdown format for efficient LLM processing"
            ),
            ToolInfo(
                name="Video to GIF",
                module_name="vid2gif",
                description="Convert video files to GIF with customizable size, duration, and dimensions"
            ),
            ToolInfo(
                name="Image Resizer",
                module_name="imgsizer",
                description="Resize and compress images with preview and quality control"
            ),
        ]

        self.create_widgets()

    def create_widgets(self):
        """Create the launcher GUI"""
        # Title frame
        title_frame = ttk.Frame(self.root, padding="20")
        title_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N))

        title_label = ttk.Label(
            title_frame,
            text="Akatz Utilities",
            font=('Arial', 24, 'bold')
        )
        title_label.grid(row=0, column=0, sticky=tk.W)

        subtitle_label = ttk.Label(
            title_frame,
            text="Select a utility tool to launch",
            font=('Arial', 11),
            foreground='gray'
        )
        subtitle_label.grid(row=1, column=0, sticky=tk.W, pady=(5, 0))

        # Separator
        separator = ttk.Separator(self.root, orient='horizontal')
        separator.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=20)

        # Tools frame
        tools_frame = ttk.Frame(self.root, padding="20")
        tools_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Create a button for each tool
        for idx, tool in enumerate(self.tools):
            self.create_tool_button(tools_frame, tool, idx)

        # Footer frame
        footer_frame = ttk.Frame(self.root, padding="20")
        footer_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.S))

        footer_label = ttk.Label(
            footer_frame,
            text="Click any tool to launch it in a new window",
            font=('Arial', 9),
            foreground='gray'
        )
        footer_label.pack()

        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

    def create_tool_button(self, parent: ttk.Frame, tool: ToolInfo, index: int):
        """Create a styled button for a tool"""
        # Tool container frame
        tool_frame = ttk.Frame(parent, relief='solid', borderwidth=1, padding="15")
        tool_frame.grid(row=index, column=0, sticky=(tk.W, tk.E), pady=10)

        # Tool name
        name_label = ttk.Label(
            tool_frame,
            text=tool.name,
            font=('Arial', 14, 'bold')
        )
        name_label.grid(row=0, column=0, sticky=tk.W)

        # Tool description
        desc_label = ttk.Label(
            tool_frame,
            text=tool.description,
            font=('Arial', 10),
            foreground='gray',
            wraplength=500
        )
        desc_label.grid(row=1, column=0, sticky=tk.W, pady=(5, 10))

        # Launch button
        launch_btn = ttk.Button(
            tool_frame,
            text="Launch",
            command=lambda t=tool: self.launch_tool(t),
            width=15
        )
        launch_btn.grid(row=2, column=0, sticky=tk.W)

        # Configure column weight
        tool_frame.columnconfigure(0, weight=1)

    def launch_tool(self, tool: ToolInfo):
        """Launch a tool in a separate thread"""
        try:
            # Import the tool module
            module = importlib.import_module(tool.module_name)

            # Get the main function
            if not hasattr(module, tool.main_func):
                messagebox.showerror(
                    "Error",
                    f"Tool '{tool.name}' does not have a '{tool.main_func}' function"
                )
                return

            main_func = getattr(module, tool.main_func)

            # Launch in a separate thread to keep launcher responsive
            thread = threading.Thread(target=main_func, daemon=True)
            thread.start()

            # Show confirmation
            self.show_launch_notification(tool.name)

        except ImportError as e:
            messagebox.showerror(
                "Import Error",
                f"Failed to import tool '{tool.name}':\n\n{str(e)}\n\n"
                f"Make sure the tool is installed in the workspace."
            )
        except Exception as e:
            messagebox.showerror(
                "Launch Error",
                f"Failed to launch '{tool.name}':\n\n{str(e)}"
            )

    def show_launch_notification(self, tool_name: str):
        """Show a brief notification that a tool was launched"""
        # Create a temporary label that fades out
        notification = tk.Toplevel(self.root)
        notification.title("Tool Launched")
        notification.geometry("300x80")
        notification.resizable(False, False)

        # Center it on screen
        notification.update_idletasks()
        x = (notification.winfo_screenwidth() // 2) - (300 // 2)
        y = (notification.winfo_screenheight() // 2) - (80 // 2)
        notification.geometry(f"+{x}+{y}")

        # Notification message
        msg_label = ttk.Label(
            notification,
            text=f"{tool_name} launched!",
            font=('Arial', 12),
            padding=20
        )
        msg_label.pack(expand=True)

        # Auto-close after 1.5 seconds
        notification.after(1500, notification.destroy)


def main():
    """Main entry point for the launcher"""
    root = tk.Tk()
    app = UtilsLauncher(root)
    root.mainloop()


if __name__ == "__main__":
    main()
