"""SQLite ma'lumotlar bazasi bilan ishlash (aiosqlite, to'liq asinxron).

Jadvallar
---------
users  : user_id (PK), username, full_name, joined_date
audios : lesson_id (PK, 1..34), file_id, caption, created_at

Audio fayllar serverda saqlanmaydi: Telegram yuklagan faylning `file_id` si
bazaga yoziladi, bot esa o'quvchilarga shu `file_id` orqali bir zumda
yuboradi.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from config import BASE_DIR, DB_PATH
from lessons import TOTAL_LESSONS

logger = logging.getLogger(__name__)

# Disk ulanmagan bo'lsa ishlatiladigan zaxira baza fayli (bepul Render web service kabi)
FALLBACK_DB_PATH = BASE_DIR / "bot.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    username    TEXT,
    full_name   TEXT,
    joined_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audios (
    lesson_id  INTEGER PRIMARY KEY,
    file_id    TEXT NOT NULL,
    caption    TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_joined_date ON users (joined_date);
"""

_conn: aiosqlite.Connection | None = None
_db_path: Path = DB_PATH


def now_iso() -> str:
    """UTC vaqt (sekund aniqligida)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _db() -> aiosqlite.Connection:
    if _conn is None:
        raise RuntimeError("Ma'lumotlar bazasi ochilmagan — avval `await init_db()` chaqirilsin.")
    return _conn


def _prepare_path(path: Path) -> Path:
    """Baza uchun papkani tayyorlaydi va TAYYOR fayl yo'lini qaytaradi."""
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def effective_db_path() -> Path:
    """Haqiqatda ishlatilayotgan baza fayli (zaxira rejimga o'tilgan bo'lishi mumkin)."""
    return _db_path


async def init_db(path: str | Path | None = None) -> None:
    """Bazani ochadi va jadvallarni yaratadi (bir necha marta chaqirish xavfsiz).

    Agar `DB_PATH` papkasi yaratilmasa yoki faylni ochib bo'lmasa (masalan Render'da
    doimiy disk ulanmagan bo'lsa), bot yiqilmaydi — lokal zaxira bazaga o'tadi va
    ogohlantirish yozadi. Bu rejimda baza efemer bo'ladi: har deplo'yda tozalanadi.
    """
    global _conn, _db_path
    if _conn is not None:
        return

    requested = Path(path) if path else DB_PATH
    try:
        _db_path = _prepare_path(requested)
        _conn = await aiosqlite.connect(_db_path)
    except (OSError, sqlite3.OperationalError) as error:
        if requested == FALLBACK_DB_PATH:
            raise
        logger.warning(
            "⚠️ %s ochilmadi (%s). Zaxira bazaga o'tildi: %s — bu rejimda baza "
            "deploy/restartda tozalanadi (doimiy disk ulash tavsiya etiladi).",
            requested,
            error,
            FALLBACK_DB_PATH,
        )
        _db_path = _prepare_path(FALLBACK_DB_PATH)
        _conn = await aiosqlite.connect(_db_path)

    _conn.row_factory = aiosqlite.Row
    await _conn.execute("PRAGMA journal_mode=WAL")
    await _conn.execute("PRAGMA foreign_keys=ON")
    await _conn.executescript(SCHEMA)
    await _conn.commit()


async def close_db() -> None:
    global _conn
    if _conn is not None:
        await _conn.close()
        _conn = None


# ---------------------------------------------------------------------------
# Foydalanuvchilar
# ---------------------------------------------------------------------------
async def add_user(user_id: int, username: str | None, full_name: str | None) -> bool:
    """Foydalanuvchini saqlaydi/yangilaydi. Yangi qo'shilgan bo'lsa True qaytaradi."""
    db = _db()
    async with db.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)) as cur:
        exists = await cur.fetchone() is not None

    if exists:
        await db.execute(
            "UPDATE users SET username = ?, full_name = ? WHERE user_id = ?",
            (username, full_name, user_id),
        )
    else:
        await db.execute(
            "INSERT INTO users (user_id, username, full_name, joined_date) VALUES (?, ?, ?, ?)",
            (user_id, username, full_name, now_iso()),
        )
    await db.commit()
    return not exists


async def get_user(user_id: int) -> dict | None:
    async with _db().execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
        row = await cur.fetchone()
    return dict(row) if row else None


async def get_all_user_ids() -> list[int]:
    """Broadcast uchun barcha foydalanuvchilar ID ro'yxati."""
    async with _db().execute("SELECT user_id FROM users ORDER BY joined_date") as cur:
        rows = await cur.fetchall()
    return [int(row["user_id"]) for row in rows]


async def count_users() -> int:
    async with _db().execute("SELECT COUNT(*) AS c FROM users") as cur:
        row = await cur.fetchone()
    return int(row["c"]) if row else 0


async def count_users_joined_since(iso_date: str) -> int:
    """Masalan: bugun qo'shilganlar soni (YYYY-MM-DD)."""
    async with _db().execute(
        "SELECT COUNT(*) AS c FROM users WHERE substr(joined_date, 1, 10) = ?", (iso_date,)
    ) as cur:
        row = await cur.fetchone()
    return int(row["c"]) if row else 0


# ---------------------------------------------------------------------------
# Audiolar (file_id)
# ---------------------------------------------------------------------------
async def save_audio(lesson_id: int, file_id: str, caption: str | None = None) -> None:
    """Audioni (yoki mavjudini) saqlaydi — bir xil dars uchun yangilanadi."""
    await _db().execute(
        """
        INSERT INTO audios (lesson_id, file_id, caption, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(lesson_id) DO UPDATE SET
            file_id    = excluded.file_id,
            caption    = excluded.caption,
            created_at = excluded.created_at
        """,
        (lesson_id, file_id, caption, now_iso()),
    )
    await _db().commit()


