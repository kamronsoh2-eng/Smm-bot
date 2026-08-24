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
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
SEENSMS_API_KEY = os.getenv("SEENSMS_API_KEY")

SEENSMS_API_URL = os.getenv(
    "SEENSMS_API_URL",
    "https://seensms.uz/api/v1"
)

ADMIN_USERNAME = os.getenv(
    "ADMIN_USERNAME",
    "rxk_17"
).replace("@", "")

ADMIN_ID = os.getenv("ADMIN_ID")

DB_NAME = "best1smm.db"


if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi!")

if not ADMIN_ID:
    raise RuntimeError(
        "ADMIN_ID Render Environment Variables'da yo'q!"
    )

try:
    ADMIN_ID = int(ADMIN_ID)
except ValueError:
    raise RuntimeError(
        "ADMIN_ID faqat raqam bo'lishi kerak!"
    )


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("BEST1SMM")


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

def get_db():
    return sqlite3.connect(DB_NAME)


def init_db():

    conn = get_db()
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

    conn = get_db()
    cur = conn.cursor()

    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    cur.execute("""
        INSERT INTO users
        (
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
        (user.username or "").replace("@", ""),
        user.first_name or "",
        now,
        now
    ))

    conn.commit()
    conn.close()


def get_balance(user_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT balance
        FROM users
        WHERE user_id=?
        """,
        (user_id,)
    )

    row = cur.fetchone()

    conn.close()

    return float(row[0]) if row else 0.0


def find_user_by_username(username):

    username = (
        username
        .strip()
        .replace("@", "")
        .lower()
    )

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            user_id,
            username,
            first_name,
            balance
        FROM users
        WHERE LOWER(username)=?
    """, (username,))

    row = cur.fetchone()

    conn.close()

    return row


def change_balance_by_username(
    username,
    amount,
    operation,
    admin_username
):

    row = find_user_by_username(username)

    if not row:
        return {
            "success": False,
            "reason": "not_found"
        }

    user_id = row[0]
    old_balance = float(row[3])

    if operation == "add":

        new_balance = (
            old_balance + amount
        )

    else:

        new_balance = (
            old_balance - amount
        )

        if new_balance < 0:
            return {
                "success": False,
                "reason": "negative"
            }

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET balance=?,
            updated_at=?
        WHERE user_id=?
    """, (
        new_balance,
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        user_id
    ))

    cur.execute("""
        INSERT INTO balance_logs
        (
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

    return {
        "success": True,
        "user_id": user_id,
        "username": row[1],
        "first_name": row[2],
        "old_balance": old_balance,
        "new_balance": new_balance
    }


def charge_balance(user_id, amount):

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT balance
        FROM users
        WHERE user_id=?
        """,
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
        SET balance=?,
            updated_at=?
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

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO orders
        (
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


def get_statistics():

    conn = get_db()
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
        """
        SELECT COALESCE(SUM(price), 0)
        FROM orders
        """
    )
    revenue = float(cur.fetchone()[0])

    cur.execute(
        """
        SELECT COALESCE(SUM(balance), 0)
        FROM users
        """
    )
    balances = float(cur.fetchone()[0])

    conn.close()

    return users, orders, revenue, balances


def get_all_users():

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT user_id FROM users"
    )

    result = [
        row[0]
        for row in cur.fetchall()
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
    username = State()
    amount = State()
    confirm = State()


class BroadcastState(StatesGroup):
    message = State()


# =========================================================
# PLATFORMS
# =========================================================

PLATFORMS = {

    "youtube": {
        "title": "▶️ YouTube",
        "keywords": [
            "youtube",
            "youtube views",
            "youtube likes",
            "youtube subscribers"
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
            "telegram views",
            "telegram members",
            "telegram reactions"
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
            "instagram followers",
            "instagram likes",
            "instagram views"
        ],
        "domains": [
            "instagram.com"
        ]
    },

    "tiktok": {
        "title": "🎵 TikTok",
        "keywords": [
            "tiktok",
            "tiktok views",
            "tiktok likes",
            "tiktok followers"
        ],
        "domains": [
            "tiktok.com"
        ]
    }
}


# =========================================================
# MAIN MENU
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
# ORDER KEYBOARDS
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
            text="❌ Bekor qilish",
            callback_data="order_cancel"
        )
    )

    return builder.as_markup()


