#!/usr/bin/env python3
"""🎧 Turk Tili A1 Fundamental — Dinleme (audio) Telegram boti.

Kitobdagi QR-kod orqali kirgan o'quvchilarga 34 ta darsning Dinleme
audiolarini yetkazib beradi. Adminlar Telegram'ning o'zidan turib istalgan
darsga MP3 audio yuklashi, yangilashi va o'chirishi mumkin (audio faylning
`file_id` si SQLite bazada saqlanadi).

Ishga tushirish:
    pip install -r requirements.txt
    cp .env.example .env        # BOT_TOKEN va ADMIN_IDS ni to'ldiring
    python main.py

Talablar: Python 3.11+ (3.10 da ham ishlaydi), aiogram 3.x, aiosqlite.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

import database as db
import handlers_admin
import handlers_user
from config import ADMIN_IDS, BOT_TOKEN
from lessons import TOTAL_LESSONS, MODULES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("aiogram.event").setLevel(logging.WARNING)
logger = logging.getLogger("turk-tili-a1-bot")


async def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit(
            "❌ BOT_TOKEN topilmadi. `.env.example` dan nusxa olib `.env` yarating "
            "va @BotFather'dan olingan tokenni kiriting."
        )
    if not ADMIN_IDS:
        logger.warning("⚠️ ADMIN_IDS bo'sh — admin panel hech kimga ko'rinmaydi (faqat o'quvchilar menyusi).")

    await db.init_db()
    stats = await db.get_stats()
    logger.info(
        "Baza tayyor: %s | foydalanuvchilar: %d | audiolar: %d/%d",
        db.effective_db_path(),
        stats["users"],
        stats["uploaded"],
        stats["total_lessons"],
    )

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

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        await db.close_db()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot to'xtatildi.")
    except SystemExit as stop:
        # Sozlama xatosi bo'lsa xabar chiqadi va jarayon nolga teng bo'lmagan kod bilan
        # tugaydi (systemd/Docker qayta ishga tushirishni to'g'ri aniqlashi uchun).
        if stop.code in (None, 0):
            logger.info("Bot to'xtatildi.")
        else:
            print(stop.code, file=sys.stderr)
            raise SystemExit(1) from None
