import os
import sqlite3
import asyncio
import logging
import aiohttp

from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


# =========================================================
# CONFIG
# =========================================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SMM_API_URL = os.getenv(
    "SMM_API_URL",
    "https://seensms.uz/api/v1"
)
SMM_API_KEY = os.getenv("SMM_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

BOT_NAME = "Best1SMM"
DB_NAME = "best1smm.db"


if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi!")

if not SMM_API_KEY:
    raise RuntimeError("SMM_API_KEY topilmadi!")


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(BOT_NAME)


# =========================================================
# BOT
# =========================================================

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    )
)

dp = Dispatcher()


# =========================================================
# DATABASE
# =========================================================

def get_db():
    return sqlite3.connect(DB_NAME)


def init_db():

    con = get_db()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            api_order TEXT,
            service_id TEXT,
            service_name TEXT,
            category TEXT,
            link TEXT,
            quantity INTEGER,
            charge REAL,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    con.commit()
    con.close()


def register_user(user):

    con = get_db()
    cur = con.cursor()

    cur.execute("""
        INSERT OR IGNORE INTO users
        (user_id, username, first_name)
        VALUES (?, ?, ?)
    """, (
        user.id,
        user.username or "",
        user.first_name or ""
    ))

    cur.execute("""
        UPDATE users
        SET username = ?, first_name = ?
        WHERE user_id = ?
    """, (
        user.username or "",
        user.first_name or "",
        user.id
    ))

    con.commit()
    con.close()


def get_balance(user_id):

    con = get_db()
    cur = con.cursor()

    cur.execute(
        "SELECT balance FROM users WHERE user_id = ?",
        (user_id,)
    )

    row = cur.fetchone()

    con.close()

    if row:
        return float(row[0])

    return 0.0


def change_balance(user_id, amount):

    con = get_db()
    cur = con.cursor()

    cur.execute("""
        UPDATE users
        SET balance = balance + ?
        WHERE user_id = ?
    """, (
        amount,
        user_id
    ))

    con.commit()
    con.close()


# =========================================================
# STATES
# =========================================================

class OrderState(StatesGroup):
    waiting_link = State()
    waiting_quantity = State()


class SearchState(StatesGroup):
    waiting_query = State()


class AdminState(StatesGroup):
    waiting_user_id = State()
    waiting_amount = State()


# =========================================================
# FORMAT
# =========================================================

def money(value):

    try:
        return f"{float(value):,.2f}".replace(",", " ")
    except:
        return "0.00"


def cut(text, length=45):

    text = str(text)

    if len(text) > length:
        return text[:length - 3] + "..."

    return text


# =========================================================
# PERMANENT BOTTOM KEYBOARD
# =========================================================

def main_keyboard():

    keyboard = [
        [
            KeyboardButton(text="🛒 Buyurtma berish"),
            KeyboardButton(text="📦 Buyurtmalarim"),
        ],
        [
            KeyboardButton(text="💰 Balansim"),
            KeyboardButton(text="➕ Balans to‘ldirish"),
        ],
        [
            KeyboardButton(text="🔎 Xizmat qidirish"),
            KeyboardButton(text="ℹ️ Yordam"),
        ],
    ]

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Bo‘limni tanlang..."
    )


# =========================================================
# API
# =========================================================

async def api_request(action, **kwargs):

    payload = {
        "key": SMM_API_KEY,
        "action": action
    }

    payload.update(kwargs)

    try:

        timeout = aiohttp.ClientTimeout(total=40)

        async with aiohttp.ClientSession(
            timeout=timeout
        ) as session:

            async with session.post(
                SMM_API_URL,
                data=payload
            ) as response:

                text = await response.text()

                try:
                    import json
                    return json.loads(text)

                except Exception:

                    return {
                        "error": text
                    }

    except asyncio.TimeoutError:

        return {
            "error": "API javob berish vaqti tugadi."
        }

    except Exception as e:

        logger.error(
            f"API ERROR: {e}"
        )

        return {
            "error": "API bilan aloqa qilib bo‘lmadi."
        }