def order_back_keyboard():

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


def confirm_keyboard():

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
            text="🔌 SeenSMS API",
            callback_data="adm:api"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="📢 Reklama",
            callback_data="adm:broadcast"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="🔄 Yangilash",
            callback_data="adm:panel"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="🏠 Asosiy menyu",
            callback_data="adm:home"
        )
    )

    return builder.as_markup()


def admin_back_keyboard():

    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="🔙 Admin panel",
            callback_data="adm:panel"
        )
    )

    return builder.as_markup()


def balance_keyboard():

    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="➕ Balans qo‘shish",
            callback_data="adm:add"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="➖ Balans ayirish",
            callback_data="adm:remove"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="🔎 Username balansini tekshirish",
            callback_data="adm:check"
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
# ADMIN CHECK
# =========================================================

def is_admin(user_id):

    return user_id == ADMIN_ID


# =========================================================
# API
# =========================================================

async def api_request(data):

    if not SEENSMS_API_KEY:
        raise RuntimeError(
            "SEENSMS_API_KEY topilmadi!"
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


async def get_services():

    return await api_request({
        "action": "services"
    })


async def get_api_balance():

    return await api_request({
        "action": "balance"
    })


async def add_api_order(
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
        "⚡ YouTube\n"
        "✈️ Telegram\n"
        "📸 Instagram\n"
        "🎵 TikTok\n\n"
        "👇 <b>Bo‘limni tanlang:</b>",
        reply_markup=main_keyboard()
    )


# =========================================================
# ORDER
# =========================================================

@dp.message(
    F.text == "🛒 Buyurtma berish"
)
async def order_start(
    message: Message,
    state: FSMContext
):

    await state.clear()

    await state.set_state(
        OrderState.platform
    )

    await message.answer(
        "🛒 <b>BUYURTMA BERISH</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🌐 Platformani tanlang:",
        reply_markup=platform_keyboard()
    )


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

        services = await get_services()

        if not isinstance(
            services,
            list
        ):

            await callback.message.edit_text(
                "❌ API xizmatlar ro‘yxatini "
                "qaytarmadi.",
                reply_markup=platform_keyboard()
            )

            await callback.answer()
            return

        filtered = []

        for service in services:

            text = (
                str(
                    service.get(
                        "name",
                        ""
                    )
                )
                + " "
                + str(
                    service.get(
                        "category",
                        ""
                    )
                )
            ).lower()

            if any(
                keyword.lower() in text
                for keyword in
                PLATFORMS[platform]["keywords"]
            ):
                filtered.append(
                    service
                )

        if not filtered:

            await callback.message.edit_text(
                "😔 <b>Xizmat topilmadi.</b>\n\n"
                "Boshqa platformani tanlang.",
                reply_markup=platform_keyboard()
            )

            await callback.answer()
            return

        await state.update_data(
            services=filtered
        )

        builder = InlineKeyboardBuilder()

        for service in filtered:

            sid = str(
                service.get(
                    "service"
                )
            )

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
            "❌ <b>SeenSMS API xatosi.</b>\n\n"
            "API sozlamalarini tekshiring.",
            reply_markup=platform_keyboard()
        )

    await callback.answer()


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
            service.get(
                "service"
            )
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
        rate=selected.get(
            "rate",
            0
        ),
        minimum=selected.get(
            "min",
            0
        ),
        maximum=selected.get(
            "max",
            0
        )
    )

    await state.set_state(
        OrderState.quantity
    )

    await callback.message.edit_text(
        "🔢 <b>MIQDORNI KIRITING</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⚡ <b>{selected.get('name')}</b>\n\n"
        f"📊 Minimum: "
        f"<b>{selected.get('min')}</b>\n"
        f"📈 Maximum: "
        f"<b>{selected.get('max')}</b>\n\n"
        "Nechta kerakligini yozing:",
        reply_markup=order_back_keyboard()
    )

    await callback.answer()


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
            "❌ <b>Faqat son kiriting.</b>\n\n"
            "Masalan: <code>1000</code>",
            reply_markup=order_back_keyboard()
        )

        return

    amount = int(text)

    data = await state.get_data()

    minimum = int(
        float(
            data.get(
                "minimum",
                0
            )
        )
    )

    maximum = int(
        float(
            data.get(
                "maximum",
                0
            )
        )
    )

    if minimum and amount < minimum:

        await message.answer(
            f"❌ Minimum: <b>{minimum}</b>",
            reply_markup=order_back_keyboard()
        )

        return

    if maximum and amount > maximum:

        await message.answer(
            f"❌ Maximum: <b>{maximum}</b>",
            reply_markup=order_back_keyboard()
        )

        return

    try:

        price = (
            float(data["rate"])
            * amount
            / 1000
        )

    except Exception:

        await message.answer(
            "❌ Xizmat narxini hisoblab bo‘lmadi."
        )

        return

    await state.update_data(
        quantity=amount,
        price=price
    )

    await state.set_state(
        OrderState.link
    )

    await message.answer(
        "🔗 <b>HAVOLANI KIRITING</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔢 Miqdor: <b>{amount:,}</b>\n"
        f"💰 Narx: <b>{price:,.2f} so‘m</b>\n\n"
        "📎 Havolani yuboring:",
        reply_markup=order_back_keyboard()
    )


