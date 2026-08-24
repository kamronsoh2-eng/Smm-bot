import asyncio
import logging
import os
import sqlite3
from datetime import datetime

import aiohttp

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


# =========================================================
# SETTINGS
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
SEENSMS_API_KEY = os.getenv("SEENSMS_API_KEY")

# SeenSMS API manzilini Render Environment Variable'dan olish
SEENSMS_API_URL = os.getenv(
    "SEENSMS_API_URL",
    "https://seensms.uz/api/v1"
)

ADMIN_USERNAME = "rxk_17"

DB_NAME = "best1smm.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("BEST1SMM")


# =========================================================
# BOT
# =========================================================

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi!")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    )
)

dp = Dispatcher(
    storage=MemoryStorage()
)


# =========================================================
# DATABASE
# =========================================================

def db():
    return sqlite3.connect(DB_NAME)


def init_db():

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance REAL DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            api_order_id TEXT,
            platform TEXT,
            service_id TEXT,
            service_name TEXT,
            quantity INTEGER,
            price REAL,
            link TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS balance_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            admin_username TEXT,
            amount REAL,
            operation TEXT,
            old_balance REAL,
            new_balance REAL,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


def save_user(user):

    conn = db()
    cur = conn.cursor()

    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    cur.execute("""
        INSERT INTO users (
            user_id,
            username,
            first_name,
            balance,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, 0, ?, ?)

        ON CONFLICT(user_id)
        DO UPDATE SET
            username=excluded.username,
            first_name=excluded.first_name,
            updated_at=excluded.updated_at
    """, (
        user.id,
        user.username or "",
        user.first_name or "",
        now,
        now
    ))

    conn.commit()
    conn.close()


def get_balance(user_id):

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT balance FROM users WHERE user_id=?",
        (user_id,)
    )

    row = cur.fetchone()

    conn.close()

    if not row:
        return 0

    return float(row[0])


def change_balance(
    user_id,
    amount,
    operation,
    admin_username
):

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT balance FROM users WHERE user_id=?",
        (user_id,)
    )

    row = cur.fetchone()

    if not row:
        conn.close()
        return None

    old_balance = float(row[0])

    if operation == "add":
        new_balance = old_balance + amount

    elif operation == "remove":
        new_balance = old_balance - amount

    else:
        conn.close()
        return None

    if new_balance < 0:
        conn.close()
        return False

    cur.execute("""
        UPDATE users
        SET balance=?, updated_at=?
        WHERE user_id=?
    """, (
        new_balance,
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        user_id
    ))

    cur.execute("""
        INSERT INTO balance_logs (
            user_id,
            admin_username,
            amount,
            operation,
            old_balance,
            new_balance,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        admin_username,
        amount,
        operation,
        old_balance,
        new_balance,
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    ))

    conn.commit()
    conn.close()

    return new_balance


def charge_balance(user_id, amount):

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT balance FROM users WHERE user_id=?",
        (user_id,)
    )

    row = cur.fetchone()

    if not row:
        conn.close()
        return False

    balance = float(row[0])

    if balance < amount:
        conn.close()
        return False

    new_balance = balance - amount

    cur.execute("""
        UPDATE users
        SET balance=?, updated_at=?
        WHERE user_id=?
    """, (
        new_balance,
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        user_id
    ))

    conn.commit()
    conn.close()

    return new_balance


def restore_balance(user_id, amount):

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET balance=balance+?
        WHERE user_id=?
    """, (
        amount,
        user_id
    ))

    conn.commit()
    conn.close()


def save_order(
    user_id,
    api_order_id,
    platform,
    service_id,
    service_name,
    quantity,
    price,
    link
):

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO orders (
            user_id,
            api_order_id,
            platform,
            service_id,
            service_name,
            quantity,
            price,
            link,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        str(api_order_id),
        platform,
        str(service_id),
        service_name,
        quantity,
        price,
        link,
        "pending",
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    ))

    conn.commit()
    conn.close()


def statistics():

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM users"
    )
    users = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM orders"
    )
    orders = cur.fetchone()[0]

    cur.execute(
        "SELECT COALESCE(SUM(price),0) FROM orders"
    )
    revenue = cur.fetchone()[0]

    cur.execute(
        "SELECT COALESCE(SUM(balance),0) FROM users"
    )
    balances = cur.fetchone()[0]

    conn.close()

    return users, orders, revenue, balances


def get_users():

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT user_id FROM users"
    )

    result = [
        x[0]
        for x in cur.fetchall()
    ]

    conn.close()

    return result


# =========================================================
# STATES
# =========================================================

class OrderState(StatesGroup):

    platform = State()
    service = State()
    quantity = State()
    link = State()
    confirm = State()


class AdminBalanceState(StatesGroup):

    user_id = State()
    amount = State()
    confirm = State()


class AdminBroadcastState(StatesGroup):

    message = State()


# =========================================================
# PLATFORM
# =========================================================