async def get_services():

    return await api_request(
        "services"
    )


async def add_order(
    service,
    link,
    quantity
):

    return await api_request(
        "add",
        service=service,
        link=link,
        quantity=quantity
    )


async def order_status(order_id):

    return await api_request(
        "status",
        order=order_id
    )


async def refill_order(order_id):

    return await api_request(
        "refill",
        order=order_id
    )


async def cancel_order(order_id):

    return await api_request(
        "cancel",
        order=order_id
    )


async def panel_balance():

    return await api_request(
        "balance"
    )


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):

    await state.clear()

    register_user(
        message.from_user
    )

    balance = get_balance(
        message.from_user.id
    )

    name = message.from_user.first_name or "Do‘st"

    await message.answer(
        f"""
✨ <b>BEST1SMM</b> ga xush kelibsiz! ✨

Assalomu alaykum, <b>{name}</b>! 👋

🚀 SMM xizmatlarini tez va qulay
buyurtma qilish uchun botimizdan
foydalanishingiz mumkin.

📸 Instagram
📱 Telegram
🎵 TikTok
▶️ YouTube

━━━━━━━━━━━━━━━━━━

💰 Balansingiz:
<b>{money(balance)} so‘m</b>

━━━━━━━━━━━━━━━━━━

👇 Pastdagi menyudan kerakli
bo‘limni tanlang.
""",
        reply_markup=main_keyboard()
    )


# =========================================================
# BUY ORDER MENU
# =========================================================

@dp.message(F.text == "🛒 Buyurtma berish")
async def buy_menu(message: Message):

    await message.answer(
        "⏳ <b>Xizmatlar yuklanmoqda...</b>"
    )

    services = await get_services()

    if not isinstance(services, list):

        await message.answer(
            f"""
❌ <b>Xizmatlarni olishda xatolik!</b>

Sabab:
{services.get("error", "Noma’lum xatolik")}
""",
            reply_markup=main_keyboard()
        )

        return

    if not services:

        await message.answer(
            "❌ Hozircha xizmatlar mavjud emas.",
            reply_markup=main_keyboard()
        )

        return

    categories = []

    for service in services:

        category = str(
            service.get(
                "category",
                "Boshqa"
            )
        )

        if category not in categories:
            categories.append(category)

    kb = InlineKeyboardBuilder()

    for index, category in enumerate(
        categories[:50]
    ):

        kb.button(
            text=f"📂 {cut(category, 40)}",
            callback_data=f"category:{index}"
        )

    kb.adjust(1)

    await message.answer(
        f"""
🛒 <b>YANGI BUYURTMA</b>

📦 Xizmatlar soni:
<b>{len(services)}</b>

📂 Kategoriyalar:
<b>{len(categories)}</b>

👇 Kategoriyani tanlang:
""",
        reply_markup=kb.as_markup()
    )


# =========================================================
# CATEGORY
# =========================================================

@dp.callback_query(
    F.data.startswith("category:")
)
async def category_menu(
    call: CallbackQuery
):

    index = int(
        call.data.split(":")[1]
    )

    services = await get_services()

    if not isinstance(services, list):

        await call.answer(
            "API xatosi!",
            show_alert=True
        )

        return

    categories = []

    for service in services:

        category = str(
            service.get(
                "category",
                "Boshqa"
            )
        )

        if category not in categories:
            categories.append(category)

    if index >= len(categories):

        await call.answer(
            "Kategoriya topilmadi!",
            show_alert=True
        )

        return

    category = categories[index]

    filtered = [
        service
        for service in services
        if str(
            service.get(
                "category",
                "Boshqa"
            )
        ) == category
    ]

    kb = InlineKeyboardBuilder()

    for service in filtered[:50]:

        service_id = str(
            service.get(
                "service",
                ""
            )
        )

        name = cut(
            service.get(
                "name",
                "Xizmat"
            ),
            45
        )

        kb.button(
            text=f"🛒 {service_id} | {name}",
            callback_data=f"service:{service_id}"
        )

    kb.button(
        text="⬅️ Kategoriyalar",
        callback_data="categories"
    )

    kb.adjust(1)

    await call.message.edit_text(
        f"""
📂 <b>{category}</b>

📦 Xizmatlar:
<b>{len(filtered)}</b>

👇 Xizmatni tanlang:
""",
        reply_markup=kb.as_markup()
    )

    await call.answer()


