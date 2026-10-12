"""👑 Admin panel: audio yuklash/yangilash/o'chirish (FSM), statistika va broadcast.

Faqat `ADMIN_IDS` dagi foydalanuvchilar uchun ishlaydi. Audio fayl serverda
saqlanmaydi: Telegram qaytargan `file_id` bazaga yoziladi va o'quvchilarga shu
`file_id` orqali yuboriladi (tez va serverda joy egallamaydi).
"""

from __future__ import annotations

import asyncio
import io
import logging
import tempfile
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from aiogram.filters import BaseFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    FSInputFile,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database as db
from config import TZ_OFFSET_HOURS, is_admin, now_local
from lessons import LESSON_BY_NO, LESSONS_SORTED, lesson_caption
from ui import render, safe_answer

logger = logging.getLogger(__name__)

router = Router(name="admin")

# Broadcast tezligi: Telegram flood limitidan saqlanish uchun kichik pauza
BROADCAST_DELAY = 0.05
# Telegram bot "getFile" cheklovi (MB)
MAX_DOWNLOAD_MB = 20
DOCUMENT_EXTENSIONS = (".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".flac")


class AdminAudio(StatesGroup):
    waiting_audio = State()


class AdminBroadcast(StatesGroup):
    waiting_message = State()


class AdminBackup(StatesGroup):
    waiting_db = State()


class IsAdmin(BaseFilter):
    """Faqat ADMIN_IDS uchun ruxsat beruvchi filtr."""

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        return is_admin(event.from_user.id if event.from_user else None)


class IsNotCommand(BaseFilter):
    """Buyruqlar (/start, /admin, /bekor ...) FSM kutish holatiga tushmasin.

    Shu tufayli admin yuklash/broadcast jarayonida ham /start va /admin
    buyruqlarini bemalol ishlata oladi.
    """

    async def __call__(self, message: Message) -> bool:
        return not (message.text or "").startswith("/")


# ---------------------------------------------------------------------------
# Matnlar va klaviaturalar
# ---------------------------------------------------------------------------
def panel_text(stats: dict[str, int]) -> str:
    return (
        "👑 <b>Admin Panel</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{stats['users']}</b> ta\n"
        f"🎵 Yuklangan audiolar: <b>{stats['uploaded']}/{stats['total_lessons']}</b> ta\n\n"
        "Quyidagi bo'limlardan birini tanlang 👇"
    )


def stats_text(stats: dict[str, int]) -> str:
    percent = round(stats["uploaded"] * 100 / stats["total_lessons"]) if stats["total_lessons"] else 0
    return (
        "📊 <b>Statistika</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{stats['users']}</b> ta\n"
        f"🆕 Bugun qo'shilganlar: <b>{stats['users_today']}</b> ta\n"
        f"🎵 Yuklangan audiolar: <b>{stats['uploaded']}/{stats['total_lessons']}</b> ta\n"
        f"⏳ Yuklanmagan: <b>{stats['missing']}</b> ta\n"
        f"📈 To'liqlik: <b>{percent}%</b>"
    )


def upload_list_text(stats: dict[str, int]) -> str:
    return (
        "🎵 <b>Audio yuklash va yangilash</b>\n\n"
        f"Holat: <b>{stats['uploaded']}/{stats['total_lessons']}</b> ta darsda audio bor\n"
        "✅ — audio yuklangan · ❌ — hali yuklanmagan\n\n"
        "Kerakli darsni tanlang, so'ngra MP3 faylni yuboring:"
    )


def panel_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🎵 Audio yuklash va yangilash", callback_data="a:up")
    kb.button(text="🗑 Audioni o'chirish", callback_data="a:del")
    kb.button(text="📊 Statistika", callback_data="a:stats")
    kb.button(text="📢 Xabar tarqatish", callback_data="a:bcast")
    kb.button(text="💾 Bazani yuklab olish (Backup)", callback_data="a:backup")
    kb.button(text="🔄 Bazani qayta tiklash (Restore)", callback_data="a:restore")
    kb.button(text="🏠 Bosh menyu", callback_data="home")
    kb.adjust(1)
    return kb.as_markup()


def lessons_kb(prefix: str, uploaded: set[int], *, only_uploaded: bool = False) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for lesson in LESSONS_SORTED:
        if only_uploaded and lesson.no not in uploaded:
            continue
        mark = "✅" if lesson.no in uploaded else "❌"
        kb.button(text=f"{lesson.no}-Dars {mark}", callback_data=f"{prefix}:{lesson.no}")
    kb.button(text="⬅️ Admin Panel", callback_data="a:panel")
    kb.adjust(4, repeat=True)
    return kb.as_markup()


def cancel_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Bekor qilish", callback_data="a:panel")
    kb.adjust(1)
    return kb.as_markup()


def audio_prompt(lesson_no: int) -> str:
    lesson = LESSON_BY_NO[lesson_no]
    return (
        f"🎵 <b>{lesson.label}</b>\n\n"
        f"Iltimos, {lesson.no}-dars uchun MP3 audio faylni yuboring "
        "(audio yoki fayl formatda).\n\n"
        f"📎 Tavsiya etilgan nom: <code>{lesson.audio_name}</code>\n"
        "⬅️ Bekor qilish uchun «Bekor qilish» tugmasini bosing yoki /bekor yuboring."
    )


# ---------------------------------------------------------------------------
# Kirish nuqtalari
# ---------------------------------------------------------------------------
@router.message(IsAdmin(), Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    await state.clear()  # ochiq qolgan yuklash/broadcast oqimini to'xtatamiz
    stats = await db.get_stats()
    await message.answer(panel_text(stats), reply_markup=panel_kb())


@router.message(~IsAdmin(), Command("admin"))
async def cmd_admin_denied(message: Message) -> None:
    logger.warning(
        "Admin bo'lmagan foydalanuvchi /admin urindi: %s",
        message.from_user.id if message.from_user else "?",
    )
    await message.answer("❌ Bu bo'lim faqat adminlar uchun.")


@router.callback_query(~IsAdmin(), F.data.startswith("a:"))
async def cb_denied(callback: CallbackQuery) -> None:
    await safe_answer(callback, "❌ Bu bo'lim faqat adminlar uchun.", show_alert=True)


@router.callback_query(IsAdmin(), F.data == "a:panel")
async def cb_panel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await safe_answer(callback)
    stats = await db.get_stats()
    await render(callback, panel_text(stats), panel_kb())


# Har qanday holatda ishlaydigan bekor qilish (FSM kutish holatidan chiqaradi)
@router.message(IsAdmin(), Command("bekor"))
async def cmd_bekor(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("✅ Bekor qilindi.", reply_markup=panel_kb())


# ---------------------------------------------------------------------------
# 1. Audio yuklash / yangilash
# ---------------------------------------------------------------------------
@router.callback_query(IsAdmin(), F.data == "a:up")
async def cb_upload_list(callback: CallbackQuery) -> None:
    await safe_answer(callback)
    uploaded = await db.get_uploaded_lesson_ids()
    stats = await db.get_stats()
    await render(callback, upload_list_text(stats), lessons_kb("a:up", uploaded))


@router.callback_query(IsAdmin(), F.data.startswith("a:up:"))
async def cb_upload_lesson(callback: CallbackQuery, state: FSMContext) -> None:
    try:
        lesson_no = int((callback.data or "").split(":", 2)[2])
        lesson = LESSON_BY_NO[lesson_no]
    except (IndexError, ValueError, KeyError):
        await safe_answer(callback, "❌ Noto'g'ri tanlov.", show_alert=True)
        return

    await state.set_state(AdminAudio.waiting_audio)
    await state.update_data(lesson_no=lesson.no)
    await safe_answer(callback)
    await render(callback, audio_prompt(lesson.no), cancel_kb())


def _document_is_audio(message: Message) -> bool:
    document = message.document
    if document is None:
        return False
    mime = (document.mime_type or "").lower()
    name = (document.file_name or "").lower()
    return mime.startswith("audio/") or name.endswith(DOCUMENT_EXTENSIONS)


@router.message(IsAdmin(), AdminAudio.waiting_audio, F.audio)
async def receive_audio(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lesson = LESSON_BY_NO.get(int(data.get("lesson_no", 0)))
    if lesson is None:
        await state.clear()
        await message.answer("⚠️ Dars tanlanmagan. Iltimos, /admin orqali qaytadan urinib ko'ring.")
        return

    file_id = message.audio.file_id
    await db.save_audio(lesson.no, file_id, lesson_caption(lesson))
    await state.clear()

    logger.info("%d-dars audiosi saqlandi (file_id=%s…)", lesson.no, file_id[:12])
    stats = await db.get_stats()
    await message.answer(
        f"✅ <b>{lesson.no}-Dars audiosi muvaffaqiyatli saqlandi!</b>\n\n"
        f"🎧 {lesson.title}\n"
        f"📦 Yuklangan audiolar: <b>{stats['uploaded']}/{stats['total_lessons']}</b>\n\n"
        "O'quvchilar bu audioni hoziroq eshitishlari mumkin — fayl Telegram "
        "serverida saqlanadi, serverda joy egallamaydi va bir zumda yuklanadi.",
        reply_markup=panel_kb(),
    )


@router.message(IsAdmin(), AdminAudio.waiting_audio, F.document)
async def receive_document(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lesson = LESSON_BY_NO.get(int(data.get("lesson_no", 0)))
    if lesson is None:
        await state.clear()
        await message.answer("⚠️ Dars tanlanmagan. Iltimos, /admin orqali qaytadan urinib ko'ring.")
        return

    if not _document_is_audio(message):
        await message.answer(
            "⚠️ Bu fayl audio formatga o'xshamaydi. Iltimos, MP3 (yoki M4A/OGG/WAV) "
            "fayl yuboring yoki audioni «Audio» sifatida tashlang.\n\n" + audio_prompt(lesson.no),
            reply_markup=cancel_kb(),
        )
        return

    document = message.document
    filename = document.file_name or lesson.audio_name
    size_mb = (document.file_size or 0) / (1024 * 1024)
    if size_mb > MAX_DOWNLOAD_MB:
        await message.answer(
            f"⚠️ Fayl hajmi juda katta (~{size_mb:.1f} MB). Telegram bot faylni "
            f"{MAX_DOWNLOAD_MB} MB gacha qabul qiladi.\n\n"
            "Iltimos, MP3 ni siqib (bitrate'ni kamaytirib) qayta yuboring yoki "
            "faylni «Audio» sifatida tashlang.",
            reply_markup=cancel_kb(),
        )
        return

    # Hujjat sifatida kelgan faylni bir marta qayta yuklaymiz: shunda Telegram
    # haqiqiy "audio" file_id qaytaradi va u sendAudio bilan ishonchli ishlaydi.
    buffer = io.BytesIO()
    try:
        await message.bot.download(document.file_id, destination=buffer)
        sent = await message.answer_audio(
            audio=BufferedInputFile(buffer.getvalue(), filename=filename),
            title=lesson.label,
            performer="Turk Tili A1 — Dinleme",
            caption=f"👑 Yangi yuklangan audio: <b>{lesson.label}</b>",
        )
    except TelegramAPIError as error:
        logger.exception("Hujjatni audio sifatida yuklab bo'lmadi: %s", error)
        await message.answer(
            "❌ Faylni qayta ishlashda xatolik yuz berdi. Iltimos, audioni "
            "«Audio» sifatida yuborib ko'ring yoki boshqa faylni sinab ko'ring.",
            reply_markup=cancel_kb(),
        )
        return

    if sent.audio is None:  # amalda bo'lmaydi, xavfsizlik uchun
        await message.answer("❌ Audio qabul qilinmadi, qaytadan urinib ko'ring.", reply_markup=cancel_kb())
        return

    file_id = sent.audio.file_id
    await db.save_audio(lesson.no, file_id, lesson_caption(lesson))
    await state.clear()

    logger.info("%d-dars audiosi hujjatdan qayta yuklandi (file_id=%s…)", lesson.no, file_id[:12])
    stats = await db.get_stats()
    await message.answer(
        f"✅ <b>{lesson.no}-Dars audiosi muvaffaqiyatli saqlandi!</b>\n\n"
        f"🎧 {lesson.title}\n"
        f"📎 Fayl: <code>{filename}</code> (~{size_mb:.1f} MB)\n"
        f"📦 Yuklangan audiolar: <b>{stats['uploaded']}/{stats['total_lessons']}</b>\n\n"
        "Tekshirish uchun yuqoridagi audioni eshitishingiz mumkin. O'quvchilar "
        "ham uni hoziroq tinglay oladi.",
        reply_markup=panel_kb(),
    )


@router.message(IsAdmin(), AdminAudio.waiting_audio, IsNotCommand())
async def receive_audio_wrong_type(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lesson_no = int(data.get("lesson_no", 0))
    prefix = (
        "⚠️ Iltimos, MP3 audio faylni yuboring (audio yoki fayl formatda).\n\n"
        if lesson_no in LESSON_BY_NO
        else "⚠️ Iltimos, avval /admin orqali darsni tanlang.\n\n"
    )
    await message.answer(
        prefix + (audio_prompt(lesson_no) if lesson_no in LESSON_BY_NO else ""),
        reply_markup=cancel_kb(),
    )


# ---------------------------------------------------------------------------
# 2. Audioni o'chirish
# ---------------------------------------------------------------------------
@router.callback_query(IsAdmin(), F.data == "a:del")
async def cb_delete_list(callback: CallbackQuery) -> None:
    await safe_answer(callback)
    uploaded = await db.get_uploaded_lesson_ids()
    if not uploaded:
        await render(
            callback,
            "🗑 <b>Audioni o'chirish</b>\n\nHozircha hech qanday audio yuklanmagan.",
            panel_kb(),
        )
        return
    await render(
        callback,
        "🗑 <b>Audioni o'chirish</b>\n\n"
        f"O'chirish mumkin bo'lgan darslar: <b>{len(uploaded)}</b> ta\n"
        "Kerakli darsni tanlang — audio bazadan o'chiriladi:",
        lessons_kb("a:del", uploaded, only_uploaded=True),
    )


@router.callback_query(IsAdmin(), F.data.startswith("a:del:"))
async def cb_delete_lesson(callback: CallbackQuery) -> None:
    try:
        lesson = LESSON_BY_NO[int((callback.data or "").split(":", 2)[2])]
    except (IndexError, ValueError, KeyError):
        await safe_answer(callback, "❌ Noto'g'ri tanlov.", show_alert=True)
        return

    deleted = await db.delete_audio(lesson.no)
    await safe_answer(callback, "🗑 O'chirildi" if deleted else "ℹ️ Audio topilmadi")

    if not deleted:
        await render(callback, f"ℹ️ <b>{lesson.label}</b> uchun audio topilmadi.", panel_kb())
        return

    logger.info("%d-dars audiosi o'chirildi", lesson.no)
    stats = await db.get_stats()
    await render(
        callback,
        f"🗑 <b>{lesson.no}-Dars audiosi o'chirildi.</b>\n\n"
        f"🎧 {lesson.title}\n"
        f"📦 Yuklangan audiolar: <b>{stats['uploaded']}/{stats['total_lessons']}</b>\n\n"
        "Endi o'quvchilarga «⏳ Ushbu dars audiosi tez orada yuklanadi» xabari "
        "ko'rsatiladi. Yangi audio yuklash uchun «🎵 Audio yuklash» bo'limidan "
        "foydalanishingiz mumkin.",
        panel_kb(),
    )


# ---------------------------------------------------------------------------
# 3. Statistika
# ---------------------------------------------------------------------------
@router.callback_query(IsAdmin(), F.data == "a:stats")
async def cb_stats(callback: CallbackQuery) -> None:
    await safe_answer(callback)
    await render(callback, stats_text(await db.get_stats()), panel_kb())


# ---------------------------------------------------------------------------
# 4. Xabar tarqatish (broadcast)
# ---------------------------------------------------------------------------
@router.callback_query(IsAdmin(), F.data == "a:bcast")
async def cb_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
    stats = await db.get_stats()
    await state.set_state(AdminBroadcast.waiting_message)
    await safe_answer(callback)
    await render(
        callback,
        "📢 <b>Xabar tarqatish</b>\n\n"
        f"Xabar <b>{stats['users']}</b> ta foydalanuvchiga yuboriladi.\n\n"
        "Iltimos, yubormoqchi bo'lgan xabaringizni jo'natting "
        "(matn, rasm, video, fayl yoki audio).\n"
        "⬅️ Bekor qilish uchun /bekor yuboring.",
        cancel_kb(),
    )


async def _send_broadcast(bot: Bot, user_id: int, from_chat_id: int, message_id: int) -> bool:
    """Bitta foydalanuvchiga xabarni nusxalaydi; flood bo'lsa bir marta kutadi."""
    for attempt in (1, 2):
        try:
            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=from_chat_id,
                message_id=message_id,
            )
            return True
        except TelegramRetryAfter as error:
            if attempt == 2:
                logger.warning("RetryAfter (%s) — %s ga yuborilmadi", error.retry_after, user_id)
                return False
            await asyncio.sleep(error.retry_after + 1)
        except TelegramAPIError as error:
            logger.debug("Broadcast: %s ga yuborilmadi: %s", user_id, error)
            return False
    return False


@router.message(
    IsAdmin(),
    AdminBroadcast.waiting_message,
    IsNotCommand(),
    F.text | F.photo | F.video | F.document | F.audio | F.voice | F.animation | F.sticker,
)
async def broadcast_send(message: Message, state: FSMContext) -> None:
    user_ids = await db.get_all_user_ids()
    await state.clear()

    status = await message.answer(f"📢 Xabar yuborilmoqda: 0/{len(user_ids)} …")
    sent = failed = 0

    for index, user_id in enumerate(user_ids, start=1):
        if await _send_broadcast(message.bot, user_id, message.chat.id, message.message_id):
            sent += 1
        else:
            failed += 1
        if index % 25 == 0 or index == len(user_ids):
            try:
                await status.edit_text(f"📢 Xabar yuborilmoqda: {index}/{len(user_ids)} …")
            except TelegramAPIError:
                pass
        await asyncio.sleep(BROADCAST_DELAY)

    logger.info("Broadcast yakunlandi: yuborildi=%d, xato=%d", sent, failed)
    report = (
        "📢 <b>Xabar tarqatildi</b>\n\n"
        f"✅ Muvaffaqiyatli: <b>{sent}</b> ta\n"
        f"❌ Yetkazilmadi: <b>{failed}</b> ta\n"
        f"👥 Jami foydalanuvchilar: <b>{len(user_ids)}</b> ta\n\n"
        "❌ belgisi odatda botni bloklagan yoki o'chirgan foydalanuvchilarni bildiradi."
    )
    try:
        await status.edit_text(report, reply_markup=panel_kb())
    except TelegramAPIError:
        await message.answer(report, reply_markup=panel_kb())


@router.message(IsAdmin(), AdminBroadcast.waiting_message, IsNotCommand())
async def broadcast_wrong_type(message: Message) -> None:
    await message.answer(
        "⚠️ Iltimos, matn, rasm, video, fayl yoki audio yuboring "
        "(bir nechta media birgalikda yuborilsa, faqat birinchisi tarqatiladi).\n\n"
        "⬅️ Bekor qilish uchun /bekor yuboring.",
        reply_markup=cancel_kb(),
    )


# ---------------------------------------------------------------------------
# 5. Bazani zaxiralash (backup) va tiklash (restore)
# ---------------------------------------------------------------------------
def backup_file_name() -> str:
    """Masalan: bot_backup_2026-10-12_14-35-07.db"""
    return f"bot_backup_{now_local().strftime('%Y-%m-%d_%H-%M-%S')}.db"


def backup_caption(stats: dict[str, int], filename: str) -> str:
    now = now_local()
    return (
        "💾 <b>Baza zaxirasi (backup)</b>\n\n"
        f"🗓 Sana: <b>{now.strftime('%d.%m.%Y')}</b>\n"
        f"🕒 Vaqt: <b>{now.strftime('%H:%M:%S')}</b> (GMT+{TZ_OFFSET_HOURS})\n"
        f"👥 Foydalanuvchilar: <b>{stats['users']}</b> ta\n"
        f"🎵 Yuklangan audiolar: <b>{stats['uploaded']}/{stats['total_lessons']}</b> ta\n"
        f"📦 Fayl: <code>{filename}</code>\n\n"
        "💡 Ushbu faylni «Saqlangan xabarlar» (Saved Messages) ga saqlab qo'ying — "
        "kerak bo'lganda «🔄 Bazani qayta tiklash» orqali tiklaysiz."
    )


def restore_prompt_text(stats: dict[str, int]) -> str:
    return (
        "⚠️ <b>DIQQAT:</b> Yangi baza yuklansa, hozirgi ma'lumotlar almashtiriladi. "
        "Iltimos, avval zaxiralangan <code>.db</code> faylni yuboring:\n\n"
        f"👥 Hozirgi foydalanuvchilar: <b>{stats['users']}</b> ta\n"
        f"🎵 Hozirgi audiolar: <b>{stats['uploaded']}/{stats['total_lessons']}</b> ta\n\n"
        "📎 Fayl «💾 Bazani yuklab olish (Backup)» orqali olingan <code>.db</code> "
        "bo'lishi kerak. Muvaffaqiyatli tiklangach, barcha foydalanuvchilar va "
        "audio <code>file_id</code> lari avvalgi holatiga qaytadi.\n"
        "⬅️ Bekor qilish uchun «Bekor qilish» tugmasini bosing yoki /bekor yuboring."
    )


def restore_success_text(info: dict[str, int], stats: dict[str, int], safety_name: str) -> str:
    return (
        "✅ <b>Baza muvaffaqiyatli tiklandi!</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{stats['users']}</b> ta\n"
        f"🎵 Yuklangan audiolar: <b>{stats['uploaded']}/{stats['total_lessons']}</b> ta\n"
        f"📦 Tiklangan zaxirada: {info['users']} foydalanuvchi, {info['audios']} audio\n\n"
        f"🗂 Oldingi baza xavfsizlik uchun saqlandi: <code>{safety_name}</code>\n\n"
        "Endi o'quvchilar tiklanganki darslarni hoziroq eshitishlari mumkin."
    )


@router.callback_query(IsAdmin(), F.data == "a:backup")
async def cb_backup(callback: CallbackQuery) -> None:
    """Joriy bazani vaqtinchalik faylga nusxalab, Telegram'ga hujjat sifatida yuboradi."""
    message = callback.message
    if not isinstance(message, Message):
        return

    await safe_answer(callback, "💾 Baza tayyorlanmoqda...")
    stats = await db.get_stats()
    filename = backup_file_name()

    try:
        # Vaqtinchalik katalog: fayl yuborilgach diskda qolib ketmaydi
        with tempfile.TemporaryDirectory(prefix="bot-backup-") as tmp:
            path = await db.create_backup(Path(tmp) / filename)
            await message.answer_document(
                document=FSInputFile(path, filename=filename),
                caption=backup_caption(stats, filename),
                reply_markup=panel_kb(),
            )
    except (TelegramAPIError, OSError) as error:
        logger.exception("Backup yuborilmadi: %s", error)
        await message.answer(
            "❌ Bazani yuborishda xatolik yuz berdi. Iltimos, qayta urinib ko'ring.",
            reply_markup=panel_kb(),
        )
        return

    logger.info("Baza zaxirasi yuborildi: %s (%d foydalanuvchi)", filename, stats["users"])


@router.callback_query(IsAdmin(), F.data == "a:restore")
async def cb_restore(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminBackup.waiting_db)
    await safe_answer(callback)
    await render(callback, restore_prompt_text(await db.get_stats()), cancel_kb())


@router.message(IsAdmin(), AdminBackup.waiting_db, F.document)
async def receive_backup_file(message: Message, state: FSMContext) -> None:
    document = message.document
    if document is None:  # pragma: no cover - F.document filtri kafolatlaydi
        return

    filename = document.file_name or "backup.db"
    size_mb = (document.file_size or 0) / (1024 * 1024)
    if size_mb > MAX_DOWNLOAD_MB:
        await message.answer(
            f"⚠️ Fayl hajmi juda katta (~{size_mb:.1f} MB). Telegram bot faylni "
            f"{MAX_DOWNLOAD_MB} MB gacha qabul qiladi.",
            reply_markup=cancel_kb(),
        )
        return

    with tempfile.TemporaryDirectory(prefix="bot-restore-") as tmp:
        incoming = Path(tmp) / "incoming.db"
        try:
            await message.bot.download(document.file_id, destination=incoming)
        except TelegramAPIError as error:
            logger.exception("Zaxira faylini yuklab bo'lmadi: %s", error)
            await message.answer(
                "❌ Faylni yuklab olishda xatolik yuz berdi. Iltimos, qayta yuboring.",
                reply_markup=cancel_kb(),
            )
            return

        try:
            info = await db.inspect_backup(incoming)
        except ValueError as error:
            logger.warning("Yaroqsiz zaxira fayli rad etildi: %s", error)
            await message.answer(
                f"❌ Bu fayl yaroqli baza emas: <i>{error}</i>\n\n"
                "Iltimos, bot «💾 Bazani yuklab olish (Backup)» orqali yuborgan "
                "<code>.db</code> faylni yuboring.",
                reply_markup=cancel_kb(),
            )
            return  # holat saqlanadi — admin qayta urinishi mumkin

        try:
            safety = await db.restore_from_file(incoming)
        except Exception as error:  # noqa: BLE001 - xato foydalanuvchiga ko'rsatiladi
            logger.exception("Bazani tiklab bo'lmadi: %s", error)
            await state.clear()
            await message.answer(
                "❌ Bazani tiklashda xatolik yuz berdi. Eski baza o'z joyiga "
                "qaytarildi, ma'lumotlar yo'qolmadi.",
                reply_markup=panel_kb(),
            )
            return

    await state.clear()
    stats = await db.get_stats()
    logger.info(
        "Baza tiklandi: %s fayli orqali (%d foydalanuvchi, %d audio)",
        filename,
        stats["users"],
        stats["uploaded"],
    )
    await message.answer(
        restore_success_text(info, stats, safety.name),
        reply_markup=panel_kb(),
    )


@router.message(IsAdmin(), AdminBackup.waiting_db, IsNotCommand())
async def receive_backup_wrong_type(message: Message) -> None:
    await message.answer(
        "⚠️ Iltimos, zaxira bazani <b>hujjat</b> (<code>.db</code> fayl) sifatida "
        "yuboring.\n\n" + restore_prompt_text(await db.get_stats()),
        reply_markup=cancel_kb(),
    )