PLATFORMS = {

    "youtube": {
        "title": "▶️ YouTube",
        "keywords": [
            "youtube",
            "youtu.be"
        ],
        "domains": [
            "youtube.com",
            "youtu.be"
        ]
    },

    "telegram": {
        "title": "✈️ Telegram",
        "keywords": [
            "telegram",
            "t.me"
        ],
        "domains": [
            "t.me",
            "telegram.me"
        ]
    },

    "instagram": {
        "title": "📸 Instagram",
        "keywords": [
            "instagram",
            "insta"
        ],
        "domains": [
            "instagram.com"
        ]
    },

    "tiktok": {
        "title": "🎵 TikTok",
        "keywords": [
            "tiktok",
            "tik tok"
        ],
        "domains": [
            "tiktok.com"
        ]
    }
}


# =========================================================
# MAIN REPLY KEYBOARD
# =========================================================

def main_keyboard():

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="🛒 Buyurtma berish"
                ),
                KeyboardButton(
                    text="💳 Hisobni to‘ldirish"
                )
            ],
            [
                KeyboardButton(
                    text="👤 Shaxsiy kabinet"
                ),
                KeyboardButton(
                    text="🆘 Yordam"
                )
            ]
        ],
        resize_keyboard=True,
        is_persistent=True
    )


# =========================================================
# INLINE ORDER KEYBOARDS
# =========================================================

def platform_keyboard():

    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="▶️ YouTube",
            callback_data="platform:youtube"
        ),
        InlineKeyboardButton(
            text="✈️ Telegram",
            callback_data="platform:telegram"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="📸 Instagram",
            callback_data="platform:instagram"
        ),
        InlineKeyboardButton(
            text="🎵 TikTok",
            callback_data="platform:tiktok"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="🔙 Orqaga",
            callback_data="order_back_main"
        )
    )

    return builder.as_markup()


def back_order():

    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="🔙 Orqaga",
            callback_data="order_back_platform"
        ),
        InlineKeyboardButton(
            text="❌ Bekor qilish",
            callback_data="order_cancel"
        )
    )

    return builder.as_markup()


def confirm_order_keyboard():

    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="✅ BUYURTMA BERISH",
            callback_data="order_confirm"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="🔙 Orqaga",
            callback_data="order_back_link"
        ),
        InlineKeyboardButton(
            text="❌ Bekor qilish",
            callback_data="order_cancel"
        )
    )

    return builder.as_markup()


# =========================================================
# ADMIN KEYBOARDS
# =========================================================

def admin_keyboard():

    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="📊 Statistika",
            callback_data="adm:stats"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="👥 Foydalanuvchilar",
            callback_data="adm:users"
        ),
        InlineKeyboardButton(
            text="📦 Buyurtmalar",
            callback_data="adm:orders"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="💳 Balans boshqaruvi",
            callback_data="adm:balance"
        ),
        InlineKeyboardButton(
            text="📜 Balans tarixi",
            callback_data="adm:logs"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="🔌 API holati",
            callback_data="adm:api"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="📢 Reklama yuborish",
            callback_data="adm:broadcast"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="🔄 Yangilash",
            callback_data="adm:panel"
        ),
        InlineKeyboardButton(
            text="🏠 Asosiy menyu",
            callback_data="adm:home"
        )
    )

    return builder.as_markup()


def admin_back():

    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="🔙 Admin panel",
            callback_data="adm:panel"
        )
    )

    return builder.as_markup()


def balance_admin_keyboard():

    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="➕ Balans qo‘shish",
            callback_data="adm:add_balance"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="➖ Balansdan ayirish",
            callback_data="adm:remove_balance"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="🔎 Balansni tekshirish",
            callback_data="adm:check_balance"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="🔙 Admin panel",
            callback_data="adm:panel"
        )
    )

    return builder.as_markup()


# =========================================================
# HELPERS
# =========================================================

def is_admin(user):

    return bool(
        user.username
        and user.username.lower()
        == ADMIN_USERNAME.lower()
    )


def valid_number(text):

    try:
        value = float(
            text.replace(" ", "")
        )

        if value <= 0:
            return None

        return value

    except Exception:
        return None


def service_matches(service, platform):

    data = PLATFORMS[platform]

    text = (
        str(service.get("name", ""))
        + " "
        + str(service.get("category", ""))
    ).lower()

    return any(
        keyword in text
        for keyword in data["keywords"]
    )


def calculate_price(rate, quantity):

    try:
        return (
            float(rate)
            * int(quantity)
            / 1000
        )
    except Exception:
        return 0


# =========================================================
# SEENSMS API
# =========================================================

async def api_request(data):

    if not SEENSMS_API_KEY:
        raise RuntimeError(
            "SEENSMS_API_KEY Render'da yo‘q!"
        )

    payload = {
        "key": SEENSMS_API_KEY,
        **data
    }

    timeout = aiohttp.ClientTimeout(
        total=30
    )

    async with aiohttp.ClientSession(
        timeout=timeout
    ) as session:

        async with session.post(
            SEENSMS_API_URL,
            data=payload
        ) as response:

            text = await response.text()

            if response.status != 200:
                raise RuntimeError(
                    f"HTTP {response.status}: "
                    f"{text[:300]}"
                )

            try:
                return await response.json()
            except Exception:
                raise RuntimeError(
                    text[:500]
                )