@dp.callback_query(F.data == "categories")
async def categories_back(
    call: CallbackQuery
):

    services = await get_services()

    if not isinstance(services, list):

        await call.answer(
            "API xatosi!",
            show_alert=True
        )

        return

    categories = []

    for service in services:

        category = str(
            service.get(
                "category",
                "Boshqa"
            )
        )

        if category not in categories:
            categories.append(category)

    kb = InlineKeyboardBuilder()

    for index, category in enumerate(
        categories[:50]
    ):

        kb.button(
            text=f"📂 {cut(category, 40)}",
            callback_data=f"category:{index}"
        )

    kb.adjust(1)

    await call.message.edit_text(
        "📂 <b>KATEGORIYALAR</b>\n\n"
        "Kerakli kategoriyani tanlang:",
        reply_markup=kb.as_markup()
    )

    await call.answer()


# =========================================================
# SERVICE INFO
# =========================================================

@dp.callback_query(
    F.data.startswith("service:")
)
async def service_info(
    call: CallbackQuery
):

    service_id = call.data.split(
        ":",
        1
    )[1]

    services = await get_services()

    if not isinstance(services, list):

        await call.answer(
            "API xatosi!",
            show_alert=True
        )

        return

    service = None

    for item in services:

        if str(
            item.get("service")
        ) == service_id:

            service = item
            break

    if not service:

        await call.answer(
            "Xizmat topilmadi!",
            show_alert=True
        )

        return

    name = service.get(
        "name",
        "Xizmat"
    )

    category = service.get(
        "category",
        "Boshqa"
    )

    rate = service.get(
        "rate",
        "0"
    )

    minimum = service.get(
        "min",
        "0"
    )

    maximum = service.get(
        "max",
        "0"
    )

    refill = service.get(
        "refill",
        False
    )

    cancel = service.get(
        "cancel",
        False
    )

    refill_text = (
        "✅ Bor"
        if refill
        else "❌ Yo‘q"
    )

    cancel_text = (
        "✅ Bor"
        if cancel
        else "❌ Yo‘q"
    )

    kb = InlineKeyboardBuilder()

    kb.button(
        text="🛒 BUYURTMA BERISH",
        callback_data=f"buy:{service_id}"
    )

    kb.button(
        text="⬅️ Orqaga",
        callback_data="categories"
    )

    kb.adjust(1)

    await call.message.edit_text(
        f"""
📋 <b>XIZMAT MA’LUMOTI</b>

━━━━━━━━━━━━━━━━━━

🆔 ID:
<code>{service_id}</code>

📌 Nomi:
<b>{name}</b>

📂 Kategoriya:
{category}

💵 Narx:
<b>{rate}</b> so‘m / 1000

🔽 Minimum:
<b>{minimum}</b>

🔼 Maximum:
<b>{maximum}</b>

♻️ Refill:
{refill_text}

❌ Cancel:
{cancel_text}

━━━━━━━━━━━━━━━━━━

👇 Buyurtma berish uchun tugmani bosing.
""",
        reply_markup=kb.as_markup()
    )

    await call.answer()


# =========================================================
# BUY
# =========================================================

