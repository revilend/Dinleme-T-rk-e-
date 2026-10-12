"""Sozlamalar: `.env` faylidan o'qiladi va butun loyiha bo'ylab ishlatiladi."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# .env loyiha ildizidan yuklanadi (mavjud bo'lmasa jim o'tib ketadi)
load_dotenv(BASE_DIR / ".env")


def _parse_admin_ids(raw: str) -> frozenset[int]:
    """`ADMIN_IDS=123,456 789` -> {123, 456, 789}"""
    ids: set[int] = set()
    for chunk in raw.replace(";", ",").replace(" ", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            ids.add(int(chunk))
        except ValueError:
            continue
    return frozenset(ids)


BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS: frozenset[int] = _parse_admin_ids(os.getenv("ADMIN_IDS", ""))

_db_path = Path(os.getenv("DB_PATH") or "bot.db")
DB_PATH: Path = _db_path if _db_path.is_absolute() else BASE_DIR / _db_path


def is_admin(user_id: int | None) -> bool:
    """Foydalanuvchi adminlar ro'yxatida bor-yo'qligini tekshiradi."""
    return user_id is not None and user_id in ADMIN_IDS