async def api_services():

    return await api_request({
        "action": "services"
    })


async def api_balance():

    return await api_request({
        "action": "balance"
    })


async def api_add_order(
    service,
    link,
    quantity
):

    return await api_request({
        "action": "add",
        "service": service,
        "link": link,
        "quantity": quantity
    })


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start(
    message: Message,
    state: FSMContext
):

    await state.clear()

    save_user(
        message.from_user
    )

    await message.answer(
        "✨ <b>BEST1SMM</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🚀 SMM xizmatlar paneliga xush kelibsiz!\n\n"
        "⚡ Tezkor xizmatlar\n"
        "📈 Qulay buyurtmalar\n"
        "💳 Admin orqali balans to‘ldirish\n\n"
        "👇 <b>Kerakli bo‘limni tanlang:</b>",
        reply_markup=main_keyboard()
    )


# =========================================================
# ORDER START
# =========================================================

@dp.message(
    F.text == "🛒 Buyurtma berish"
)
async def order_start(
    message: Message,
    state: FSMContext
):

    await state.set_state(
        OrderState.platform
    )

    await message.answer(
        "🛒 <b>BUYURTMA BERISH</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🌐 Qaysi platformaga buyurtma "
        "bermoqchisiz?",
        reply_markup=platform_keyboard()
    )


# =========================================================
# PLATFORM
# =========================================================

@dp.callback_query(
    OrderState.platform,
    F.data.startswith("platform:")
)
async def choose_platform(
    callback: CallbackQuery,
    state: FSMContext
):

    platform = callback.data.split(":")[1]

    await state.update_data(
        platform=platform
    )

    await callback.message.edit_text(
        "⏳ <b>Xizmatlar yuklanmoqda...</b>"
    )

    try:

        services = await api_services()

        if not isinstance(
            services,
            list
        ):

            await callback.message.edit_text(
                "❌ <b>API noto‘g‘ri javob qaytardi.</b>",
                reply_markup=platform_keyboard()
            )

            return

        filtered = [
            service
            for service in services
            if service_matches(
                service,
                platform
            )
        ]

        if not filtered:

            await callback.message.edit_text(
                "😔 <b>Bu platforma uchun xizmat "
                "topilmadi.</b>",
                reply_markup=platform_keyboard()
            )

            return

        await state.update_data(
            services=filtered
        )

        builder = InlineKeyboardBuilder()

        for service in filtered:

            sid = service.get("service")
            name = str(
                service.get(
                    "name",
                    "Xizmat"
                )
            )

            if len(name) > 45:
                name = name[:42] + "..."

            builder.row(
                InlineKeyboardButton(
                    text=f"⚡ {name}",
                    callback_data=f"service:{sid}"
                )
            )

        builder.row(
            InlineKeyboardButton(
                text="🔙 Platformalar",
                callback_data="order_back_platform"
            )
        )

        await state.set_state(
            OrderState.service
        )

        await callback.message.edit_text(
            f"{PLATFORMS[platform]['title']}\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "⚡ <b>Xizmatni tanlang:</b>",
            reply_markup=builder.as_markup()
        )

    except Exception as error:

        logger.exception(error)

        await callback.message.edit_text(
            "❌ <b>SeenSMS API bilan aloqa "
            "bo‘lmadi.</b>",
            reply_markup=platform_keyboard()
        )

    await callback.answer()


# =========================================================
# SERVICE
# =========================================================

@dp.callback_query(
    OrderState.service,
    F.data.startswith("service:")
)
async def choose_service(
    callback: CallbackQuery,
    state: FSMContext
):

    service_id = callback.data.split(":")[1]

    data = await state.get_data()

    selected = None

    for service in data.get(
        "services",
        []
    ):

        if str(
            service.get("service")
        ) == service_id:

            selected = service
            break

    if not selected:

        await callback.answer(
            "Xizmat topilmadi!",
            show_alert=True
        )

        return

    await state.update_data(
        service_id=service_id,
        service_name=selected.get(
            "name",
            "Xizmat"
        ),
        rate=selected.get("rate"),
        minimum=selected.get("min"),
        maximum=selected.get("max")
    )

    await state.set_state(
        OrderState.quantity
    )

    await callback.message.edit_text(
        "🔢 <b>MIQDORNI KIRITING</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⚡ Xizmat:\n"
        f"<b>{selected.get('name')}</b>\n\n"
        f"📊 Minimum: <b>{selected.get('min')}</b>\n"
        f"📈 Maximum: <b>{selected.get('max')}</b>\n\n"
        "👇 Nechta kerakligini yozing:",
        reply_markup=back_order()
    )

    await callback.answer()


# =========================================================
# QUANTITY
# =========================================================

