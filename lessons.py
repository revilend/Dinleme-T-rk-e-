"""Darslik tuzilishi (6 modul / 34 dars), matnlar va Inline klaviaturalar.

Bu modul `handlers_user.py` va `handlers_admin.py` tomonidan birgalikda
ishlatiladi, shuning uchun handlerlarni import qilmaydi (aylanma import yo'q).
"""

from __future__ import annotations

from dataclasses import dataclass

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

BOOK_TITLE = "Turk Tili A1 Fundamental"
AUDIO_PERFORMER = f"{BOOK_TITLE} — Dinleme"
BOOK_PAGES = "161 bet"

# Dinleme topshirig'i joylashgan bet (har bir dars uchun standart qiymat)
BOOK_PAGE_DEFAULT = 3
# Kitob orqasidagi Dinleme matnlari joylashgan betlar
TEXT_PAGES = "149–152"
# Dars bo'yicha aniq bet ma'lum bo'lsa, shu yerga qo'shing: masalan {12: 45}
LESSON_PAGES: dict[int, int] = {}


# ---------------------------------------------------------------------------
# Ma'lumot modeli
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Lesson:
    no: int
    title: str
    module_no: int

    @property
    def label(self) -> str:
        """Masalan: 7-Dars: Sonlar va hisoblash (0-100)"""
        return f"{self.no}-Dars: {self.title}"

    @property
    def audio_name(self) -> str:
        """Masalan: 7_dars.mp3 (admin panelida ko'rsatiladi)"""
        return f"{self.no}_dars.mp3"


@dataclass(frozen=True, slots=True)
class Module:
    no: int
    title: str
    lessons: tuple[Lesson, ...]

    @property
    def range_label(self) -> str:
        return f"{self.lessons[0].no}–{self.lessons[-1].no}"


_RAW_MODULES: tuple[tuple[int, str, tuple[tuple[int, str], ...]], ...] = (
    (
        1,
        "Tanishuv va Alifbo Asoslari",
        (
            (1, "Salomlashuv va tanishuv"),
            (2, "29 harfli turk alifbosi"),
            (3, "Katta unlilar uyg'unligi"),
            (4, "Ko'plik qo'shimchasi (-lar / -ler)"),
            (5, "Ko'rsatish olmoshlari (Bu, Şu, O)"),
            (6, "So'roq shakllari (Bu ne? Bu kim?)"),
            (7, "Sonlar va hisoblash (0-100)"),
            (8, "Sinf xonasi va anjomlar"),
            (9, "Mamlakatlar, millatlar va tillar"),
        ),
    ),
    (
        2,
        "Makon, Shahar va Bor/Yo'q",
        (
            (10, "Shahar joylari va binolar"),
            (11, "O'rin-payt kelishigi (-da / -ta)"),
            (12, "Borlik va yo'qlik (Var / Yok)"),
            (13, "Umumiy so'roq yuklamasi (-mı / -mi)"),
            (14, "Uy, xonalar va mebellar"),
            (15, "Yo'nalish va manzil so'rash"),
            (16, "Tartib sonlar (-ıncı / -inci)"),
        ),
    ),
    (
        3,
        "Kundalik Hayot va Hozirgi Zamon",
        (
            (17, "Soatlar va vaqt tizimi"),
            (18, "Kun tartibi va 20 ta asosiy fe'l"),
            (19, "Hozirgi davomli zamon (-yor)"),
            (20, "Unlilar torayishi (başlıyor)"),
            (21, "Hozirgi zamon inkor va so'roq"),
            (22, "Hafta kunlari, oylar, fasllar"),
        ),
    ),
    (
        4,
        "Oila, Egalik va Sifatlar",
        (
            (23, "Oila a'zolari va qarindoshlik"),
            (24, "Egalik qo'shimchalari (-im / -in / -i)"),
            (25, "Qaratqich kelishigi (Ali'nin evi)"),
            (26, "Tashqi qiyofa va sifatlar"),
        ),
    ),
    (
        5,
        "Xarid, Restoran va Kelishiklar",
        (
            (27, "Bozorda savdolashish va mevalar"),
            (28, "Restoran va taom buyurtma qilish"),
            (29, "Yo'nalish (-e) va Chiqish (-den)"),
            (30, "Istak mayli (Hadi gidelim!)"),
        ),
    ),
    (
        6,
        "Sayohat va O'tgan Zamon",
        (
            (31, "Sayohat va aeroportda muloqot"),
            (32, "Aniq o'tgan zamon (-dı / -ti)"),
            (33, "O'tgan zamon inkor va so'roq"),
            (34, "Mehmonxonada xona band qilish"),
        ),
    ),
)

MODULES: tuple[Module, ...] = tuple(
    Module(
        no=module_no,
        title=module_title,
        lessons=tuple(
            Lesson(no=lesson_no, title=lesson_title, module_no=module_no)
            for lesson_no, lesson_title in lessons
        ),
    )
    for module_no, module_title, lessons in _RAW_MODULES
)

MODULE_BY_NO: dict[int, Module] = {module.no: module for module in MODULES}
LESSON_BY_NO: dict[int, Lesson] = {
    lesson.no: lesson for module in MODULES for lesson in module.lessons
}
TOTAL_LESSONS = len(LESSON_BY_NO)  # 34
# 1-darsdan 34-darsgacha tartiblangan ro'yxat (admin paneli uchun)
LESSONS_SORTED: tuple[Lesson, ...] = tuple(LESSON_BY_NO[no] for no in sorted(LESSON_BY_NO))

