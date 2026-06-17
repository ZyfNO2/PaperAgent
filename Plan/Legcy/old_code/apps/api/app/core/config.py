"""Runtime configuration.

Phase 01 仅暴露 SQLite DSN；后续 Phase 会追加 PostgreSQL、LiteLLM、
Langfuse、Docling、MinIO 等配置。
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# __file__ = apps/api/app/core/config.py
# parents[0]=core [1]=app [2]=api [3]=apps [4]=<repo root>
PROJECT_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TOPICPILOT_",
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    sqlite_path: str = str(PROJECT_ROOT / "data" / "topicpilot.db")


def _sqlite_dsn(path: str) -> str:
    """构造 SQLite async DSN。

    强制把相对路径解析为绝对路径，避免 uvicorn 在 ``--app-dir apps/api``
    启动时 cwd 是 apps/api、相对路径解析到错地方。
    """

    absolute = Path(path).expanduser().resolve()
    absolute.parent.mkdir(parents=True, exist_ok=True)
    # Windows 路径 ``G:/...`` 要转 ``G:\\...``，否则 SQLAlchemy 会把它
    # 当成 URI scheme 后面的 relative 路径处理，落库到 cwd 下的同名目录。
    return f"sqlite+aiosqlite:///{absolute.as_posix()}"


settings = Settings()
DATABASE_URL = _sqlite_dsn(settings.sqlite_path)