@dp.message(
    OrderState.quantity
)
async def quantity(
    message: Message,
    state: FSMContext
):

    if not message.text:
        return

    text = message.text.strip()

    if not text.isdigit():

        await message.answer(
            "❌ <b>Faqat butun son kiriting.</b>\n\n"
            "Masalan: <code>1000</code>",
            reply_markup=back_order()
        )

        return

    quantity_value = int(text)

    data = await state.get_data()

    minimum = int(
        float(data.get("minimum", 0))
    )

    maximum = int(
        float(data.get("maximum", 0))
    )

    if minimum and quantity_value < minimum:

        await message.answer(
            f"❌ Minimum miqdor: "
            f"<b>{minimum}</b>",
            reply_markup=back_order()
        )

        return

    if maximum and quantity_value > maximum:

        await message.answer(
            f"❌ Maximum miqdor: "
            f"<b>{maximum}</b>",
            reply_markup=back_order()
        )

        return

    price = calculate_price(
        data.get("rate"),
        quantity_value
    )

    await state.update_data(
        quantity=quantity_value,
        price=price
    )

    await state.set_state(
        OrderState.link
    )

    await message.answer(
        "🔗 <b>HAVOLANI KIRITING</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔢 Miqdor: <b>{quantity_value:,}</b>\n"
        f"💰 Narx: <b>{price:,.2f} so‘m</b>\n\n"
        "📎 Buyurtma havolasini yuboring:",
        reply_markup=back_order()
    )


# =========================================================
# LINK
# =========================================================

@dp.message(
    OrderState.link
)
async def link(
    message: Message,
    state: FSMContext
):

    if not message.text:
        return

    link_value = message.text.strip()

    if not (
        link_value.startswith("https://")
        or link_value.startswith("http://")
    ):

        await message.answer(
            "❌ <b>Havola noto‘g‘ri.</b>\n\n"
            "https:// bilan boshlanadigan "
            "havola yuboring.",
            reply_markup=back_order()
        )

        return

    data = await state.get_data()

    platform = data["platform"]

    domains = PLATFORMS[
        platform
    ]["domains"]

    if not any(
        domain in link_value.lower()
        for domain in domains
    ):

        await message.answer(
            "❌ <b>Havola tanlangan platformaga "
            "mos emas.</b>",
            reply_markup=back_order()
        )

        return

    await state.update_data(
        link=link_value
    )

    await state.set_state(
        OrderState.confirm
    )

    await message.answer(
        "🧾 <b>BUYURTMANI TASDIQLASH</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🌐 Platforma: "
        f"<b>{PLATFORMS[platform]['title']}</b>\n\n"
        f"⚡ Xizmat:\n"
        f"<b>{data['service_name']}</b>\n\n"
        f"🔢 Miqdor: "
        f"<b>{data['quantity']:,}</b>\n\n"
        f"💰 Narx: "
        f"<b>{data['price']:,.2f} so‘m</b>\n\n"
        f"🔗 Havola:\n"
        f"<code>{link_value}</code>\n\n"
        "👇 Hammasi to‘g‘ri bo‘lsa tasdiqlang:",
        reply_markup=confirm_order_keyboard()
    )


# =========================================================
# CONFIRM ORDER
# =========================================================

@dp.callback_query(
    OrderState.confirm,
    F.data == "order_confirm"
)
async def confirm_order(
    callback: CallbackQuery,
    state: FSMContext
):

    data = await state.get_data()

    user_id = callback.from_user.id
    price = float(data["price"])

    balance = get_balance(user_id)

    if balance < price:

        await callback.message.edit_text(
            "❌ <b>Balans yetarli emas.</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 Buyurtma narxi: "
            f"<b>{price:,.2f} so‘m</b>\n"
            f"💳 Sizning balansingiz: "
            f"<b>{balance:,.2f} so‘m</b>\n\n"
            "💳 Hisobni to‘ldirish uchun "
            "pastdagi tugmadan foydalaning.",
            reply_markup=platform_keyboard()
        )

        await state.clear()
        await callback.answer()

        return

    await callback.message.edit_text(
        "⏳ <b>BUYURTMA YUBORILMOQDA...</b>"
    )

    try:

        response = await api_add_order(
            service=data["service_id"],
            link=data["link"],
            quantity=data["quantity"]
        )

        order_id = None

        if isinstance(
            response,
            dict
        ):
            order_id = response.get("order")

        if not order_id:

            error = (
                response.get("error")
                if isinstance(response, dict)
                else "Noma'lum API xatosi"
            )

            await callback.message.edit_text(
                "❌ <b>Buyurtma yaratilmadi.</b>\n\n"
                f"📛 {error}",
                reply_markup=platform_keyboard()
            )

            await state.clear()
            await callback.answer()

            return

        new_balance = charge_balance(
            user_id,
            price
        )

        if new_balance is False:

            await callback.message.edit_text(
                "❌ Balans bilan bog‘liq xatolik.",
                reply_markup=platform_keyboard()
            )

            await state.clear()
            await callback.answer()

            return

        save_order(
            user_id=user_id,
            api_order_id=order_id,
            platform=data["platform"],
            service_id=data["service_id"],
            service_name=data["service_name"],
            quantity=data["quantity"],
            price=price,
            link=data["link"]
        )

        await callback.message.edit_text(
            "🎉 <b>BUYURTMA QABUL QILINDI!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🆔 Buyurtma ID: "
            f"<code>{order_id}</code>\n"
            f"🌐 Platforma: "
            f"<b>{PLATFORMS[data['platform']]['title']}</b>\n"
            f"🔢 Miqdor: "
            f"<b>{data['quantity']:,}</b>\n"
            f"💰 To‘lov: "
            f"<b>{price:,.2f} so‘m</b>\n"
            f"💳 Qolgan balans: "
            f"<b>{new_balance:,.2f} so‘m</b>\n\n"
            "⏳ Buyurtma bajarilishi boshlanadi.",
            reply_markup=platform_keyboard()
        )

    except Exception as error:

        logger.exception(error)

        await callback.message.edit_text(
            "❌ <b>Server/API xatosi.</b>\n\n"
            "Buyurtma yuborilmadi.",
            reply_markup=platform_keyboard()
        )

    await state.clear()
    await callback.answer()