@dp.message(
    OrderState.link
)
async def order_link(
    message: Message,
    state: FSMContext
):

    if not message.text:
        return

    link = message.text.strip()

    if not (
        link.startswith("https://")
        or link.startswith("http://")
    ):

        await message.answer(
            "❌ <b>Havola noto‘g‘ri.</b>\n\n"
            "https:// bilan boshlanadigan "
            "havola yuboring.",
            reply_markup=order_back_keyboard()
        )

        return

    data = await state.get_data()

    domains = PLATFORMS[
        data["platform"]
    ]["domains"]

    if not any(
        domain in link.lower()
        for domain in domains
    ):

        await message.answer(
            "❌ Havola tanlangan platformaga "
            "mos emas.",
            reply_markup=order_back_keyboard()
        )

        return

    await state.update_data(
        link=link
    )

    await state.set_state(
        OrderState.confirm
    )

    await message.answer(
        "🧾 <b>BUYURTMANI TASDIQLASH</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🌐 Platforma: "
        f"<b>{PLATFORMS[data['platform']]['title']}</b>\n\n"
        f"⚡ Xizmat:\n"
        f"<b>{data['service_name']}</b>\n\n"
        f"🔢 Miqdor: "
        f"<b>{data['quantity']:,}</b>\n\n"
        f"💰 Narx: "
        f"<b>{data['price']:,.2f} so‘m</b>\n\n"
        f"🔗 Havola:\n"
        f"<code>{link}</code>\n\n"
        "Tasdiqlaysizmi?",
        reply_markup=confirm_keyboard()
    )


