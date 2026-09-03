"""python -m apps.desktop  — native window around the Floor Brief website."""

from __future__ import annotations

import socket
import threading
import time
import urllib.request
from pathlib import Path

import uvicorn
import webview

from apps.api import app
from apps.pdf_export import peek_pdf_export, take_pdf_export

webview.settings["ALLOW_DOWNLOADS"] = True


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
    class Bridge:
        def save_pdf(self, token: str, filename: str = "floor-brief.pdf") -> bool:
            row = peek_pdf_export(str(token or ""))
            if not row:
                return False
            suggested, data = row
            window = webview.windows[0]
            choice = window.create_file_dialog(
                webview.FileDialog.SAVE,
                directory=str(Path.home() / "Downloads"),
                save_filename=suggested or filename,
                file_types=("PDF (*.pdf)",),
            )
            if not choice:
                return False
            path = choice if isinstance(choice, str) else choice[0]
            Path(path).write_bytes(data)
            take_pdf_export(str(token or ""))
            return True

    webview.create_window(
        "Floor Brief",
        url,
        width=1320,
        height=880,
        min_size=(960, 640),
        js_api=Bridge(),
    )
    webview.start()


if __name__ == "__main__":
    main()