EXAM_TEXT = (
    "🎓 <b>35-Dars: Bitiruv Imtihoni</b>\n\n"
    "Bu darsda yangi audio yo'q — maqsad 1–34-darslarda o'rgangan "
    "bilimlaringizni sinab ko'rish.\n\n"
    "<b>Tayyorlanish tartibi:</b>\n"
    "1️⃣ Har bir modulni takrorlang va audiolarni yana bir bor eshiting.\n"
    f"2️⃣ Dinleme matnlarini kitob orqasidagi {TEXT_PAGES}-betlar bilan solishtiring.\n"
    "3️⃣ Mashqlarni yozma bajaring, so'ng audioni qayta eshitib tekshiring.\n"
    "4️⃣ Imtihon bo'yicha aniq ko'rsatmalar darslikning oxirgi bo'limida "
    "keltirilgan.\n\n"
    "Omad tilaymiz! 💪"
)

ABOUT_TEXT = (
    f"📖 <b>Kitob haqida</b>\n"
    f"«{BOOK_TITLE}» — {BOOK_PAGES}lik o'quv qo'llanma. U 6 ta modul va "
    f"{TOTAL_LESSONS} ta darsdan iborat. Har bir darsda 🎧 Dinleme "
    "topshirig'i va mashqlar mavjud.\n\n"
    "🎧 <b>Audiodan qanday foydalanish kerak</b>\n"
    "1️⃣ Menyudan darsni tanlang — bot MP3 audioni yuboradi.\n"
    "2️⃣ Kitobingizdagi 🎧 Dinleme topshirig'ini bajaring.\n"
    f"3️⃣ Matnni tekshirish uchun kitob orqasidagi {TEXT_PAGES}-betlarga qarang.\n"
    "4️⃣ Mashqlarni yozma bajargach, audioni yana bir bor eshiting.\n\n"
    "🆘 <b>Yordam</b>\n"
    "• Audio yuborilmasa, «⏳ Ushbu dars audiosi tez orada yuklanadi» degan "
    "xabar chiqadi — birozdan so'ng qayta urinib ko'ring.\n"
    "• Menyu yo'qolib qolsa, /start buyrug'ini yuboring.\n"
    "• Boshqa savollar bo'lsa, o'qituvchingizga murojaat qiling."
)


def start_text(full_name: str | None = None) -> str:
    hello = f"Assalomu alaykum, {full_name}! 👋" if full_name else "Assalomu alaykum, hurmatli o'quvchi! 👋"
    return (
        f"🎧 <b>{BOOK_TITLE} — Dinleme audiolari</b>\n\n"
        f"{hello}\n"
        "Darslikdagi QR-kodni skaner qildingiz — demak to'g'ri joydasiz.\n\n"
        f"Bu botda kitobning barcha <b>{TOTAL_LESSONS} ta darsi</b> uchun "
        "«Dinleme» (eshitib tushunish) audiolari <b>6 ta modul</b> bo'yicha "
        "tartiblangan.\n\n"
        "👇 Kerakli modulni tanlang:"
    )


def module_text(module: Module) -> str:
    return (
        f"📚 <b>{module.no}-Modul: {module.title}</b>\n"
        f"🗂 Darslar: {module.range_label}\n"
        f"📖 Darslik: «{BOOK_TITLE}» ({BOOK_PAGES})\n\n"
        "Kerakli darsni tanlang — bot audioni darhol yuboradi 👇"
    )


def dinleme_izoh(lesson_no: int) -> str:
    page = LESSON_PAGES.get(lesson_no, BOOK_PAGE_DEFAULT)
    return (
        f"📌 Kitobingizning {page}-sahifasidagi 🎧 Dinleme topshirig'ini "
        "bajaring. Matnni tekshirish uchun kitob orqasidagi "
        f"{TEXT_PAGES}-betlarga qarang."
    )


def lesson_caption(lesson: Lesson) -> str:
    """Audio yuborilganda ishlatiladigan izoh (caption)."""
    module = MODULE_BY_NO[lesson.module_no]
    return (
        f"🎧 <b>{lesson.no}-Dars: {lesson.title}</b>\n"
        f"📚 {module.no}-Modul: {module.title}\n\n"
        f"{dinleme_izoh(lesson.no)}"
    )


def missing_audio_text(lesson: Lesson) -> str:
    return (
        "⏳ <b>Ushbu dars audiosi tez orada yuklanadi</b>\n\n"
        f"<b>{lesson.no}-Dars: {lesson.title}</b>\n"
        "Hurmatli o'quvchi, bu darsning audiosi hali joylanmagan. Iltimos, "
        "birozdan so'ng qayta urinib ko'ring. 🙏\n\n"
        "Bu vaqtda boshqa darslarni bemalol tinglashingiz mumkin."
    )


# ---------------------------------------------------------------------------
# Klaviaturalar
# ---------------------------------------------------------------------------
def main_menu_kb(show_admin: bool = False) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for module in MODULES:
        kb.button(
            text=f"{module.no}-Modul · {module.title} ({module.range_label})",
            callback_data=f"m:{module.no}",
        )
    kb.button(text="🎓 35-Dars: Bitiruv Imtihoni", callback_data="x:exam")
    kb.button(text="📖 Kitob haqida", callback_data="x:about")
    if show_admin:
        kb.button(text="👑 Admin Panel", callback_data="a:panel")
    kb.adjust(1)
    return kb.as_markup()


def module_kb(module: Module) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for lesson in module.lessons:
        kb.button(text=lesson.label, callback_data=f"l:{lesson.no}")
    kb.button(text="⬅️ Bosh menyu", callback_data="home")
    kb.adjust(1)
    return kb.as_markup()


def lesson_kb(lesson: Lesson) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Ortga", callback_data=f"m:{lesson.module_no}")
    kb.button(text="🏠 Bosh menyu", callback_data="home")
    kb.adjust(2)
    return kb.as_markup()