@dp.callback_query(
    F.data.startswith("buy:")
)
async def start_order(
    call: CallbackQuery,
    state: FSMContext
):

    service_id = call.data.split(
        ":",
        1
    )[1]

    services = await get_services()

    service = next(
        (
            x for x in services
            if str(
                x.get("service")
            ) == service_id
        ),
        None
    )

    if not service:

        await call.answer(
            "Xizmat topilmadi!",
            show_alert=True
        )

        return

    await state.update_data(

        service_id=service_id,

        service_name=service.get(
            "name",
            "Xizmat"
        ),

        category=service.get(
            "category",
            "Boshqa"
        ),

        rate=float(
            service.get(
                "rate",
                0
            )
        ),

        minimum=int(
            service.get(
                "min",
                0
            )
        ),

        maximum=int(
            service.get(
                "max",
                0
            )
        )
    )

    await call.message.answer(
        f"""
🔗 <b>LINKNI YUBORING</b>

📌 Xizmat:
<b>{service.get("name", "Xizmat")}</b>

🆔 ID:
<code>{service_id}</code>

👇 Kerakli post/profil/kanal
havolasini yuboring.

Masalan:
<code>https://instagram.com/...</code>
"""
    )

    await state.set_state(
        OrderState.waiting_link
    )

    await call.answer()


# =========================================================
# LINK
# =========================================================

@dp.message(
    OrderState.waiting_link
)
async def get_link(
    message: Message,
    state: FSMContext
):

    link = (
        message.text or ""
    ).strip()

    if not link.startswith(
        ("http://", "https://")
    ):

        await message.answer(
            "❌ Iltimos, to‘g‘ri URL yuboring."
        )

        return

    await state.update_data(
        link=link
    )

    data = await state.get_data()

    await message.answer(
        f"""
🔢 <b>MIQDORNI YUBORING</b>

📉 Minimum:
<b>{data["minimum"]}</b>

📈 Maximum:
<b>{data["maximum"]}</b>

Masalan:
<code>1000</code>
"""
    )

    await state.set_state(
        OrderState.waiting_quantity
    )


# =========================================================
# QUANTITY
# =========================================================

