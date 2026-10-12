#!/usr/bin/env python3
"""🎧 Turk Tili A1 Fundamental — Dinleme (audio) Telegram boti.

Render'da **Web Service** sifatida ishga tushiriladi (`python bot.py`):
`dp.start_polling(bot)` (aiogram long-polling) va aiohttp healthcheck serveri
bitta asyncio loopda parallel ishlaydi. Render `PORT` env o'zgaruvchisiga
eshhitadi, shuning uchun bot portni ochishda kechikmasdan "healthy" bo'ladi.

Xizmat nuqtalari:
    GET /        -> 200 OK
    GET /health  -> 200 OK

Ishga tushirish:
    pip install -r requirements.txt
    cp .env.example .env        # BOT_TOKEN va ADMIN_IDS ni to'ldiring
    python bot.py               # (python main.py ham ishlaydi)

Talablar: Python 3.11+ (3.10 da ham ishlaydi), aiogram 3.x, aiohttp, aiosqlite.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

import database as db
import handlers_admin
import handlers_user
from config import ADMIN_IDS, BOT_TOKEN
from lessons import MODULES, TOTAL_LESSONS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("aiogram.event").setLevel(logging.WARNING)
logger = logging.getLogger("turk-tili-a1-bot")

HOST = "0.0.0.0"


def _port() -> int:
    """Render $PORT ni o'qiydi (standart: 10000). Noto'g'ri qiymatda 10000 ga tushadi."""
    raw = (os.getenv("PORT") or "10000").strip()
    try:
        return int(raw)
    except ValueError:
        logger.warning("PORT noto'g'ri qiymat (%r) — 10000 ishlatiladi", raw)
        return 10000


PORT = _port()


async def _ok_handler(request: web.Request) -> web.Response:
    """Render healthcheck uchun javob (200 OK)."""
    return web.Response(text="OK", status=200)


async def start_http_server() -> web.AppRunner:
    """`0.0.0.0:$PORT` da kichkina HTTP server ochadi (`/` va `/health` -> 200 OK)."""
    app = web.Application()
    app.router.add_get("/", _ok_handler)
    app.router.add_get("/health", _ok_handler)
    # access_log: Render logida so'rovlar shovqin qilmasin
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, HOST, PORT)
    await site.start()
    return runner


async def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit(
            "❌ BOT_TOKEN topilmadi. `.env.example` dan nusxa olib `.env` yarating "
            "yoki Render'da Environment bo'limiga kiriting."
        )
    if not ADMIN_IDS:
        logger.warning("⚠️ ADMIN_IDS bo'sh — admin panel hech kimga ko'rinmaydi (faqat o'quvchilar menyusi).")

    # 1) Avval port ochamiz — Render port skanerida kechikmasin
    runner = await start_http_server()
    logger.info("HTTP server tayyor: http://%s:%d/ va /health", HOST, PORT)

    try:
        # 2) Baza
        await db.init_db()
        stats = await db.get_stats()
        logger.info(
            "Baza tayyor: %s | foydalanuvchilar: %d | audiolar: %d/%d",
            db.effective_db_path(),
            stats["users"],
            stats["uploaded"],
            stats["total_lessons"],
        )

        # 3) Bot va routerlar
        bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        dp = Dispatcher(storage=MemoryStorage())

        # Admin router birinchi ulanadi: FSM holatlari va /admin avval shu yerda tekshiriladi
        dp.include_router(handlers_admin.router)
        dp.include_router(handlers_user.router)

        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Darslar menyusi"),
                BotCommand(command="help", description="Kitob haqida va yordam"),
                BotCommand(command="admin", description="👑 Admin panel"),
                BotCommand(command="bekor", description="Amalni bekor qilish"),
            ]
        )
        await bot.delete_webhook(drop_pending_updates=False)

        me = await bot.get_me()
        logger.info(
            "Bot ishga tushdi: @%s | %d dars, %d modul | adminlar: %d ta",
            me.username,
            TOTAL_LESSONS,
            len(MODULES),
            len(ADMIN_IDS),
        )

        # 4) Long-polling (HTTP server shu loopda parallel ishlayveradi)
        try:
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        finally:
            await bot.session.close()
    finally:
        await runner.cleanup()
        await db.close_db()


def run() -> None:
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot to'xtatildi.")
    except SystemExit as stop:
        # Sozlama xatosi: xabar chiqadi va jarayon 1-kod bilan tugaydi
        if stop.code in (None, 0):
            logger.info("Bot to'xtatildi.")
        else:
            print(stop.code, file=sys.stderr)
            raise SystemExit(1) from None


if __name__ == "__main__":
    run()