# =========================================================
# ORDER CANCEL / BACK
# =========================================================

@dp.callback_query(
    F.data == "order_cancel"
)
async def order_cancel(
    callback: CallbackQuery,
    state: FSMContext
):

    await state.clear()

    await callback.message.edit_text(
        "❌ <b>Buyurtma bekor qilindi.</b>\n\n"
        "Asosiy menyuga qaytdingiz."
    )

    await callback.answer()


@dp.callback_query(
    F.data == "order_back_main"
)
async def order_back_main(
    callback: CallbackQuery,
    state: FSMContext
):

    await state.clear()

    await callback.message.delete()

    await callback.answer()


@dp.callback_query(
    F.data == "order_back_platform"
)
async def order_back_platform(
    callback: CallbackQuery,
    state: FSMContext
):

    await state.set_state(
        OrderState.platform
    )

    await callback.message.edit_text(
        "🛒 <b>BUYURTMA BERISH</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🌐 Platformani tanlang:",
        reply_markup=platform_keyboard()
    )

    await callback.answer()


@dp.callback_query(
    F.data == "order_back_link"
)
async def order_back_link(
    callback: CallbackQuery,
    state: FSMContext
):

    await state.set_state(
        OrderState.link
    )

    await callback.message.edit_text(
        "🔗 <b>HAVOLANI KIRITING</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📎 Buyurtma havolasini yuboring:",
        reply_markup=back_order()
    )

    await callback.answer()


# =========================================================
# BALANCE — USER
# =========================================================

@dp.message(
    F.text == "💳 Hisobni to‘ldirish"
)
async def user_deposit(
    message: Message
):

    balance = get_balance(
        message.from_user.id
    )

    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="👨‍💻 Admin bilan bog‘lanish",
            url=f"https://t.me/{ADMIN_USERNAME}"
        )
    )

    await message.answer(
        "💳 <b>HISOBNI TO‘LDIRISH</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Joriy balans: "
        f"<b>{balance:,.2f} so‘m</b>\n\n"
        "Botda balans faqat admin orqali "
        "to‘ldiriladi.\n\n"
        "💬 To‘lovni admin bilan kelishib oling "
        "va to‘lovdan so‘ng admin balansingizni "
        "bot orqali to‘ldiradi.",
        reply_markup=builder.as_markup()
    )


# =========================================================
# PROFILE
# =========================================================

@dp.message(
    F.text == "👤 Shaxsiy kabinet"
)
async def profile(
    message: Message
):

    user = message.from_user

    balance = get_balance(
        user.id
    )

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM orders WHERE user_id=?",
        (user.id,)
    )

    orders = cur.fetchone()[0]

    conn.close()

    username = (
        f"@{user.username}"
        if user.username
        else "yo‘q"
    )

    await message.answer(
        "👤 <b>SHAXSIY KABINET</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"👤 Username: <b>{username}</b>\n"
        f"📛 Ism: <b>{user.first_name}</b>\n\n"
        f"💰 Balans: "
        f"<b>{balance:,.2f} so‘m</b>\n"
        f"📦 Buyurtmalar: <b>{orders}</b>",
        reply_markup=main_keyboard()
    )


# =========================================================
# HELP
# =========================================================

@dp.message(
    F.text == "🆘 Yordam"
)
async def help_user(
    message: Message
):

    await message.answer(
        "🆘 <b>YORDAM</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🛒 <b>Buyurtma berish</b>\n"
        "Platforma → xizmat → miqdor → "
        "havola → tasdiqlash.\n\n"
        "💳 <b>Hisobni to‘ldirish</b>\n"
        "Admin bilan bog‘laning.\n\n"
        "👤 <b>Shaxsiy kabinet</b>\n"
        "Balans va buyurtmalarni ko‘ring.\n\n"
        f"👨‍💻 Admin: @{ADMIN_USERNAME}",
        reply_markup=main_keyboard()
    )


# =========================================================
# ADMIN COMMAND
# =========================================================

