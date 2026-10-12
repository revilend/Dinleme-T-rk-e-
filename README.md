# 🎧 Dinleme — Türkçe

**«Turk Tili A1 Fundamental»** (161 betlik darslik) kitobining QR-kodi orqali kirgan
o'quvchilarga barcha **34 ta dars**ning **Dinleme (eshitib tushunish)** audio fayllarini
yetkazib beruvchi Telegram bot — **ichida to'liq ishlaydigan admin panel bilan**.

- **Python** 3.11+ · **aiogram 3.x** · **aiosqlite** · to'liq asinxron (long-polling)
- **6 ta modul**, **34 ta dars** + 🎓 35-dars (imtihon) + 📖 Kitob haqida
- **👑 Admin panel Telegram ichida:** admin serverga kirmasdan istalgan darsga MP3 audio
  yuklaydi, yangilaydi, o'chiradi, statistikani ko'radi va hammaga xabar tarqatadi
- Audio **serverda saqlanmaydi**: Telegram qaytargan `file_id` SQLite bazaga yoziladi va
  o'quvchilarga bir zumda (Telegram keshidan) yuboriladi

---

## 1. O'rnatish

```bash
git clone <repo-url> && cd <repo>

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

## 2. Sozlash (`.env`)

```bash
cp .env.example .env
```

`.env` faylini to'ldiring:

```env
BOT_TOKEN=1234567890:AAE...sizning-tokeningiz     # @BotFather -> /newbot
ADMIN_IDS=123456789,987654321                     # adminlarning Telegram ID raqamlari
# DB_PATH=bot.db                                  # ixtiyoriy
```

- **ADMIN_IDS** — admin panelga ruxsat berilgan ID raqamlar (vergul bilan). O'z ID
  raqamingizni **@userinfobot** orqali bilib oling. Bir nechta admin qo'shish mumkin;
  ro'yxat bo'sh bo'lsa admin panel hech kimga ko'rinmaydi.

## 3. Ishga tushirish

```bash
python main.py
```

Konsolda quyidagilar chiqadi:

```
Baza tayyor: /loyiha/bot.db | foydalanuvchilar: 0 | audiolar: 0/34
Bot ishga tushdi: @sizning_botingiz | 34 dars, 6 modul | adminlar: 1 ta
```

To'xtatish: `Ctrl + C`. Birinchi ishga tushirishda `bot.db` fayli avtomatik yaratiladi.

---

## 4. O'quvchi uchun (user interface)

1. **`/start`** — foydalanuvchi bazaga saqlanadi, o'zbekcha salomlashuv va 6 ta modul
   tugmasi chiqadi (admin bo'lsa, qo'shimcha **👑 Admin Panel** tugmasi ham).
2. **Modul** tanlanadi → o'sha modulning darslari + `⬅️ Bosh menyu`.
3. **Dars** tanlanadi:
   - Bazada `file_id` bo'lsa → audio **darhol** yuboriladi, izohida dars nomi,
     3-sahifadagi 🎧 Dinleme topshirig'i va kitob orqasidagi **149–152-betlar** eslatmasi
     bo'ladi; audio ostida `⬅️ Ortga` va `🏠 Bosh menyu` turadi.
   - Audio hali yuklanmagan bo'lsa → **«⏳ Ushbu dars audiosi tez orada yuklanadi»** xabari
     (bot xatolik bermaydi).
4. **🎓 35-Dars: Bitiruv Imtihoni** — imtihonga tayyorlanish yo'riqnomasi.
5. **📖 Kitob haqida** — kitob tavsifi va audiodan foydalanish tartibi (`/help`, `/yordam`).

## 5. 👑 Admin panel

Adminlar `/admin` buyrug'i yoki menyudagi **👑 Admin Panel** tugmasi orqali kiradi:

| Bo'lim | Vazifasi |
|---|---|
| **🎵 Audio yuklash va yangilash** | 34 ta dars holati bilan ro'yxat: `1-Dars ✅`, `2-Dars ❌`, … Dars tanlanadi → bot FSM holatiga o'tadi: *«Iltimos, 7-dars uchun MP3 audio faylni yuboring (audio yoki fayl formatda)»* → admin MP3 ni tashlaydi → bot `file_id` ni bazaga saqlaydi va *«✅ 7-Dars audiosi muvaffaqiyatli saqlandi!»* deb javob beradi. Ayni darsga qayta yuklash = **yangilash**. |
| **🗑 Audioni o'chirish** | Faqat yuklangan darslar ko'rsatiladi; tanlansa yozuv bazadan o'chadi, o'quvchilarga yana «tez orada yuklanadi» chiqadi. |
| **📊 Statistika** | Jami foydalanuvchilar, bugun qo'shilganlar, yuklangan audiolar (`28/34`), qolganlar va to'liqlik foizi. |
| **📢 Xabar tarqatish** | FSM orqali matn/rasm/video/fayl/audio qabul qilinadi va **barcha** foydalanuvchilarga nusxalanadi. Natija: `✅ Muvaffaqiyatli: N`, `❌ Yetkazilmadi: M`. Flood limitiga qarshi pauza va `RetryAfter` ushlash mavjud. |
| **💾 Bazani yuklab olish (Backup)** | Joriy SQLite baza izchil nusxalanib (`VACUUM INTO` — WAL rejimida ham xavfsiz), Telegram'ga `.db` hujjat sifatida yuboriladi. Izohda sana/vaqt (GMT+5), foydalanuvchilar va yuklangan audiolar soni bo'ladi — faylni «Saqlangan xabarlar» ga saqlab qo'yish mumkin. |
| **🔄 Bazani qayta tiklash (Restore)** | FSM: ogohlantirish chiqadi → admin `.db` faylni yuboradi → bot faylni tekshiradi (`integrity_check` + kerakli jadvallar), bazani almashtiradi va qayta ochadi. Natija: `✅ Baza muvaffaqiyatli tiklandi!` va barcha foydalanuvchilar hamda 34 darsning audio `file_id` lari avvalgi holatiga qaytadi. Oldingi baza `bot.db.before-restore-<vaqt>` nomi bilan saqlanadi. |

Qo'shimcha:

- **Audio qanday saqlanadi:** Telegram `file_id` (matn) bazaga yoziladi — server diskida joy
  egallamaydi va yuborish juda tez.
- **Fayl yoki audio:** admin MP3 ni «Audio» sifatida yuborsa `file_id` to'g'ridan-to'g'ri
  saqlanadi; «Fayl (document)» sifatida yuborsa, bot uni bir marta qayta yuklab, haqiqiy
  *audio* `file_id` oladi (shunda keyinchalik yuborish ishonchli bo'ladi). Fayl cheklovi: 20 MB.
- **Backup/restore tafsilotlari:** backup `VACUUM INTO` bilan olinadi, shuning uchun WAL
  jurnalidagi yozuvlar ham nusxaga tushadi. Restore'da fayl avval tekshiriladi
  (`PRAGMA integrity_check` + `users`/`audios` jadvallari mavjudligi) — yaroqsiz fayl rad
  etiladi va joriy bazaga tegilmaydi. Tiklash jarayonida eski baza
  `bot.db.before-restore-<vaqt>` nomi bilan saqlanadi, yangi baza ochilmasa avtomatik qaytariladi.
- **Vaqt mintaqasi:** backup izohidagi sana/vaqt `TZ_OFFSET_HOURS` (standart `5` = GMT+5)
  bilan sozlanadi, masalan `.env` da `TZ_OFFSET_HOURS=3`.
- **Bekor qilish:** istalgan payt `/bekor`.
- **Xavfsizlik:** barcha admin handlerlari `ADMIN_IDS` filtri bilan himoyalangan; oddiy
  foydalanuvchi `/admin` yoki panel tugmasini bossa «❌ Bu bo'lim faqat adminlar uchun» oladi.

---

## 6. Modullar va darslar

| Modul | Nomi | Darslar |
|---|---|---|
| 1 | Tanishuv va Alifbo Asoslari | 1–9 |
| 2 | Makon, Shahar va Bor/Yo'q | 10–16 |
| 3 | Kundalik Hayot va Hozirgi Zamon | 17–22 |
| 4 | Oila, Egalik va Sifatlar | 23–26 |
| 5 | Xarid, Restoran va Kelishiklar | 27–30 |
| 6 | Sayohat va O'tgan Zamon | 31–34 |

## 7. Ma'lumotlar bazasi (SQLite)

```sql
users  (user_id PK, username, full_name, joined_date)
audios (lesson_id PK, file_id, caption, created_at)
```

Barcha so'rovlar `database.py` ichida (aiosqlite). `audios.lesson_id` — 1..34;
bir dars uchun yozuv `UPSERT` bilan yangilanadi (takrorlanmaydi).

## 8. Loyiha tuzilishi

```
.
├── main.py             # Botni ishga tushirish: routerlar, DB init, polling
├── database.py         # aiosqlite: users/audios jadvallari, CRUD, statistika
├── handlers_user.py    # O'quvchilar: /start, modul/dars menyusi, audio yetkazish
├── handlers_admin.py   # Admin panel: audio FSM, o'chirish, statistika, broadcast
├── lessons.py          # 6 modul / 34 dars ma'lumoti, matnlar, klaviaturalar
├── config.py           # .env sozlamalari (BOT_TOKEN, ADMIN_IDS, DB_PATH)
├── ui.py               # Umumiy UI yordamchilari (xabar yangilash/tahrirlash)
├── requirements.txt    # aiogram, aiosqlite, python-dotenv
├── .env.example        # Sozlamalar namunasi
├── render.yaml         # Render Blueprint (background worker + doimiy disk)
├── .python-version     # Hosting uchun Python versiyasi (3.12)
└── bot.db              # SQLite baza (ishga tushganda yaratiladi, gitga tushmaydi)
```

## 9. Sozlash bo'yicha maslahatlar

- **Darsning aniq beti.** Izohdagi bet raqami standart `3`. Kitobdagi haqiqiy betlarni
  bilganingizda `lessons.py` dagi `LESSON_PAGES` lug'atini to'ldiring: `LESSON_PAGES = {12: 45}`.
- **Zaxira nusxa.** Eng qulay usul — bot ichidagi **💾 Bazani yuklab olish (Backup)**: fayl
  Telegram'ga keladi va «Saqlangan xabarlar»da turadi. Serverdan ham olish mumkin:
  `cp bot.db bot.db.bak` (WAL rejimida xavfsiz nusxa kerak bo'lsa `sqlite3 bot.db "VACUUM INTO 'zaxira.db'"`).
- **Doimiy ishlash.** Serverda `systemd`, Docker yoki `screen`/`tmux` orqali uzluksiz ishga
  tushirish tavsiya etiladi (`Ctrl + C` botsiz qolmasin). Bulutda — quyidagi
  [Render bo'limi](#11-renderga-deploy-github-orqali).
- **Bot username.** Kitobdagi QR-kodni `https://t.me/<bot_username>` manziliga yo'naltiring.
- **Ko'p admin.** `ADMIN_IDS=111,222,333` — hammasi bir xil imkoniyatlarga ega.

