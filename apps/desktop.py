"""python -m apps.desktop  — native window around the Floor Brief website."""

from __future__ import annotations

import socket
import threading
import time
import urllib.request

import uvicorn
import webview

from apps.api import app


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> None:
    port = _free_port()
    thread = threading.Thread(
        target=lambda: uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning"),
        daemon=True,
    )
    thread.start()
    url = f"http://127.0.0.1:{port}/"
    for _ in range(180):
        try:
            urllib.request.urlopen(url + "api/health", timeout=1)
            break
        except Exception:
            time.sleep(0.25)
    webview.create_window(
        "Floor Brief",
        url,
        width=1320,
        height=880,
        min_size=(960, 640),
    )
    webview.start()


if __name__ == "__main__":
    main()