@dp.message(Command("admin"))
async def admin_command(
    message: Message
):

    if not is_admin(
        message.from_user
    ):

        await message.answer(
            "⛔ <b>Ruxsat yo‘q.</b>"
        )

        return

    await show_admin_panel(
        message
    )


async def show_admin_panel(
    target
):

    users, orders, revenue, balances = statistics()

    text = (
        "👑 <b>BEST1SMM ADMIN</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📊 <b>UMUMIY STATISTIKA</b>\n\n"
        f"👥 Foydalanuvchilar: "
        f"<b>{users}</b>\n"
        f"📦 Buyurtmalar: "
        f"<b>{orders}</b>\n"
        f"💰 Buyurtma summasi: "
        f"<b>{revenue:,.2f} so‘m</b>\n"
        f"💳 User balanslari: "
        f"<b>{balances:,.2f} so‘m</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🛠 <b>BOSHQARUV PANELI</b>"
    )

    if isinstance(target, Message):

        await target.answer(
            text,
            reply_markup=admin_keyboard()
        )

    else:

        await target.message.edit_text(
            text,
            reply_markup=admin_keyboard()
        )


# =========================================================
# ADMIN PANEL
# =========================================================

@dp.callback_query(
    F.data == "adm:panel"
)
async def adm_panel(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user
    ):
        await callback.answer(
            "⛔ Ruxsat yo‘q!",
            show_alert=True
        )
        return

    await show_admin_panel(
        callback
    )

    await callback.answer()


# =========================================================
# ADMIN STATS
# =========================================================

@dp.callback_query(
    F.data == "adm:stats"
)
async def adm_stats(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user
    ):
        return

    users, orders, revenue, balances = statistics()

    await callback.message.edit_text(
        "📊 <b>STATISTIKA</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Foydalanuvchilar: <b>{users}</b>\n"
        f"📦 Buyurtmalar: <b>{orders}</b>\n"
        f"💰 Buyurtmalar summasi: "
        f"<b>{revenue:,.2f} so‘m</b>\n"
        f"💳 User balanslari: "
        f"<b>{balances:,.2f} so‘m</b>",
        reply_markup=admin_back()
    )

    await callback.answer()


# =========================================================
# ADMIN BALANCE MENU
# =========================================================

@dp.callback_query(
    F.data == "adm:balance"
)
async def adm_balance(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user
    ):
        return

    await callback.message.edit_text(
        "💳 <b>BALANS BOSHQARUVI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Kerakli amalni tanlang:",
        reply_markup=balance_admin_keyboard()
    )

    await callback.answer()


# =========================================================
# ADD / REMOVE BALANCE
# =========================================================

async def start_balance_change(
    callback,
    state,
    operation
):

    if not is_admin(
        callback.from_user
    ):
        return

    await state.update_data(
        operation=operation
    )

    await state.set_state(
        AdminBalanceState.user_id
    )

    title = (
        "➕ <b>BALANS QO‘SHISH</b>"
        if operation == "add"
        else
        "➖ <b>BALANSDAN AYIRISH</b>"
    )

    await callback.message.edit_text(
        f"{title}\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "👤 Foydalanuvchining Telegram ID'sini "
        "kiriting:\n\n"
        "Masalan:\n"
        "<code>123456789</code>",
        reply_markup=admin_back()
    )

    await callback.answer()


@dp.callback_query(
    F.data == "adm:add_balance"
)
async def adm_add_balance(
    callback: CallbackQuery,
    state: FSMContext
):

    await start_balance_change(
        callback,
        state,
        "add"
    )


@dp.callback_query(
    F.data == "adm:remove_balance"
)
async def adm_remove_balance(
    callback: CallbackQuery,
    state: FSMContext
):

    await start_balance_change(
        callback,
        state,
        "remove"
    )


# =========================================================
# ADMIN USER ID
# =========================================================

@dp.message(
    AdminBalanceState.user_id
)
async def admin_user_id(
    message: Message,
    state: FSMContext
):

    if not is_admin(
        message.from_user
    ):
        return

    if not message.text.isdigit():

        await message.answer(
            "❌ Faqat Telegram ID son bo‘lishi kerak."
        )

        return

    user_id = int(
        message.text
    )

    balance = get_balance(
        user_id
    )

    await state.update_data(
        target_user_id=user_id,
        old_balance=balance
    )

    await state.set_state(
        AdminBalanceState.amount
    )

    data = await state.get_data()

    operation_text = (
        "qo‘shiladigan"
        if data["operation"] == "add"
        else "ayiriladigan"
    )

    await message.answer(
        "💰 <b>SUMMA</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 User ID: <code>{user_id}</code>\n"
        f"💳 Hozirgi balans: "
        f"<b>{balance:,.2f} so‘m</b>\n\n"
        f"💵 {operation_text} summani kiriting:\n\n"
        "Masalan: <code>20000</code>"
    )


# =========================================================
# ADMIN AMOUNT
# =========================================================

