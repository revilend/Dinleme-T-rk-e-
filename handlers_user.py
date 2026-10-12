"""O'quvchilar (user) uchun handlerlar: /start, modul/dars menyusi va audio yetkazish."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import database as db
from config import is_admin
from lessons import (
    ABOUT_TEXT,
    EXAM_TEXT,
    LESSON_BY_NO,
    MODULE_BY_NO,
    lesson_caption,
    lesson_kb,
    main_menu_kb,
    missing_audio_text,
    module_kb,
    module_text,
    start_text,
)
from ui import render, render_message, safe_answer

logger = logging.getLogger(__name__)

router = Router(name="user")


def _full_name(message: Message) -> str | None:
    user = message.from_user
    if user is None:
        return None
    return " ".join(part for part in (user.first_name, user.last_name) if part) or None


def _is_stale_file_error(error: TelegramAPIError) -> bool:
    """Telegram `file_id` endi yaroqsiz bo'lib qolganini aniqlaydi."""
    text = str(error).lower()
    return any(
        marker in text
        for marker in ("wrong file identifier", "file_id_invalid", "file reference", "wrong remote file")
    )


async def send_lesson_audio(message: Message, lesson_no: int) -> bool:
    """Bazadagi `file_id` orqali audioni yuboradi.

    True  — audio yuborildi,
    False — audio hali yuklanmagan (yoki yaroqsiz), foydalanuvchiga xabar beriladi.
    """
    lesson = LESSON_BY_NO[lesson_no]
    audio = await db.get_audio(lesson_no)

    if not audio:
        await render_message(message, missing_audio_text(lesson), lesson_kb(lesson))
        return False

    caption = (audio.get("caption") or "").strip() or lesson_caption(lesson)

    try:
        await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.UPLOAD_VOICE)
    except TelegramAPIError:
        pass

    try:
        await message.answer_audio(
            audio=str(audio["file_id"]),
            title=lesson.label,
            performer=f"Turk Tili A1 — {lesson.title}",
            caption=caption,
            reply_markup=lesson_kb(lesson),
        )
    except TelegramAPIError as error:
        logger.warning("%d-dars audiosini yuborishda xatolik: %s", lesson_no, error)
        if _is_stale_file_error(error):
            # Telegram'dagi fayl o'chib ketgan — yozuvni tozalaymiz, admin qayta yuklaydi
            await db.delete_audio(lesson_no)
            logger.warning("%d-dars uchun eskirgan file_id bazadan o'chirildi", lesson_no)
        await render_message(message, missing_audio_text(lesson), lesson_kb(lesson))
        return False

    return True


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()  # admin FSM holati ochiq qolib ketmasin
    user = message.from_user
    if user is not None:
        is_new = await db.add_user(user.id, user.username, _full_name(message))
        logger.info(
            "%s foydalanuvchi: %s (@%s)",
            "Yangi" if is_new else "Qaytgan",
            user.id,
            user.username or "—",
        )
    await message.answer(
        start_text(user.first_name if user else None),
        reply_markup=main_menu_kb(is_admin(user.id if user else None)),
    )


@router.message(Command("help", "yordam"))
async def cmd_help(message: Message) -> None:
    user = message.from_user
    await message.answer(
        ABOUT_TEXT,
        reply_markup=main_menu_kb(is_admin(user.id if user else None)),
    )


@router.callback_query(F.data == "home")
async def cb_home(callback: CallbackQuery) -> None:
    await safe_answer(callback)
    user = callback.from_user
    await render(
        callback,
        start_text(user.first_name if user else None),
        main_menu_kb(is_admin(user.id)),
    )


@router.callback_query(F.data.startswith("m:"))
async def cb_module(callback: CallbackQuery) -> None:
    try:
        module = MODULE_BY_NO[int((callback.data or "").split(":", 1)[1])]
    except (IndexError, ValueError, KeyError):
        await safe_answer(callback, "❌ Noto'g'ri tanlov. /start dan foydalaning.", show_alert=True)
        return

    await safe_answer(callback)
    await render(callback, module_text(module), module_kb(module))


@router.callback_query(F.data.startswith("l:"))
async def cb_lesson(callback: CallbackQuery) -> None:
    try:
        lesson = LESSON_BY_NO[int((callback.data or "").split(":", 1)[1])]
    except (IndexError, ValueError, KeyError):
        await safe_answer(callback, "❌ Noto'g'ri tanlov. /start dan foydalaning.", show_alert=True)
        return

    await safe_answer(callback, "🎧 Audio yuborilmoqda...")

    message = callback.message
    if not isinstance(message, Message):
        return

    sent = await send_lesson_audio(message, lesson.no)
    if sent:
        # Menyu xabaridagi tugmalarni olib tashlaymiz — navigatsiya audio ostida qoladi
        try:
            await message.edit_reply_markup(reply_markup=None)
        except TelegramAPIError:
            pass


@router.callback_query(F.data == "x:exam")
async def cb_exam(callback: CallbackQuery) -> None:
    await safe_answer(callback)
    await render(callback, EXAM_TEXT, main_menu_kb(is_admin(callback.from_user.id)))


@router.callback_query(F.data == "x:about")
async def cb_about(callback: CallbackQuery) -> None:
    await safe_answer(callback)
    await render(callback, ABOUT_TEXT, main_menu_kb(is_admin(callback.from_user.id)))


@router.message()
async def fallback(message: Message) -> None:
    user = message.from_user
    await message.answer(
        "Menyuni ochish uchun /start buyrug'ini yuboring 👇",
        reply_markup=main_menu_kb(is_admin(user.id if user else None)),
    )