## 10. Muammolar (Troubleshooting)

| Muammo | Sabab / yechim |
|---|---|
| `❌ BOT_TOKEN topilmadi` | `.env` yo'q yoki `BOT_TOKEN` bo'sh — `.env.example` dan nusxa oling |
| Admin panel ko'rinmaydi | `ADMIN_IDS` bo'sh yoki ID noto'g'ri — @userinfobot'dan ID ni olib, `.env` ga yozing va botni qayta ishga tushiring |
| `Unauthorized` | Token noto'g'ri/bekor qilingan — @BotFather'dan yangisini oling |
| «⏳ Ushbu dars audiosi tez orada yuklanadi» | O'sha darsga audio hali yuklanmagan — admin paneldan yuklang |
| Audio yuborilmaydi / `wrong file identifier` | Eski `file_id` yaroqsiz bo'lib qolgan — bot yozuvni avtomatik tozalaydi, admin qayta yuklashi kerak |
| Hujjat (fayl) yuklanmayapti | Fayl 20 MB dan katta yoki MP3/M4A/OGG/WAV emas — siqib qayta yuboring |
| Broadcast yetib bormayapti | Foydalanuvchi botni bloklagan (`❌` hisobida ko'rinadi) |
| Logda `⚠️ ... ochilmadi ... Zaxira bazaga o'tildi` | Render'da doimiy disk ulanmagan — `bot-data` diskini `/var/data` ga ulang, aks holda userlar va `file_id` lar har deplo'yda yo'qoladi |

---

## 11. Render'ga deploy (GitHub orqali)

Repo ichida tayyor `render.yaml` (Blueprint) va `.python-version` bor, shuning uchun deploy
bir necha bosqichda bo'ladi:

1. Kodni GitHub'ga push qiling.
2. [Render Dashboard](https://dashboard.render.com) → **New +** → **Blueprint** → reponi tanlang → **Apply**.
3. Render **BOT_TOKEN** va **ADMIN_IDS** qiymatlarini so'raydi (ular `render.yaml` da
   `sync: false` bilan belgilangan — gitga tushmaydi). Kiriting.
4. Loglarda `Bot ishga tushdi: @... | 34 dars, 6 modul | adminlar: 1 ta` chiqsa — tayyor.
5. Telegram'da botga `/admin` yuborib, audiolarni yuklashni boshlang.

| Sozlama | Qiymat |
|---|---|
| Service type | **Background Worker** — bot long-polling bilan ishlaydi, port tinglamaydi |
| Build command | `pip install -r requirements.txt` |
| Start command | `python main.py` |
| Persistent disk | `bot-data` → `/var/data` (1 GB) |
| Environment | `DB_PATH=/var/data/bot.db`, `BOT_TOKEN`, `ADMIN_IDS` |

### ⚠️ Baza, disk va tarif haqida

- SQLite baza `DB_PATH=/var/data/bot.db` — **doimiy diskda**, shuning uchun redeploy va
  restartlarda foydalanuvchilar hamda yuklangan `file_id` lar saqlanib qoladi.
- **Doimiy disk faqat pullik compute planda ishlaydi.** Disksiz (bepul) web service'da har
  deplo'yda baza o'chadi: userlar yo'qoladi va admin 34 audioni qaytadan yuklashi kerak bo'ladi.
- Render'da **Background Worker bepul tarifda yo'q** (eng arzon plan ~$7/oy, 0.5 CPU / 512 MB).
  Bepul **Web Service** esa bot uchun yaroqsiz: 15 daqiqa trafik bo'lmasa uxlab qoladi,
  port talab qiladi va disk ulab bo'lmaydi.
- Bepul variant kerak bo'lsa: kichik VPS (Hetzner, Oracle free tier), Railway, Fly.io yoki uy
  serveri — hammasida `python main.py` ni `systemd`/Docker bilan uzluksiz ishga tushiring.
- Boshqa region kerak bo'lsa `render.yaml` dagi `region` (hozir `frankfurt`) qiymatini o'zgartiring.
- **Baza ochilmasa bot yiqilmaydi:** agar `DB_PATH` papkasi yaratilmasa (masalan disk ulanmagan),
  bot ogohlantirish yozib lokal `bot.db` ga o'tadi va ishlashda davom etadi — bunda baza saqlanmaydi,
  shuning uchun logdagi ogohlantirishni ko'rsangiz diskni ulang.

### Yangilash

`main` branch'ga push qilinsa Render avtomatik qayta deploy qiladi (`autoDeploy: true`).
Baza `/var/data` da, audio fayllar esa Telegram serverida — hech biri yo'qolmaydi.

---

© Darslik mualliflari uchun tayyorlangan o'quv yordamchi bot.
