import os
import asyncio
import logging
import sqlite3
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

logger = logging.getLogger("Best1SMM")


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

def db():
    return sqlite3.connect(DB_NAME)


def init_db():

    con = db()
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

    con = db()
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

    con = db()
    cur = con.cursor()

    cur.execute(
        "SELECT balance FROM users WHERE user_id=?",
        (user_id,)
    )

    row = cur.fetchone()

    con.close()

    return float(row[0]) if row else 0


def change_balance(user_id, amount):

    con = db()
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
    link = State()
    quantity = State()


class SearchState(StatesGroup):
    query = State()


class AdminState(StatesGroup):
    user_id = State()
    amount = State()


# =========================================================
# HELPERS
# =========================================================

def money(number):
    try:
        return f"{float(number):,.2f}".replace(",", " ")
    except:
        return "0.00"


def short(text, length=45):

    text = str(text)

    if len(text) > length:
        return text[:length - 3] + "..."

    return text


# =========================================================
# BOTTOM MENU
# =========================================================

def main_menu():

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="🛒 Buyurtma berish"
                ),
                KeyboardButton(
                    text="📦 Buyurtmalarim"
                )
            ],
            [
                KeyboardButton(
                    text="💰 Balansim"
                ),
                KeyboardButton(
                    text="➕ Balans to‘ldirish"
                )
            ],
            [
                KeyboardButton(
                    text="🔎 Xizmat qidirish"
                ),
                KeyboardButton(
                    text="ℹ️ Yordam"
                )
            ]
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Best1SMM menyusi..."
    )


# =========================================================
# SEENSMS API
# =========================================================

async def api(action, **params):

    payload = {
        "key": SMM_API_KEY,
        "action": action
    }

    payload.update(params)

    try:

        timeout = aiohttp.ClientTimeout(
            total=40
        )

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
                except:
                    return {
                        "error": text
                    }

    except Exception as e:

        logger.error(
            f"API error: {e}"
        )

        return {
            "error": "SeenSMS API bilan aloqa bo‘lmadi."
        }


async def services():

    return await api("services")


async def create_order(
    service,
    link,
    quantity
):

    return await api(
        "add",
        service=service,
        link=link,
        quantity=quantity
    )


async def get_order_status(order):

    return await api(
        "status",
        order=order
    )


# =========================================================
# PLATFORM FILTER
# =========================================================

PLATFORMS = {
    "instagram": {
        "title": "📸 Instagram",
        "keywords": [
            "instagram",
            "insta"
        ]
    },

    "tiktok": {
        "title": "🎵 TikTok",
        "keywords": [
            "tiktok",
            "tik tok"
        ]
    },

    "telegram": {
        "title": "📱 Telegram",
        "keywords": [
            "telegram",
            "tg"
        ]
    },

    "youtube": {
        "title": "▶️ YouTube",
        "keywords": [
            "youtube",
            "youtu.be"
        ]
    }
}


def detect_platform(service):

    text = (
        str(service.get("name", "")) + " " +
        str(service.get("category", ""))
    ).lower()

    for platform, info in PLATFORMS.items():

        for keyword in info["keywords"]:

            if keyword in text:
                return platform

    return None


def filtered_services(all_services):

    result = {
        "instagram": [],
        "tiktok": [],
        "telegram": [],
        "youtube": []
    }

    if not isinstance(all_services, list):
        return result

    for service in all_services:

        platform = detect_platform(service)

        if platform:
            result[platform].append(service)

    return result


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start(
    message: Message,
    state: FSMContext
):

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
╔══════════════════════╗
     🚀 <b>BEST1SMM</b>
╚══════════════════════╝

Assalomu alaykum,
<b>{name}</b>! 👋

✨ SMM xizmatlarining qulay
va tezkor markaziga xush kelibsiz!

📸 Instagram
🎵 TikTok
📱 Telegram
▶️ YouTube

━━━━━━━━━━━━━━━━━━━━

💰 Balans:
<b>{money(balance)} so‘m</b>

━━━━━━━━━━━━━━━━━━━━

👇 Pastdagi menyudan foydalaning.
""",
        reply_markup=main_menu()
    )


# =========================================================
# ORDER PLATFORM MENU
# =========================================================

@dp.message(F.text == "🛒 Buyurtma berish")
async def order_menu(message: Message):

    msg = await message.answer(
        "⏳ <b>Xizmatlar yuklanmoqda...</b>"
    )

    all_services = await services()

    if not isinstance(all_services, list):

        await msg.edit_text(
            f"""