@dp.callback_query(
    OrderState.confirm,
    F.data == "order_confirm"
)
async def order_confirm(
    callback: CallbackQuery,
    state: FSMContext
):

    data = await state.get_data()

    price = float(
        data["price"]
    )

    balance = get_balance(
        callback.from_user.id
    )

    if balance < price:

        await callback.message.edit_text(
            "❌ <b>BALANS YETARLI EMAS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 Kerak: "
            f"<b>{price:,.2f} so‘m</b>\n"
            f"💳 Balans: "
            f"<b>{balance:,.2f} so‘m</b>\n\n"
            "Hisobni admin orqali to‘ldiring.",
            reply_markup=platform_keyboard()
        )

        await state.clear()
        await callback.answer()
        return

    await callback.message.edit_text(
        "⏳ <b>BUYURTMA YUBORILMOQDA...</b>"
    )

    try:

        result = await add_api_order(
            service=data["service_id"],
            link=data["link"],
            quantity=data["quantity"]
        )

        if not isinstance(
            result,
            dict
        ):

            raise RuntimeError(
                "API javobi noto‘g‘ri."
            )

        order_id = result.get(
            "order"
        )

        if not order_id:

            error = result.get(
                "error",
                "Noma'lum xato"
            )

            await callback.message.edit_text(
                f"❌ <b>Buyurtma yaratilmadi.</b>\n\n"
                f"📛 {error}",
                reply_markup=platform_keyboard()
            )

            await state.clear()
            await callback.answer()
            return

        new_balance = charge_balance(
            callback.from_user.id,
            price
        )

        if new_balance is False:

            await callback.message.edit_text(
                "❌ Balansni yechishda xatolik.",
                reply_markup=platform_keyboard()
            )

            await state.clear()
            await callback.answer()
            return

        save_order(
            callback.from_user.id,
            order_id,
            data["platform"],
            data["service_id"],
            data["service_name"],
            data["quantity"],
            price,
            data["link"]
        )

        await callback.message.edit_text(
            "🎉 <b>BUYURTMA QABUL QILINDI!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🆔 ID: <code>{order_id}</code>\n"
            f"🌐 {PLATFORMS[data['platform']]['title']}\n"
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
            "❌ <b>SeenSMS API xatosi.</b>\n\n"
            "Buyurtma yuborilmadi.",
            reply_markup=platform_keyboard()
        )

    await state.clear()
    await callback.answer()


# =========================================================
# ORDER BACK
# =========================================================

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
        "🔗 <b>HAVOLA</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📎 Havolani yuboring:",
        reply_markup=order_back_keyboard()
    )

    await callback.answer()


@dp.callback_query(
    F.data == "order_cancel"
)
async def order_cancel(
    callback: CallbackQuery,
    state: FSMContext
):

    await state.clear()

    await callback.message.edit_text(
        "❌ <b>Buyurtma bekor qilindi.</b>"
    )

    await callback.answer()


# =========================================================
# USER BALANCE
# =========================================================