@dp.message(
    AdminBalanceState.amount
)
async def admin_amount(
    message: Message,
    state: FSMContext
):

    if not is_admin(
        message.from_user
    ):
        return

    amount = valid_number(
        message.text
    )

    if amount is None:

        await message.answer(
            "❌ To‘g‘ri musbat summa kiriting."
        )

        return

    await state.update_data(
        amount=amount
    )

    await state.set_state(
        AdminBalanceState.confirm
    )

    data = await state.get_data()

    operation = data["operation"]

    if operation == "add":

        new_balance = (
            data["old_balance"]
            + amount
        )

        action = "➕ Qo‘shiladi"

    else:

        new_balance = (
            data["old_balance"]
            - amount
        )

        action = "➖ Ayiriladi"

    if new_balance < 0:

        await message.answer(
            "❌ Bu summa ayirilsa balans "
            "0 dan pastga tushadi."
        )

        await state.clear()

        return

    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="✅ TASDIQLASH",
            callback_data="adm:balance_confirm"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="❌ Bekor qilish",
            callback_data="adm:balance_cancel"
        )
    )

    await message.answer(
        "🧾 <b>OPERATSIYANI TASDIQLASH</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 User ID: "
        f"<code>{data['target_user_id']}</code>\n"
        f"{action}: "
        f"<b>{amount:,.2f} so‘m</b>\n"
        f"💳 Eski balans: "
        f"<b>{data['old_balance']:,.2f}</b>\n"
        f"💰 Yangi balans: "
        f"<b>{new_balance:,.2f}</b>\n\n"
        "Tasdiqlaysizmi?",
        reply_markup=builder.as_markup()
    )


# =========================================================
# ADMIN BALANCE CONFIRM
# =========================================================

@dp.callback_query(
    F.data == "adm:balance_confirm"
)
async def adm_balance_confirm(
    callback: CallbackQuery,
    state: FSMContext
):

    if not is_admin(
        callback.from_user
    ):
        return

    data = await state.get_data()

    result = change_balance(
        user_id=data["target_user_id"],
        amount=data["amount"],
        operation=data["operation"],
        admin_username=ADMIN_USERNAME
    )

    if result is None:

        await callback.message.edit_text(
            "❌ <b>Foydalanuvchi topilmadi.</b>",
            reply_markup=admin_back()
        )

    elif result is False:

        await callback.message.edit_text(
            "❌ <b>Balansni ayirish mumkin emas.</b>",
            reply_markup=admin_back()
        )

    else:

        symbol = (
            "➕"
            if data["operation"] == "add"
            else "➖"
        )

        await callback.message.edit_text(
            "✅ <b>BALANS O‘ZGARTIRILDI</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 User ID: "
            f"<code>{data['target_user_id']}</code>\n"
            f"{symbol} Summa: "
            f"<b>{data['amount']:,.2f} so‘m</b>\n"
            f"💳 Yangi balans: "
            f"<b>{result:,.2f} so‘m</b>\n\n"
            f"👑 Admin: @{ADMIN_USERNAME}",
            reply_markup=admin_back()
        )

        # Userga xabar
        try:

            await bot.send_message(
                data["target_user_id"],
                (
                    "💳 <b>BALANS YANGILANDI</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"{symbol} "
                    f"<b>{data['amount']:,.2f} so‘m</b>\n"
                    f"💰 Yangi balans: "
                    f"<b>{result:,.2f} so‘m</b>"
                )
            )

        except Exception:
            pass

    await state.clear()
    await callback.answer()


@dp.callback_query(
    F.data == "adm:balance_cancel"
)
async def adm_balance_cancel(
    callback: CallbackQuery,
    state: FSMContext
):

    await state.clear()

    await callback.message.edit_text(
        "❌ <b>Operatsiya bekor qilindi.</b>",
        reply_markup=admin_back()
    )

    await callback.answer()


# =========================================================
# ADMIN API
# =========================================================

@dp.callback_query(
    F.data == "adm:api"
)
async def adm_api(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user
    ):
        return

    await callback.message.edit_text(
        "🔌 <b>API TEKSHIRILMOQDA...</b>"
    )

    try:

        services = await api_services()

        balance = await api_balance()

        if isinstance(
            services,
            list
        ):

            service_count = len(
                services
            )

        else:

            service_count = 0

        if isinstance(
            balance,
            dict
        ):

            api_balance_value = balance.get(
                "balance",
                "Noma'lum"
            )

        else:

            api_balance_value = "Noma'lum"

        await callback.message.edit_text(
            "🟢 <b>SEENSMS API ONLINE</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"⚡ Xizmatlar: "
            f"<b>{service_count}</b>\n"
            f"💰 API balans: "
            f"<b>{api_balance_value}</b>",
            reply_markup=admin_back()
        )

    except Exception as error:

        await callback.message.edit_text(
            "🔴 <b>SEENSMS API OFFLINE</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<code>{str(error)[:500]}</code>",
            reply_markup=admin_back()
        )

    await callback.answer()


# =========================================================
# ADMIN USERS
# =========================================================