❌ <b>XIZMATLARNI YUKLAB BO‘LMADI</b>

{all_services.get("error", "Noma’lum API xatosi")}
"""
        )

        return

    data = filtered_services(
        all_services
    )

    kb = InlineKeyboardBuilder()

    for platform, info in PLATFORMS.items():

        count = len(
            data[platform]
        )

        if count > 0:

            kb.button(
                text=f"{info['title']} • {count} ta",
                callback_data=f"platform:{platform}"
            )

    kb.adjust(1)

    total = sum(
        len(x)
        for x in data.values()
    )

    await msg.edit_text(
        f"""
╔══════════════════════╗
     🛒 <b>YANGI BUYURTMA</b>
╚══════════════════════╝

✨ Kerakli platformani tanlang.

📦 Mavjud xizmatlar:
<b>{total}</b> ta

━━━━━━━━━━━━━━━━━━━━
📸 Instagram
🎵 TikTok
📱 Telegram
▶️ YouTube
━━━━━━━━━━━━━━━━━━━━
""",
        reply_markup=kb.as_markup()
    )


# =========================================================
# PLATFORM
# =========================================================

@dp.callback_query(
    F.data.startswith("platform:")
)
async def platform_menu(
    call: CallbackQuery
):

    platform = call.data.split(
        ":",
        1
    )[1]

    if platform not in PLATFORMS:

        await call.answer(
            "Platforma topilmadi!",
            show_alert=True
        )

        return

    all_services = await services()

    if not isinstance(all_services, list):

        await call.answer(
            "API xatosi!",
            show_alert=True
        )

        return

    data = filtered_services(
        all_services
    )

    items = data[platform]

    kb = InlineKeyboardBuilder()

    for service in items[:100]:

        service_id = str(
            service.get(
                "service",
                ""
            )
        )

        name = short(
            service.get(
                "name",
                "Xizmat"
            ),
            48
        )

        kb.button(
            text=f"🛒 {service_id} • {name}",
            callback_data=f"service:{service_id}"
        )

    kb.button(
        text="⬅️ Platformalar",
        callback_data="platforms"
    )

    kb.adjust(1)

    title = PLATFORMS[
        platform
    ]["title"]

    await call.message.edit_text(
        f"""
╔══════════════════════╗
     {title}
╚══════════════════════╝

📦 Xizmatlar:
<b>{len(items)}</b> ta

👇 Kerakli xizmatni tanlang:
""",
        reply_markup=kb.as_markup()
    )

    await call.answer()


# =========================================================
# BACK TO PLATFORMS
# =========================================================

@dp.callback_query(
    F.data == "platforms"
)
async def platforms_back(
    call: CallbackQuery
):

    all_services = await services()

    data = filtered_services(
        all_services
    )

    kb = InlineKeyboardBuilder()

    for platform, info in PLATFORMS.items():

        count = len(
            data[platform]
        )

        if count:

            kb.button(
                text=f"{info['title']} • {count} ta",
                callback_data=f"platform:{platform}"
            )

    kb.adjust(1)

    await call.message.edit_text(
        """
🛒 <b>PLATFORMA TANLANG</b>

Qaysi platformaga xizmat kerak?
""",
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

    all_services = await services()

    if not isinstance(all_services, list):

        await call.answer(
            "API xatosi!",
            show_alert=True
        )

        return

    service = next(
        (
            x for x in all_services
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

    platform = detect_platform(
        service
    )

    kb = InlineKeyboardBuilder()

    kb.button(
        text="🛒 BUYURTMA BERISH",
        callback_data=f"buy:{service_id}"
    )

    if platform:
        kb.button(
            text="⬅️ Orqaga",
            callback_data=f"platform:{platform}"
        )

    kb.adjust(1)

    refill = (
        "✅ Mavjud"
        if service.get("refill")
        else "❌ Yo‘q"
    )

    cancel = (
        "✅ Mavjud"
        if service.get("cancel")
        else "❌ Yo‘q"
    )

    await call.message.edit_text(
        f"""
╔══════════════════════╗
     📋 <b>XIZMAT</b>
╚══════════════════════╝

🆔 ID:
<code>{service_id}</code>

📌 <b>{service.get("name", "Xizmat")}</b>

📂 Kategoriya:
{service.get("category", "-")}

