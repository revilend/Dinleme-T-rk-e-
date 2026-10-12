"""Telegram interfeysi uchun kichik yordamchi funksiyalar (user va admin uchun umumiy)."""

from __future__ import annotations

import logging

from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

logger = logging.getLogger(__name__)


async def safe_answer(
    callback: CallbackQuery,
    text: str | None = None,
    *,
    show_alert: bool = False,
) -> None:
    """`callback.answer()` xatolarini yutadi (eski tugma, tarmoq va h.k.)."""
    try:
        await callback.answer(text, show_alert=show_alert)
    except TelegramAPIError as error:
        logger.debug("callback.answer() xatosi: %s", error)


async def render_message(
    message: Message,
    text: str,
    keyboard: InlineKeyboardMarkup | None = None,
) -> None:
    """Menyu xabarini yangilaydi; imkoni bo'lmasa yangi xabar yuboradi.

    Audio (yoki rasm) xabari tahrirlana olmaydi — bunday holatda eski
    tugmalar olib tashlanadi va matn yangi xabar sifatida yuboriladi.
    """
    try:
        await message.edit_text(text, reply_markup=keyboard)
        return
    except TelegramBadRequest:
        pass
    except TelegramAPIError as error:
        logger.debug("edit_text xatosi: %s", error)
        return

    try:
        await message.edit_reply_markup(reply_markup=None)
    except TelegramAPIError:
        pass

    try:
        await message.answer(text, reply_markup=keyboard)
    except TelegramAPIError as error:  # pragma: no cover - tarmoq xatolari
        logger.warning("Xabar yuborilmadi: %s", error)


async def render(
    callback: CallbackQuery,
    text: str,
    keyboard: InlineKeyboardMarkup | None = None,
) -> None:
    """`render_message` ning callback uchun qulay ko'rinishi."""
    if isinstance(callback.message, Message):
        await render_message(callback.message, text, keyboard)
