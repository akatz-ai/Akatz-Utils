"""Akatz Utils Launcher - Web-based hub for utility tools."""

import argparse
import threading
import webbrowser

__version__ = "0.1.0"


def _browser_host(host: str) -> str:
    if host in {"0.0.0.0", "::"}:
        return "localhost"
    return host


def main() -> None:
    """Start the Flask server and open the browser."""
    from .app import create_app

    parser = argparse.ArgumentParser(prog="akatz-utils")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host interface to bind. Use 0.0.0.0 to expose on your LAN/Tailnet.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port to bind.",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open the hub in a browser after starting.",
    )
    args = parser.parse_args()

    app = create_app()
    host = args.host
    port = args.port
    browser_url = f"http://{_browser_host(host)}:{port}"
    bind_url = f"http://{host}:{port}"

    if not args.no_browser:
        # Open browser after a short delay to let the server start
        def open_browser():
            import time
            time.sleep(0.8)
            webbrowser.open(browser_url)

        threading.Thread(target=open_browser, daemon=True).start()

    print(f"Akatz Utils Hub running at {bind_url}")
    if host == "0.0.0.0":
        print(f"Local browser URL: {browser_url}")
    print("Press Ctrl+C to stop")
    app.run(host=host, port=port, debug=False, threaded=True)