━━━━━━━━━━━━━━━━━━━━

💵 Narx:
<b>{service.get("rate", "0")}</b> / 1000

🔽 Minimum:
<b>{service.get("min", "0")}</b>

🔼 Maximum:
<b>{service.get("max", "0")}</b>

♻️ Refill:
{refill}

❌ Cancel:
{cancel}

━━━━━━━━━━━━━━━━━━━━

👇 Buyurtma berish uchun tugmani bosing.
""",
        reply_markup=kb.as_markup()
    )

    await call.answer()


# =========================================================
# START ORDER
# =========================================================

@dp.callback_query(
    F.data.startswith("buy:")
)
async def start_buy(
    call: CallbackQuery,
    state: FSMContext
):

    service_id = call.data.split(
        ":",
        1
    )[1]

    all_services = await services()

    service = next(
        (
            x for x in all_services
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

━━━━━━━━━━━━━━━━━━━━

Masalan:
<code>https://instagram.com/...</code>
"""
    )

    await state.set_state(
        OrderState.link
    )

    await call.answer()


# =========================================================
# LINK
# =========================================================

@dp.message(OrderState.link)
async def receive_link(
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
            "❌ To‘g‘ri link yuboring."
        )

        return

    await state.update_data(
        link=link
    )

    data = await state.get_data()

    await message.answer(
        f"""
🔢 <b>MIQDORNI YUBORING</b>

🔽 Minimum:
<b>{data["minimum"]}</b>

🔼 Maximum:
<b>{data["maximum"]}</b>

Masalan:
<code>1000</code>
"""
    )

    await state.set_state(
        OrderState.quantity
    )


# =========================================================
# QUANTITY
# =========================================================