@dp.message(
    F.text == "💳 Hisobni to‘ldirish"
)
async def deposit(
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
        "Balansni faqat admin orqali "
        "to‘ldirish mumkin.\n\n"
        f"👑 Admin: @{ADMIN_USERNAME}",
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

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT COUNT(*)
        FROM orders
        WHERE user_id=?
        """,
        (user.id,)
    )

    orders = cur.fetchone()[0]

    conn.close()

    username = (
        f"@{user.username}"
        if user.username
        else "username yo‘q"
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
async def help_message(
    message: Message
):

    await message.answer(
        "🆘 <b>YORDAM</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🛒 Buyurtma berish — xizmat tanlash "
        "va buyurtma berish.\n\n"
        "💳 Hisobni to‘ldirish — admin bilan "
        "bog‘lanish.\n\n"
        "👤 Shaxsiy kabinet — balans va "
        "buyurtmalar.\n\n"
        f"👑 Admin: @{ADMIN_USERNAME}",
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
        message.from_user.id
    ):

        await message.answer(
            "⛔ <b>Siz admin emassiz.</b>"
        )

        return

    await send_admin_panel(
        message
    )


async def send_admin_panel(
    target
):

    users, orders, revenue, balances = (
        get_statistics()
    )

    text = (
        "👑 <b>BEST1SMM ADMIN PANEL</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Foydalanuvchilar: <b>{users}</b>\n"
        f"📦 Buyurtmalar: <b>{orders}</b>\n"
        f"💰 Buyurtmalar: "
        f"<b>{revenue:,.2f} so‘m</b>\n"
        f"💳 User balanslari: "
        f"<b>{balances:,.2f} so‘m</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👇 <b>Boshqaruv bo‘limini tanlang:</b>"
    )

    if isinstance(
        target,
        Message
    ):

        await target.answer(
            text,
            reply_markup=admin_keyboard()
        )

    else:

        await target.message.edit_text(
            text,
            reply_markup=admin_keyboard()
        )


@dp.callback_query(
    F.data == "adm:panel"
)
async def admin_panel(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user.id
    ):
        await callback.answer(
            "⛔ Ruxsat yo‘q!",
            show_alert=True
        )
        return

    await send_admin_panel(
        callback
    )

    await callback.answer()


# =========================================================
# ADMIN BALANCE MENU
# =========================================================

@dp.callback_query(
    F.data == "adm:balance"
)
async def admin_balance(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user.id
    ):
        return

    await callback.message.edit_text(
        "💳 <b>BALANS BOSHQARUVI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "⚡ Foydalanuvchini <b>@username</b> "
        "orqali tanlang.",
        reply_markup=balance_keyboard()
    )

    await callback.answer()


async def start_balance(
    callback,
    state,
    operation
):

    if not is_admin(
        callback.from_user.id
    ):
        return

    await state.update_data(
        operation=operation
    )

    await state.set_state(
        AdminBalanceState.username
    )

    action = (
        "➕ BALANS QO‘SHISH"
        if operation == "add"
        else
        "➖ BALANS AYIRISH"
    )

    await callback.message.edit_text(
        f"👑 <b>{action}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "👤 Foydalanuvchining username'ini "
        "kiriting:\n\n"
        "Masalan:\n"
        "<code>@kamron123</code>\n\n"
        "⚠️ User botda avval /start bosgan "
        "bo‘lishi kerak.",
        reply_markup=admin_back_keyboard()
    )

    await callback.answer()


@dp.callback_query(
    F.data == "adm:add"
)
async def admin_add(
    callback: CallbackQuery,
    state: FSMContext
):

    await start_balance(
        callback,
        state,
        "add"
    )


@dp.callback_query(
    F.data == "adm:remove"
)
async def admin_remove(
    callback: CallbackQuery,
    state: FSMContext
):

    await start_balance(
        callback,
        state,
        "remove"
    )


# =========================================================
# ADMIN USERNAME
# =========================================================

@dp.message(
    AdminBalanceState.username
)
async def admin_username(
    message: Message,
    state: FSMContext
):

    if not is_admin(
        message.from_user.id
    ):
        return

    username = (
        message.text
        .strip()
        .replace("@", "")
    )

    if not username:

        await message.answer(
            "❌ Username kiriting."
        )

        return

    user = find_user_by_username(
        username
    )

    if not user:

        await message.answer(
            "❌ <b>Foydalanuvchi topilmadi.</b>\n\n"
            f"🔎 Qidirildi: <b>@{username}</b>\n\n"
            "U botga /start bosganini tekshiring."
        )

        return

    await state.update_data(
        target_username=username,
        target_user_id=user[0],
        target_name=user[2],
        old_balance=float(user[3])
    )

    await state.set_state(
        AdminBalanceState.amount
    )

    data = await state.get_data()

    action = (
        "qo‘shiladigan"
        if data["operation"] == "add"
        else "ayiriladigan"
    )

    await message.answer(
        "💰 <b>SUMMA</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 User: <b>@{username}</b>\n"
        f"📛 Ism: <b>{user[2]}</b>\n"
        f"💳 Hozirgi balans: "
        f"<b>{float(user[3]):,.2f} so‘m</b>\n\n"
        f"💵 {action} summani yozing:\n"
        "Masalan: <code>50000</code>"
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
        message.from_user.id
    ):
        return

    try:

        amount = float(
            message.text
            .replace(" ", "")
            .replace(",", ".")
        )

        if amount <= 0:
            raise ValueError

    except Exception:

        await message.answer(
            "❌ To‘g‘ri summa kiriting.\n\n"
            "Masalan: <code>50000</code>"
        )

        return

    data = await state.get_data()

    if data["operation"] == "add":

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
                "❌ Bu summani ayirib bo‘lmaydi.\n"
                "Balans manfiy bo‘lib qoladi."
            )

            return

    await state.update_data(
        amount=amount,
        new_balance=new_balance
    )

    await state.set_state(
        AdminBalanceState.confirm
    )

    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="✅ TASDIQLASH",
            callback_data="adm:confirm_balance"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="❌ BEKOR QILISH",
            callback_data="adm:cancel_balance"
        )
    )

    await message.answer(
        "🧾 <b>BALANS OPERATSIYASI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 User: "
        f"<b>@{data['target_username']}</b>\n"
        f"{action}: "
        f"<b>{amount:,.2f} so‘m</b>\n\n"
        f"💳 Eski balans: "
        f"<b>{data['old_balance']:,.2f}</b>\n"
        f"💰 Yangi balans: "
        f"<b>{new_balance:,.2f}</b>\n\n"
        "Tasdiqlaysizmi?",
        reply_markup=builder.as_markup()
    )


# =========================================================
# ADMIN CONFIRM
# =========================================================

@dp.callback_query(
    F.data == "adm:confirm_balance"
)
async def confirm_balance(
    callback: CallbackQuery,
    state: FSMContext
):

    if not is_admin(
        callback.from_user.id
    ):
        return

    data = await state.get_data()

    result = change_balance_by_username(
        username=data["target_username"],
        amount=data["amount"],
        operation=data["operation"],
        admin_username=ADMIN_USERNAME
    )

    if not result["success"]:

        if result["reason"] == "not_found":

            text = (
                "❌ Foydalanuvchi topilmadi."
            )

        else:

            text = (
                "❌ Balansni ayirib bo‘lmaydi."
            )

        await callback.message.edit_text(
            text,
            reply_markup=admin_back_keyboard()
        )

        await state.clear()
        await callback.answer()
        return

    symbol = (
        "➕"
        if data["operation"] == "add"
        else "➖"
    )

    await callback.message.edit_text(
        "✅ <b>BALANS MUVAFFAQIYATLI "
        "O‘ZGARTIRILDI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 User: "
        f"<b>@{result['username']}</b>\n"
        f"{symbol} Summa: "
        f"<b>{data['amount']:,.2f} so‘m</b>\n"
        f"💳 Yangi balans: "
        f"<b>{result['new_balance']:,.2f} so‘m</b>\n\n"
        f"👑 Admin: @{ADMIN_USERNAME}",
        reply_markup=admin_back_keyboard()
    )

    try:

        await bot.send_message(
            result["user_id"],
            "💳 <b>BALANSINGIZ YANGILANDI</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{symbol} Summa: "
            f"<b>{data['amount']:,.2f} so‘m</b>\n"
            f"💰 Yangi balans: "
            f"<b>{result['new_balance']:,.2f} so‘m</b>"
        )

    except Exception as error:

        logger.warning(
            "Userga balans xabari yuborilmadi: %s",
            error
        )

    await state.clear()
    await callback.answer()


@dp.callback_query(
    F.data == "adm:cancel_balance"
)
async def cancel_balance(
    callback: CallbackQuery,
    state: FSMContext
):

    await state.clear()

    await callback.message.edit_text(
        "❌ <b>Operatsiya bekor qilindi.</b>",
        reply_markup=admin_back_keyboard()
    )

    await callback.answer()


# =========================================================
# ADMIN CHECK USERNAME BALANCE
# =========================================================

@dp.callback_query(
    F.data == "adm:check"
)
async def admin_check(
    callback: CallbackQuery,
    state: FSMContext
):

    if not is_admin(
        callback.from_user.id
    ):
        return

    await state.set_state(
        AdminBalanceState.username
    )

    await state.update_data(
        operation="check"
    )

    await callback.message.edit_text(
        "🔎 <b>USERNAME BO‘YICHA BALANS</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "@username yuboring:",
        reply_markup=admin_back_keyboard()
    )

    await callback.answer()


# =========================================================
# ADMIN API
# =========================================================

@dp.callback_query(
    F.data == "adm:api"
)
async def admin_api(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user.id
    ):
        return

    await callback.message.edit_text(
        "⏳ <b>SeenSMS API tekshirilmoqda...</b>"
    )

    try:

        services = await get_services()
        balance = await get_api_balance()

        service_count = (
            len(services)
            if isinstance(
                services,
                list
            )
            else 0
        )

        if isinstance(
            balance,
            dict
        ):

            balance_value = balance.get(
                "balance",
                "Noma'lum"
            )

        else:

            balance_value = "Noma'lum"

        await callback.message.edit_text(
            "🟢 <b>SEENSMS API ONLINE</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"⚡ Xizmatlar: "
            f"<b>{service_count}</b>\n"
            f"💰 API balans: "
            f"<b>{balance_value}</b>",
            reply_markup=admin_back_keyboard()
        )

    except Exception as error:

        await callback.message.edit_text(
            "🔴 <b>SEENSMS API OFFLINE</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<code>{str(error)[:500]}</code>",
            reply_markup=admin_back_keyboard()
        )

    await callback.answer()


# =========================================================
# ADMIN USERS
# =========================================================

@dp.callback_query(
    F.data == "adm:users"
)
async def admin_users(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user.id
    ):
        return

    users, orders, revenue, balances = (
        get_statistics()
    )

    await callback.message.edit_text(
        "👥 <b>FOYDALANUVCHILAR</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Jami: <b>{users}</b>\n"
        f"📦 Buyurtmalar: <b>{orders}</b>\n"
        f"💳 Umumiy balans: "
        f"<b>{balances:,.2f} so‘m</b>",
        reply_markup=admin_back_keyboard()
    )

    await callback.answer()


# =========================================================
# ADMIN ORDERS
# =========================================================

@dp.callback_query(
    F.data == "adm:orders"
)
async def admin_orders(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user.id
    ):
        return

    conn = get_db()
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

    text = (
        "📦 <b>SO‘NGGI BUYURTMALAR</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    if not rows:

        text += "Buyurtmalar hali yo‘q."

    else:

        for row in rows:

            text += (
                f"🆔 <code>{row[0]}</code>\n"
                f"👤 <code>{row[1]}</code>\n"
                f"🌐 {row[2]}\n"
                f"🔢 {row[3]:,}\n"
                f"💰 {row[4]:,.2f}\n"
                f"📌 {row[5]}\n"
                f"🕐 {row[6]}\n"
                "────────────\n"
            )

    await callback.message.edit_text(
        text[:4000],
        reply_markup=admin_back_keyboard()
    )

    await callback.answer()


# =========================================================
# BALANCE LOGS
# =========================================================

@dp.callback_query(
    F.data == "adm:logs"
)
async def admin_logs(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user.id
    ):
        return

    conn = get_db()
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

    text = (
        "📜 <b>BALANS TARIXI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    if not rows:

        text += "Operatsiyalar hali yo‘q."

    else:

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
                "────────────\n"
            )

    await callback.message.edit_text(
        text[:4000],
        reply_markup=admin_back_keyboard()
    )

    await callback.answer()


# =========================================================
# BROADCAST
# =========================================================

@dp.callback_query(
    F.data == "adm:broadcast"
)
async def broadcast_start(
    callback: CallbackQuery,
    state: FSMContext
):

    if not is_admin(
        callback.from_user.id
    ):
        return

    await state.set_state(
        BroadcastState.message
    )

    await callback.message.edit_text(
        "📢 <b>REKLAMA</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Yubormoqchi bo‘lgan xabaringizni "
        "keyingi xabarda yuboring.",
        reply_markup=admin_back_keyboard()
    )

    await callback.answer()


@dp.message(
    BroadcastState.message
)
async def broadcast_send(
    message: Message,
    state: FSMContext
):

    if not is_admin(
        message.from_user.id
    ):
        return

    users = get_all_users()

    sent = 0
    failed = 0

    await message.answer(
        f"📢 Yuborish boshlandi...\n"
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

        await asyncio.sleep(
            0.05
        )

    await state.clear()

    await message.answer(
        "📢 <b>REKLAMA YAKUNLANDI</b>\n"
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
async def admin_home(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user.id
    ):
        return

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
            "SEENSMS_API_KEY mavjud emas!"
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
