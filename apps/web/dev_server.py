"""前端 dev server: 静态文件服务, 端口 18182.

Usage:
    .venv/Scripts/python.exe apps/web/dev_server.py
"""

from __future__ import annotations

import http.server
import socketserver
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parent
PORT = 18182


class _Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def end_headers(self):
        # 避免缓存, 让修改立刻生效
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        pass  # 静默


if __name__ == "__main__":
    with socketserver.TCPServer(("127.0.0.1", PORT), _Handler) as httpd:
        print(f"apps/web dev server: http://127.0.0.1:{PORT}/")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