@dp.message(OrderState.quantity)
async def receive_quantity(
    message: Message,
    state: FSMContext
):

    try:
        quantity = int(
            message.text.strip()
        )
    except:
        await message.answer(
            "❌ Miqdorni raqam bilan kiriting."
        )
        return

    data = await state.get_data()

    if quantity < data["minimum"]:

        await message.answer(
            f"❌ Minimum: <b>{data['minimum']}</b>"
        )

        return

    if quantity > data["maximum"]:

        await message.answer(
            f"❌ Maximum: <b>{data['maximum']}</b>"
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

💵 Buyurtma:
<b>{money(price)} so‘m</b>

💰 Balansingiz:
<b>{money(balance)} so‘m</b>

📉 Yetishmayapti:
<b>{money(price - balance)} so‘m</b>

👇 Avval balansni to‘ldiring.
""",
            reply_markup=main_menu()
        )

        await state.clear()

        return

    await message.answer(
        "⏳ <b>Buyurtma yuborilmoqda...</b>"
    )

    result = await create_order(
        service=data["service_id"],
        link=data["link"],
        quantity=quantity
    )

    if not isinstance(result, dict):

        await message.answer(
            "❌ API noto‘g‘ri javob berdi."
        )

        await state.clear()

        return

    if "error" in result:

        await message.answer(
            f"""
❌ <b>BUYURTMA BERILMADI</b>

Sabab:
{result["error"]}
""",
            reply_markup=main_menu()
        )

        await state.clear()

        return

    api_order = result.get(
        "order"
    )

    if not api_order:

        await message.answer(
            "❌ Order ID olinmadi."
        )

        await state.clear()

        return

    change_balance(
        message.from_user.id,
        -price
    )

    con = db()
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
        "",
        data["link"],
        quantity,
        price,
        "Pending"
    ))

    con.commit()
    con.close()

    await message.answer(
        f"""
╔══════════════════════╗
     🎉 <b>BUYURTMA QABUL QILINDI</b>
╚══════════════════════╝

🆔 Buyurtma:
<code>#{api_order}</code>

📌 Xizmat:
<b>{data["service_name"]}</b>

🔢 Miqdor:
<b>{quantity}</b>

💵 Narx:
<b>{money(price)} so‘m</b>

📊 Holat:
<b>Pending</b>

━━━━━━━━━━━━━━━━━━━━

💰 Qolgan balans:
<b>{money(get_balance(message.from_user.id))} so‘m</b>
""",
        reply_markup=main_menu()
    )

    await state.clear()


# =========================================================
# BALANCE
# =========================================================

@dp.message(F.text == "💰 Balansim")
async def balance(message: Message):

    amount = get_balance(
        message.from_user.id
    )

    await message.answer(
        f"""
╔══════════════════════╗
     💰 <b>BALANSIM</b>
╚══════════════════════╝

💵 Joriy balans:

<b>{money(amount)} so‘m</b>

━━━━━━━━━━━━━━━━━━━━

➕ Balans to‘ldirish uchun
pastdagi tugmadan foydalaning.
""",
        reply_markup=main_menu()
    )


# =========================================================
# DEPOSIT
# =========================================================

@dp.message(F.text == "➕ Balans to‘ldirish")
async def deposit(message: Message):

    await message.answer(
        """
╔══════════════════════╗
   ➕ <b>BALANS TO‘LDIRISH</b>
╚══════════════════════╝

💳 Balansni to‘ldirish uchun
administrator bilan bog‘laning.

👨‍💼 Admin:
@rxk_17

━━━━━━━━━━━━━━━━━━━━

⚠️ To‘lovni faqat rasmiy
administratorga yuboring.
""",
        reply_markup=main_menu()
    )


# =========================================================
# MY ORDERS
# =========================================================

@dp.message(F.text == "📦 Buyurtmalarim")
async def my_orders(message: Message):

    con = db()
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
        LIMIT 15
    """, (
        message.from_user.id,
    ))

    rows = cur.fetchall()

    con.close()

    if not rows:

        await message.answer(
            """
📦 <b>BUYURTMALARIM</b>

Sizda hali buyurtmalar yo‘q.
""",
            reply_markup=main_menu()
        )

        return

    text = "📦 <b>BUYURTMALARIM</b>\n\n"

    for row in rows:

        text += (
            f"🆔 <code>#{row[0]}</code>\n"
            f"📌 {short(row[1], 35)}\n"
            f"🔢 {row[2]}\n"
            f"💵 {money(row[3])} so‘m\n"
            f"📊 {row[4]}\n"
            f"━━━━━━━━━━━━\n"
        )

    await message.answer(
        text,
        reply_markup=main_menu()
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

Xizmat nomini yoki Service ID
ni yuboring.

Masalan:

<code>Instagram</code>
<code>TikTok</code>
<code>Telegram</code>
<code>YouTube</code>
"""
    )

    await state.set_state(
        SearchState.query
    )


@dp.message(SearchState.query)
async def search(
    message: Message,
    state: FSMContext
):

    query = (
        message.text or ""
    ).lower().strip()

    all_services = await services()

    if not isinstance(all_services, list):

        await message.answer(
            "❌ API xatosi."
        )

        await state.clear()

        return

    allowed = []

    for service in all_services:

        if not detect_platform(service):
            continue

        text = (
            str(service.get("name", "")) +
            " " +
            str(service.get("category", "")) +
            " " +
            str(service.get("service", ""))
        ).lower()

        if query in text:
            allowed.append(service)

    if not allowed:

        await message.answer(
            "❌ Xizmat topilmadi.",
            reply_markup=main_menu()
        )

        await state.clear()

        return

    kb = InlineKeyboardBuilder()

    for service in allowed[:50]:

        service_id = str(
            service.get("service")
        )

        name = short(
            service.get("name", "Xizmat"),
            45
        )

        kb.button(
            text=f"🛒 {service_id} • {name}",
            callback_data=f"service:{service_id}"
        )

    kb.adjust(1)

    await message.answer(
        f"""
🔎 <b>QIDIRUV NATIJALARI</b>

Topildi:
<b>{len(allowed)}</b> ta xizmat.
""",
        reply_markup=kb.as_markup()
    )

    await state.clear()


# =========================================================
# HELP
# =========================================================

@dp.message(F.text == "ℹ️ Yordam")
async def help_message(message: Message):

    await message.answer(
        """
╔══════════════════════╗
       ℹ️ <b>YORDAM</b>
╚══════════════════════╝

🛒 <b>Buyurtma berish</b>
Platformani tanlang → xizmat →
link → miqdor.

💰 <b>Balansim</b>
Hisobingizdagi mablag‘.

➕ <b>Balans to‘ldirish</b>
Administrator orqali.

📦 <b>Buyurtmalarim</b>
Buyurtmalaringiz tarixi.

🔎 <b>Xizmat qidirish</b>
Kerakli xizmatni tez topish.

━━━━━━━━━━━━━━━━━━━━

📸 Instagram
🎵 TikTok
📱 Telegram
▶️ YouTube
""",
        reply_markup=main_menu()
    )


# =========================================================
# STATUS COMMAND
# =========================================================

@dp.message(Command("status"))
async def status(message: Message):

    parts = (
        message.text or ""
    ).split()

    if len(parts) != 2:

        await message.answer(
            "Misol: <code>/status 12345</code>"
        )

        return

    result = await get_order_status(
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

📉 Qoldiq:
<b>{result.get("remains", "-")}</b>
"""
    )