@dp.callback_query(
    F.data == "adm:users"
)
async def adm_users(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user
    ):
        return

    users, orders, revenue, balances = statistics()

    await callback.message.edit_text(
        "👥 <b>FOYDALANUVCHILAR</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Jami: <b>{users}</b>\n"
        f"📦 Buyurtmalar: <b>{orders}</b>\n"
        f"💳 User balanslari: "
        f"<b>{balances:,.2f} so‘m</b>",
        reply_markup=admin_back()
    )

    await callback.answer()


# =========================================================
# ADMIN ORDERS
# =========================================================

@dp.callback_query(
    F.data == "adm:orders"
)
async def adm_orders(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user
    ):
        return

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            api_order_id,
            user_id,
            platform,
            quantity,
            price,
            status,
            created_at
        FROM orders
        ORDER BY id DESC
        LIMIT 10
    """)

    rows = cur.fetchall()

    conn.close()

    if not rows:

        text = (
            "📦 <b>BUYURTMALAR</b>\n\n"
            "Hozircha buyurtmalar yo‘q."
        )

    else:

        text = (
            "📦 <b>SO‘NGGI BUYURTMALAR</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        for row in rows:

            text += (
                f"🆔 <code>{row[0]}</code>\n"
                f"👤 <code>{row[1]}</code>\n"
                f"🌐 {row[2]}\n"
                f"🔢 {row[3]:,}\n"
                f"💰 {row[4]:,.2f}\n"
                f"📌 {row[5]}\n"
                f"🕐 {row[6]}\n"
                "──────────────\n"
            )

    await callback.message.edit_text(
        text[:4000],
        reply_markup=admin_back()
    )

    await callback.answer()


# =========================================================
# BALANCE LOGS
# =========================================================

@dp.callback_query(
    F.data == "adm:logs"
)
async def adm_logs(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user
    ):
        return

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            user_id,
            amount,
            operation,
            old_balance,
            new_balance,
            created_at
        FROM balance_logs
        ORDER BY id DESC
        LIMIT 10
    """)

    rows = cur.fetchall()

    conn.close()

    if not rows:

        text = (
            "📜 <b>BALANS TARIXI</b>\n\n"
            "Hozircha operatsiyalar yo‘q."
        )

    else:

        text = (
            "📜 <b>BALANS TARIXI</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        for row in rows:

            symbol = (
                "➕"
                if row[2] == "add"
                else "➖"
            )

            text += (
                f"👤 <code>{row[0]}</code>\n"
                f"{symbol} {row[1]:,.2f} so‘m\n"
                f"💳 {row[3]:,.2f} → "
                f"{row[4]:,.2f}\n"
                f"🕐 {row[5]}\n"
                "──────────────\n"
            )

    await callback.message.edit_text(
        text[:4000],
        reply_markup=admin_back()
    )

    await callback.answer()


# =========================================================
# ADMIN BROADCAST
# =========================================================

@dp.callback_query(
    F.data == "adm:broadcast"
)
async def adm_broadcast(
    callback: CallbackQuery,
    state: FSMContext
):

    if not is_admin(
        callback.from_user
    ):
        return

    await state.set_state(
        AdminBroadcastState.message
    )

    await callback.message.edit_text(
        "📢 <b>REKLAMA YUBORISH</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Yubormoqchi bo‘lgan xabaringizni "
        "keyingi xabarda yuboring.\n\n"
        "⚠️ Xabar bazadagi foydalanuvchilarga "
        "yuboriladi.",
        reply_markup=admin_back()
    )

    await callback.answer()


@dp.message(
    AdminBroadcastState.message
)
async def broadcast(
    message: Message,
    state: FSMContext
):

    if not is_admin(
        message.from_user
    ):
        return

    users = get_users()

    sent = 0
    failed = 0

    await message.answer(
        f"📢 <b>Yuborish boshlandi...</b>\n\n"
        f"👥 Jami: <b>{len(users)}</b>"
    )

    for user_id in users:

        try:

            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )

            sent += 1

        except Exception:

            failed += 1

        await asyncio.sleep(0.05)

    await state.clear()

    await message.answer(
        "📢 <b>YAKUNLANDI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"✅ Yuborildi: <b>{sent}</b>\n"
        f"❌ Xato: <b>{failed}</b>",
        reply_markup=admin_keyboard()
    )


# =========================================================
# ADMIN HOME
# =========================================================

@dp.callback_query(
    F.data == "adm:home"
)
async def adm_home(
    callback: CallbackQuery
):

    await callback.message.delete()

    await callback.message.answer(
        "🏠 <b>BEST1SMM</b>\n\n"
        "Asosiy menyu:",
        reply_markup=main_keyboard()
    )

    await callback.answer()


# =========================================================
# RUN
# =========================================================

async def main():

    init_db()

    if not SEENSMS_API_KEY:
        logger.warning(
            "SEENSMS_API_KEY Render Environment "
            "Variables'da topilmadi."
        )

    await bot.delete_webhook(
        drop_pending_updates=True
    )

    logger.info(
        "🚀 BEST1SMM ishga tushdi"
    )

    await dp.start_polling(
        bot
    )


if __name__ == "__main__":
    asyncio.run(main())
