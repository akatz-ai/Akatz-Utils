"""Akatz Utils Launcher - Web-based hub for utility tools."""

import threading
import webbrowser

__version__ = "0.1.0"


def main() -> None:
    """Start the Flask server and open the browser."""
    from .app import create_app

    app = create_app()
    port = 5000

    # Open browser after a short delay to let the server start
    def open_browser():
        import time
        time.sleep(0.8)
        webbrowser.open(f"http://localhost:{port}")

    threading.Thread(target=open_browser, daemon=True).start()

    print(f"Akatz Utils Hub running at http://localhost:{port}")
    print("Press Ctrl+C to stop")
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