# =========================================================
# ADMIN PANEL
# =========================================================

def admin_menu():

    kb = InlineKeyboardBuilder()

    kb.button(
        text="📊 Statistika",
        callback_data="admin_stats"
    )

    kb.button(
        text="💰 Balans qo‘shish",
        callback_data="admin_add"
    )

    kb.button(
        text="📦 Buyurtmalar",
        callback_data="admin_orders"
    )

    kb.adjust(1)

    return kb.as_markup()


@dp.message(Command("admin"))
async def admin(message: Message):

    if message.from_user.id != ADMIN_ID:

        await message.answer(
            "❌ Siz admin emassiz."
        )

        return

    await message.answer(
        """
╔══════════════════════╗
     👑 <b>ADMIN PANEL</b>
╚══════════════════════╝

Best1SMM boshqaruv paneli
""",
        reply_markup=admin_menu()
    )


# =========================================================
# ADMIN STATS
# =========================================================

@dp.callback_query(
    F.data == "admin_stats"
)
async def admin_stats(
    call: CallbackQuery
):

    if call.from_user.id != ADMIN_ID:
        return

    con = db()
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
    total = cur.fetchone()[0]

    con.close()

    await call.message.edit_text(
        f"""
📊 <b>BEST1SMM STATISTIKA</b>

👥 Users:
<b>{users}</b>

📦 Buyurtmalar:
<b>{orders}</b>

💰 Savdo:
<b>{money(total)} so‘m</b>
""",
        reply_markup=admin_menu()
    )

    await call.answer()


# =========================================================
# ADMIN ADD BALANCE
# =========================================================

@dp.callback_query(
    F.data == "admin_add"
)
async def admin_add(
    call: CallbackQuery,
    state: FSMContext
):

    if call.from_user.id != ADMIN_ID:
        return

    await call.message.answer(
        """
👤 Foydalanuvchi Telegram ID'sini yuboring:

<code>123456789</code>
"""
    )

    await state.set_state(
        AdminState.user_id
    )

    await call.answer()


@dp.message(AdminState.user_id)
async def admin_user(
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
            "❌ ID raqam bo‘lishi kerak."
        )
        return

    await state.update_data(
        user_id=user_id
    )

    await message.answer(
        """
💵 Qancha pul qo‘shamiz?

Masalan:
<code>10000</code>
"""
    )

    await state.set_state(
        AdminState.amount
    )


@dp.message(AdminState.amount)
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
            "❌ Summa 0 dan katta bo‘lsin."
        )
        return

    data = await state.get_data()

    user_id = data["user_id"]

    con = db()
    cur = con.cursor()

    cur.execute("""
        INSERT OR IGNORE INTO users
        (user_id, balance)
        VALUES (?, 0)
    """, (user_id,))

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
        reply_markup=admin_menu()
    )

    await state.clear()


# =========================================================
# ADMIN ORDERS
# =========================================================

@dp.callback_query(
    F.data == "admin_orders"
)
async def admin_orders(
    call: CallbackQuery
):

    if call.from_user.id != ADMIN_ID:
        return

    con = db()
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
        LIMIT 20
    """)

    rows = cur.fetchall()

    con.close()

    text = "📦 <b>OXIRGI BUYURTMALAR</b>\n\n"

    for row in rows:

        text += (
            f"🆔 #{row[0]}\n"
            f"👤 {row[1]}\n"
            f"📌 {short(row[2], 30)}\n"
            f"🔢 {row[3]}\n"
            f"💵 {money(row[4])}\n"
            f"📊 {row[5]}\n"
            f"━━━━━━━━━━━━\n"
        )

    if not rows:
        text += "Hali buyurtma yo‘q."

    await call.message.edit_text(
        text,
        reply_markup=admin_menu()
    )

    await call.answer()


# =========================================================
# RUN
# =========================================================

async def main():

    init_db()

    logger.info(
        "🚀 BEST1SMM PRO IS RUNNING"
    )

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