@dp.message(
    OrderState.waiting_quantity
)
async def get_quantity(
    message: Message,
    state: FSMContext
):

    try:

        quantity = int(
            (message.text or "").strip()
        )

    except:

        await message.answer(
            "❌ Miqdorni faqat raqamda yuboring."
        )

        return

    data = await state.get_data()

    if quantity < data["minimum"]:

        await message.answer(
            f"❌ Minimal miqdor: "
            f"<b>{data['minimum']}</b>"
        )

        return

    if quantity > data["maximum"]:

        await message.answer(
            f"❌ Maksimal miqdor: "
            f"<b>{data['maximum']}</b>"
        )

        return

    price = (
        data["rate"] * quantity
    ) / 1000

    balance = get_balance(
        message.from_user.id
    )

    if balance < price:

        await message.answer(
            f"""
❌ <b>BALANS YETARLI EMAS</b>

💵 Buyurtma narxi:
<b>{money(price)} so‘m</b>

💰 Sizning balansingiz:
<b>{money(balance)} so‘m</b>

📉 Yetishmayapti:
<b>{money(price - balance)} so‘m</b>

👇 Pastdagi menyudan balansni to‘ldiring.
""",
            reply_markup=main_keyboard()
        )

        await state.clear()

        return

    await message.answer(
        "⏳ <b>Buyurtma yuborilmoqda...</b>"
    )

    result = await add_order(
        service=data["service_id"],
        link=data["link"],
        quantity=quantity
    )

    if not isinstance(result, dict):

        await message.answer(
            "❌ API noto‘g‘ri javob qaytardi."
        )

        await state.clear()

        return

    if "error" in result:

        await message.answer(
            f"""
❌ <b>BUYURTMA BERILMADI</b>

Sabab:
{result["error"]}
"""
        )

        await state.clear()

        return

    api_order = result.get(
        "order"
    )

    if not api_order:

        await message.answer(
            "❌ API order ID qaytarmadi."
        )

        await state.clear()

        return

    # Balansdan yechish
    change_balance(
        message.from_user.id,
        -price
    )

    # Buyurtmani saqlash
    con = get_db()
    cur = con.cursor()

    cur.execute("""
        INSERT INTO orders
        (
            user_id,
            api_order,
            service_id,
            service_name,
            category,
            link,
            quantity,
            charge,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        message.from_user.id,
        str(api_order),
        data["service_id"],
        data["service_name"],
        data["category"],
        data["link"],
        quantity,
        price,
        "Pending"
    ))

    con.commit()
    con.close()

    await message.answer(
        f"""
🎉 <b>BUYURTMA QABUL QILINDI!</b>

━━━━━━━━━━━━━━━━━━

🆔 Buyurtma:
<code>#{api_order}</code>

📦 Xizmat:
<b>{data["service_name"]}</b>

🔢 Miqdor:
<b>{quantity}</b>

💵 Narx:
<b>{money(price)} so‘m</b>

📊 Holat:
<b>Pending</b>

━━━━━━━━━━━━━━━━━━

💰 Qolgan balans:
<b>{money(get_balance(message.from_user.id))} so‘m</b>

Buyurtmangiz panel tomonidan
qayta ishlanadi. 🚀
""",
        reply_markup=main_keyboard()
    )

    await state.clear()


# =========================================================
# BALANCE
# =========================================================

@dp.message(F.text == "💰 Balansim")
async def balance_page(message: Message):

    balance = get_balance(
        message.from_user.id
    )

    await message.answer(
        f"""
💰 <b>MENING BALANSIM</b>

━━━━━━━━━━━━━━━━━━

💵 Balans:
<b>{money(balance)} so‘m</b>

━━━━━━━━━━━━━━━━━━

➕ Balansni to‘ldirish uchun
pastdagi tugmani bosing.
""",
        reply_markup=main_keyboard()
    )


# =========================================================
# DEPOSIT
# =========================================================

@dp.message(F.text == "➕ Balans to‘ldirish")
async def deposit_page(message: Message):

    await message.answer(
        """
➕ <b>BALANS TO‘LDIRISH</b>

Balans to‘ldirish uchun
administrator bilan bog‘laning.

👨‍💼 Admin:
@YOUR_ADMIN_USERNAME

━━━━━━━━━━━━━━━━━━

💳 To‘lov summasini admin bilan
kelishib oling.

⚠️ To‘lovni faqat rasmiy
administrator orqali amalga oshiring.
""",
        reply_markup=main_keyboard()
    )


# =========================================================
# MY ORDERS
# =========================================================

@dp.message(F.text == "📦 Buyurtmalarim")
async def my_orders(message: Message):

    con = get_db()
    cur = con.cursor()

    cur.execute("""
        SELECT
            api_order,
            service_name,
            quantity,
            charge,
            status
        FROM orders
        WHERE user_id=?
        ORDER BY id DESC
        LIMIT 10
    """, (
        message.from_user.id,
    ))

    rows = cur.fetchall()

    con.close()

    if not rows:

        await message.answer(
            "📦 <b>BUYURTMALARIM</b>\n\n"
            "Hali buyurtmalaringiz yo‘q.",
            reply_markup=main_keyboard()
        )

        return

    text = "📦 <b>BUYURTMALARIM</b>\n\n"

    for row in rows:

        text += (
            f"🆔 <code>#{row[0]}</code>\n"
            f"📌 {cut(row[1], 40)}\n"
            f"🔢 {row[2]}\n"
            f"💵 {money(row[3])} so‘m\n"
            f"📊 {row[4]}\n"
            f"━━━━━━━━━━━━\n"
        )

    await message.answer(
        text,
        reply_markup=main_keyboard()
    )


# =========================================================
# SEARCH
# =========================================================

@dp.message(F.text == "🔎 Xizmat qidirish")
async def search_start(
    message: Message,
    state: FSMContext
):

    await message.answer(
        """
🔎 <b>XIZMAT QIDIRISH</b>

Xizmat nomi, platforma yoki
Service ID yuboring.

Masalan:

<code>Instagram</code>

<code>Telegram</code>

<code>TikTok</code>

<code>123</code>
"""
    )

    await state.set_state(
        SearchState.waiting_query
    )


@dp.message(
    SearchState.waiting_query
)
async def search_service(
    message: Message,
    state: FSMContext
):

    query = (
        message.text or ""
    ).lower().strip()

    services = await get_services()

    if not isinstance(services, list):

        await message.answer(
            "❌ Xizmatlarni olishda xatolik."
        )

        await state.clear()

        return

    results = []

    for service in services:

        name = str(
            service.get(
                "name",
                ""
            )
        ).lower()

        category = str(
            service.get(
                "category",
                ""
            )
        ).lower()

        service_id = str(
            service.get(
                "service",
                ""
            )
        ).lower()

        if (
            query in name
            or query in category
            or query in service_id
        ):

            results.append(
                service
            )

    if not results:

        await message.answer(
            "❌ Hech qanday xizmat topilmadi.",
            reply_markup=main_keyboard()
        )

        await state.clear()

        return

    kb = InlineKeyboardBuilder()

    for service in results[:40]:

        service_id = str(
            service.get(
                "service"
            )
        )

        name = cut(
            service.get(
                "name",
                "Xizmat"
            ),
            45
        )

        kb.button(
            text=f"🛒 {service_id} | {name}",
            callback_data=f"service:{service_id}"
        )

    kb.adjust(1)

    await message.answer(
        f"""
🔎 <b>QIDIRUV NATIJALARI</b>

Topildi:
<b>{len(results)}</b> ta xizmat.

👇 Kerakli xizmatni tanlang:
""",
        reply_markup=kb.as_markup()
    )

    await state.clear()


# =========================================================
# HELP
# =========================================================

@dp.message(F.text == "ℹ️ Yordam")
async def help_page(message: Message):

    await message.answer(
        """
ℹ️ <b>BEST1SMM YORDAM</b>

🛒 <b>Buyurtma berish</b>
Xizmat → link → miqdor.

💰 <b>Balansim</b>
Hisobingizdagi mablag‘ni ko‘rsatadi.

➕ <b>Balans to‘ldirish</b>
Administrator orqali to‘ldiriladi.

📦 <b>Buyurtmalarim</b>
Buyurtmalaringiz ro‘yxati.

🔎 <b>Xizmat qidirish</b>
Xizmat nomi yoki ID orqali qidirish.

━━━━━━━━━━━━━━━━━━

👨‍💼 Support:
@YOUR_ADMIN_USERNAME
""",
        reply_markup=main_keyboard()
    )


# =========================================================
# STATUS
# =========================================================

@dp.message(Command("status"))
async def status_command(message: Message):

    parts = (
        message.text or ""
    ).split()

    if len(parts) != 2:

        await message.answer(
            "❌ Misol:\n/status 12345"
        )

        return

    result = await order_status(
        parts[1]
    )

    if "error" in result:

        await message.answer(
            f"❌ {result['error']}"
        )

        return

    await message.answer(
        f"""
📊 <b>BUYURTMA STATUSI</b>

🆔 Order:
<code>#{parts[1]}</code>

📊 Status:
<b>{result.get("status", "-")}</b>

🔢 Start:
<b>{result.get("start_count", "-")}</b>

📉 Remains:
<b>{result.get("remains", "-")}</b>

💵 Charge:
<b>{result.get("charge", "-")}</b>

💱 Currency:
<b>{result.get("currency", "UZS")}</b>
""",
        reply_markup=main_keyboard()
    )


# =========================================================
# REFILL
# =========================================================

@dp.message(Command("refill"))
async def refill_command(message: Message):

    parts = (
        message.text or ""
    ).split()

    if len(parts) != 2:

        await message.answer(
            "❌ Misol:\n/refill 12345"
        )

        return

    result = await refill_order(
        parts[1]
    )

    if "error" in result:

        await message.answer(
            f"❌ {result['error']}"
        )

        return

    await message.answer(
        f"""
♻️ <b>REFILL SO‘ROVI YUBORILDI</b>

🆔 Order:
<code>#{parts[1]}</code>

Javob:
<code>{result}</code>
""",
        reply_markup=main_keyboard()
    )


# =========================================================
# CANCEL
# =========================================================

@dp.message(Command("cancel"))
async def cancel_command(message: Message):

    parts = (
        message.text or ""
    ).split()

    if len(parts) != 2:

        await message.answer(
            "❌ Misol:\n/cancel 12345"
        )

        return

    result = await cancel_order(
        parts[1]
    )

    if "error" in result:

        await message.answer(
            f"❌ {result['error']}"
        )

        return

    await message.answer(
        f"""
❌ <b>BEKOR QILISH SO‘ROVI YUBORILDI</b>

🆔 Order:
<code>#{parts[1]}</code>

Javob:
<code>{result}</code>
""",
        reply_markup=main_keyboard()
    )


# =========================================================
# ADMIN
# =========================================================

def admin_keyboard():

    kb = InlineKeyboardBuilder()

    kb.button(
        text="📊 Statistika",
        callback_data="admin:stats"
    )

    kb.button(
        text="💰 Balans qo‘shish",
        callback_data="admin:add"
    )

    kb.button(
        text="💳 Panel balansi",
        callback_data="admin:balance"
    )

    kb.button(
        text="📦 Oxirgi buyurtmalar",
        callback_data="admin:orders"
    )

    kb.adjust(1)

    return kb.as_markup()


@dp.message(Command("admin"))
async def admin_command(message: Message):

    if message.from_user.id != ADMIN_ID:

        await message.answer(
            "❌ Siz admin emassiz."
        )

        return

    await message.answer(
        """
👨‍💼 <b>BEST1SMM ADMIN PANEL</b>

━━━━━━━━━━━━━━━━━━

Kerakli bo‘limni tanlang:
""",
        reply_markup=admin_keyboard()
    )


# =========================================================
# ADMIN STATS
# =========================================================

@dp.callback_query(
    F.data == "admin:stats"
)
async def admin_stats(
    call: CallbackQuery
):

    if call.from_user.id != ADMIN_ID:
        return

    con = get_db()
    cur = con.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM users"
    )

    users = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM orders"
    )

    orders = cur.fetchone()[0]

    cur.execute(
        "SELECT COALESCE(SUM(charge),0) FROM orders"
    )

    revenue = cur.fetchone()[0]

    con.close()

    await call.message.edit_text(
        f"""
📊 <b>BEST1SMM STATISTIKA</b>

👥 Foydalanuvchilar:
<b>{users}</b>

📦 Buyurtmalar:
<b>{orders}</b>

💰 Buyurtmalar summasi:
<b>{money(revenue)} so‘m</b>
""",
        reply_markup=admin_keyboard()
    )

    await call.answer()


# =========================================================
# ADMIN PANEL BALANCE
# =========================================================

@dp.callback_query(
    F.data == "admin:balance"
)
async def admin_panel_balance(
    call: CallbackQuery
):

    if call.from_user.id != ADMIN_ID:
        return

    result = await panel_balance()

    if "error" in result:

        await call.message.edit_text(
            f"❌ API xatosi:\n{result['error']}",
            reply_markup=admin_keyboard()
        )

        return

    await call.message.edit_text(
        f"""
💳 <b>SEENSMS PANEL BALANSI</b>

💰 Balans:
<b>{result.get("balance", "0")}</b>

💱 Valyuta:
<b>{result.get("currency", "UZS")}</b>
""",
        reply_markup=admin_keyboard()
    )

    await call.answer()


# =========================================================
# ADMIN ADD BALANCE
# =========================================================

@dp.callback_query(
    F.data == "admin:add"
)
async def admin_add(
    call: CallbackQuery,
    state: FSMContext
):

    if call.from_user.id != ADMIN_ID:
        return

    await call.message.answer(
        """
💰 <b>BALANS QO‘SHISH</b>

Foydalanuvchining Telegram ID'sini yuboring.

Masalan:
<code>123456789</code>
"""
    )

    await state.set_state(
        AdminState.waiting_user_id
    )

    await call.answer()


@dp.message(
    AdminState.waiting_user_id
)
async def admin_user_id(
    message: Message,
    state: FSMContext
):

    if message.from_user.id != ADMIN_ID:
        return

    try:

        user_id = int(
            message.text.strip()
        )

    except:

        await message.answer(
            "❌ ID faqat raqam bo‘lishi kerak."
        )

        return

    await state.update_data(
        user_id=user_id
    )

    await message.answer(
        """
💵 Qancha balans qo‘shamiz?

Masalan:
<code>10000</code>
"""
    )

    await state.set_state(
        AdminState.waiting_amount
    )


@dp.message(
    AdminState.waiting_amount
)
async def admin_amount(
    message: Message,
    state: FSMContext
):

    if message.from_user.id != ADMIN_ID:
        return

    try:

        amount = float(
            message.text.strip()
        )

    except:

        await message.answer(
            "❌ Summani to‘g‘ri kiriting."
        )

        return

    if amount <= 0:

        await message.answer(
            "❌ Summa 0 dan katta bo‘lishi kerak."
        )

        return

    data = await state.get_data()

    user_id = data["user_id"]

    con = get_db()
    cur = con.cursor()

    cur.execute(
        """
        INSERT OR IGNORE INTO users
        (user_id, balance)
        VALUES (?, 0)
        """,
        (user_id,)
    )

    con.commit()
    con.close()

    change_balance(
        user_id,
        amount
    )

    await message.answer(
        f"""
✅ <b>BALANS QO‘SHILDI</b>

👤 User:
<code>{user_id}</code>

💵 Qo‘shildi:
<b>{money(amount)} so‘m</b>

💰 Yangi balans:
<b>{money(get_balance(user_id))} so‘m</b>
""",
        reply_markup=admin_keyboard()
    )

    await state.clear()


# =========================================================
# ADMIN ORDERS
# =========================================================

@dp.callback_query(
    F.data == "admin:orders"
)
async def admin_orders(
    call: CallbackQuery
):

    if call.from_user.id != ADMIN_ID:
        return

    con = get_db()
    cur = con.cursor()

    cur.execute("""
        SELECT
            api_order,
            user_id,
            service_name,
            quantity,
            charge,
            status
        FROM orders
        ORDER BY id DESC
        LIMIT 15
    """)

    rows = cur.fetchall()

    con.close()

    text = "📦 <b>OXIRGI BUYURTMALAR</b>\n\n"

    if not rows:

        text += "Hali buyurtmalar yo‘q."

    else:

        for row in rows:

            text += (
                f"🆔 #{row[0]}\n"
                f"👤 {row[1]}\n"
                f"📌 {cut(row[2], 30)}\n"
                f"🔢 {row[3]}\n"
                f"💵 {money(row[4])}\n"
                f"📊 {row[5]}\n"
                f"━━━━━━━━━━━━\n"
            )

    await call.message.edit_text(
        text,
        reply_markup=admin_keyboard()
    )

    await call.answer()


# =========================================================
# RUN
# =========================================================

async def main():

    init_db()

    logger.info(
        "🚀 BEST1SMM BOT IS RUNNING"
    )

    await dp.start_polling(
        bot
    )


if __name__ == "__main__":

    asyncio.run(main())
