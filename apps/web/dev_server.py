"""Mini static file server for apps/web (dev only).

MVP: 用 http.server 在 18182 端口 serve index.html / app.js / styles.css,
e2e 测试通过 http://127.0.0.1:18182 访问 (与后端 uvicorn 18181 分开)。
"""

from __future__ import annotations

import http.server
import os
import socketserver
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("WEB_PORT", "18182"))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        # 避免浏览器缓存
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, format, *args):  # noqa: A002
        # 静默日志
        pass


def main() -> int:
    print(f"[web_dev] serving {ROOT} at http://127.0.0.1:{PORT}", flush=True)
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        httpd.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