async def get_audio(lesson_id: int) -> dict | None:
    async with _db().execute("SELECT * FROM audios WHERE lesson_id = ?", (lesson_id,)) as cur:
        row = await cur.fetchone()
    return dict(row) if row else None


async def get_audio_file_id(lesson_id: int) -> str | None:
    audio = await get_audio(lesson_id)
    return str(audio["file_id"]) if audio else None


async def delete_audio(lesson_id: int) -> bool:
    """Audioni o'chiradi. O'chirilgan bo'lsa True qaytaradi."""
    cur = await _db().execute("DELETE FROM audios WHERE lesson_id = ?", (lesson_id,))
    await _db().commit()
    return cur.rowcount > 0


async def get_uploaded_lesson_ids() -> set[int]:
    """Qaysi darslarga audio yuklanganini bildiruvchi to'plam."""
    async with _db().execute("SELECT lesson_id FROM audios") as cur:
        rows = await cur.fetchall()
    return {int(row["lesson_id"]) for row in rows}


async def count_audios() -> int:
    async with _db().execute("SELECT COUNT(*) AS c FROM audios") as cur:
        row = await cur.fetchone()
    return int(row["c"]) if row else 0


# ---------------------------------------------------------------------------
# Statistika
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Zaxiralash (backup) va tiklash (restore)
# ---------------------------------------------------------------------------
REQUIRED_TABLES: tuple[str, ...] = ("users", "audios")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _inspect_backup(path: Path) -> dict[str, int]:
    """Zaxira faylini tekshiradi (sinxron — `asyncio.to_thread` ichida chaqiriladi).

    Returns: {"users": n, "audios": n}
    Raises: ValueError — fayl baza emas, buzilgan yoki kerakli jadvallar yo'q.
    """
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError("fayl bo'sh yoki mavjud emas")

    try:
        # read-only rejimda ochamiz: yaroqsiz fayl ustida hech narsa o'zgarmasin
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error as error:
        raise ValueError(f"faylni ochib bo'lmadi: {error}") from error

    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()
        if not integrity or str(integrity[0]).lower() != "ok":
            raise ValueError(f"baza butunligi buzilgan (integrity_check={integrity})")

        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        missing = [name for name in REQUIRED_TABLES if name not in tables]
        if missing:
            raise ValueError(f"kerakli jadvallar yo'q: {', '.join(missing)}")

        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        audios = conn.execute("SELECT COUNT(*) FROM audios").fetchone()[0]
        return {"users": int(users), "audios": int(audios)}
    except sqlite3.DatabaseError as error:
        raise ValueError(f"sqlite xatosi: {error}") from error
    finally:
        conn.close()


async def inspect_backup(path: str | Path) -> dict[str, int]:
    """Zaxira faylini asinxron tekshiradi (event loop bloklanmaydi)."""
    return await asyncio.to_thread(_inspect_backup, Path(path))


async def create_backup(destination: str | Path) -> Path:
    """Bazaning izchil nusxasini yaratadi (`VACUUM INTO` — WAL rejimida ham xavfsiz)."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.unlink(missing_ok=True)  # VACUUM INTO mavjud fayl ustiga yozmaydi
    await _db().execute("VACUUM INTO ?", (str(destination),))
    return destination


def _cleanup_old_copies(target: Path, keep: Path) -> None:
    """Faqat oxirgi xavfsizlik nusxasini qoldiradi."""
    for old in target.parent.glob(f"{target.name}.before-restore-*"):
        if old != keep:
            old.unlink(missing_ok=True)


async def restore_from_file(source: str | Path) -> Path:
    """Joriy bazani zaxira fayl bilan almashtiradi va qayta ochadi.

    Xavfsizlik uchun almashtirishdan oldingi baza `<baza>.before-restore-<vaqt>`
    nomi bilan saqlanadi; yangi baza ochilmasa, eski baza qaytariladi.

    Returns: saqlangan eski baza faylining yo'li.
    """
    source = Path(source)
    target = _db_path
    safety = target.with_name(f"{target.name}.before-restore-{_stamp()}")

    await close_db()
    try:
        if target.exists():
            os.replace(target, safety)
        # eski WAL jurnallari yangi faylga qo'shilib ketmasligi uchun o'chiramiz
        for suffix in ("-wal", "-shm"):
            Path(f"{target}{suffix}").unlink(missing_ok=True)
        shutil.copyfile(source, target)
        await init_db(target)
    except Exception:
        logger.exception("Bazani tiklashda xatolik — eski baza qaytarilmoqda")
        await close_db()
        target.unlink(missing_ok=True)
        if safety.exists():
            os.replace(safety, target)
        await init_db(target)
        raise

    _cleanup_old_copies(target, keep=safety)
    logger.info("Baza tiklandi: %s (eski nusxa: %s)", target, safety.name)
    return safety


async def get_stats() -> dict[str, int]:
    """Admin panel uchun qisqa statistika."""
    uploaded = await count_audios()
    today = now_iso()[:10]
    return {
        "users": await count_users(),
        "users_today": await count_users_joined_since(today),
        "uploaded": uploaded,
        "total_lessons": TOTAL_LESSONS,
        "missing": max(TOTAL_LESSONS - uploaded, 0),
    }
