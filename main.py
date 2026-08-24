import asyncio
import logging
import os
import sqlite3
from datetime import datetime

import aiohttp

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
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
# SOZLAMALAR
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
SEENSMS_API_KEY = os.getenv("SEENSMS_API_KEY")

SEENSMS_API_URL = "https://seensms.uz/api/v1"

# 50% ustama
PRICE_MARKUP = 50

# Adminning Telegram raqamli ID'si
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# Admin username
ADMIN_USERNAME = os.getenv(
    "ADMIN_USERNAME",
    "rxk_17"
).replace("@", "")

DB_NAME = "best1smm.db"


if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi!")

if not SEENSMS_API_KEY:
    raise RuntimeError("SEENSMS_API_KEY topilmadi!")

if ADMIN_ID == 0:
    raise RuntimeError(
        "ADMIN_ID Render Environment Variables'da berilmagan!"
    )


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

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
            status TEXT,
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
        INSERT INTO users
        (user_id, username, first_name, balance,
         created_at, updated_at)
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
    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT balance FROM users WHERE user_id=?",
        (user_id,)
    )

    row = cur.fetchone()

    conn.close()

    return float(row[0]) if row else 0.0


def find_username(username):
    username = (
        username
        .strip()
        .replace("@", "")
        .lower()
    )

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT user_id, username, first_name, balance
        FROM users
        WHERE LOWER(username)=?
    """, (username,))

    row = cur.fetchone()

    conn.close()

    return row


def add_balance_username(
    username,
    amount,
    operation
):
    user = find_username(username)

    if not user:
        return None

    user_id = user[0]
    old = float(user[3])

    if operation == "add":
        new = old + amount
    else:
        new = old - amount

        if new < 0:
            return False

    conn = db()
    cur = conn.cursor()

    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    cur.execute("""
        UPDATE users
        SET balance=?, updated_at=?
        WHERE user_id=?
    """, (
        new,
        now,
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
        ADMIN_USERNAME,
        amount,
        operation,
        old,
        new,
        now
    ))

    conn.commit()
    conn.close()

    return {
        "user_id": user_id,
        "username": user[1],
        "name": user[2],
        "old": old,
        "new": new
    }


def charge_user(user_id, amount):
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


def refund_user(user_id, amount):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET balance = balance + ?,
            updated_at=?
        WHERE user_id=?
    """, (
        amount,
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
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
        "Pending",
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    ))

    conn.commit()
    conn.close()


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


class AdminCheckState(StatesGroup):
    username = State()


class BroadcastState(StatesGroup):
    message = State()


# =========================================================
# PLATFORMALAR
# =========================================================

PLATFORMS = {
    "youtube": {
        "name": "▶️ YouTube",
        "words": [
            "youtube"
        ],
        "domains": [
            "youtube.com",
            "youtu.be"
        ]
    },

    "telegram": {
        "name": "✈️ Telegram",
        "words": [
            "telegram",
            "tg "
        ],
        "domains": [
            "t.me",
            "telegram.me"
        ]
    },

    "instagram": {
        "name": "📸 Instagram",
        "words": [
            "instagram",
            "insta"
        ],
        "domains": [
            "instagram.com"
        ]
    },

    "tiktok": {
        "name": "🎵 TikTok",
        "words": [
            "tiktok",
            "tik tok"
        ],
        "domains": [
            "tiktok.com"
        ]
    }
}


# =========================================================
# ASOSIY MENYU
# =========================================================

def main_menu():

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
# BUYURTMA INLINE
# =========================================================

def platform_menu():

    b = InlineKeyboardBuilder()

    b.row(
        InlineKeyboardButton(
            text="▶️ YouTube",
            callback_data="platform:youtube"
        ),
        InlineKeyboardButton(
            text="✈️ Telegram",
            callback_data="platform:telegram"
        )
    )

    b.row(
        InlineKeyboardButton(
            text="📸 Instagram",
            callback_data="platform:instagram"
        ),
        InlineKeyboardButton(
            text="🎵 TikTok",
            callback_data="platform:tiktok"
        )
    )

    b.row(
        InlineKeyboardButton(
            text="❌ Bekor qilish",
            callback_data="order:cancel"
        )
    )

    return b.as_markup()


def back_order():

    b = InlineKeyboardBuilder()

    b.row(
        InlineKeyboardButton(
            text="🔙 Orqaga",
            callback_data="order:platform"
        ),
        InlineKeyboardButton(
            text="❌ Bekor qilish",
            callback_data="order:cancel"
        )
    )

    return b.as_markup()


def confirm_order():

    b = InlineKeyboardBuilder()

    b.row(
        InlineKeyboardButton(
            text="✅ BUYURTMA BERISH",
            callback_data="order:confirm"
        )
    )

    b.row(
        InlineKeyboardButton(
            text="🔙 Orqaga",
            callback_data="order:link"
        ),
        InlineKeyboardButton(
            text="❌ Bekor qilish",
            callback_data="order:cancel"
        )
    )

    return b.as_markup()


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start(
    message: Message,
    state: FSMContext
):

    await state.clear()

    save_user(message.from_user)

    await message.answer(
        "✨ <b>BEST1SMM</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🚀 SMM xizmatlar paneliga xush kelibsiz!\n\n"
        "⚡ Tezkor xizmatlar\n"
        "💰 Qulay narxlar\n"
        "🔒 Shaxsiy kabinet\n\n"
        "👇 <b>Kerakli bo‘limni tanlang:</b>",
        reply_markup=main_menu()
    )


# =========================================================
# BUYURTMA BOSHLASH
# =========================================================

@dp.message(
    F.text == "🛒 Buyurtma berish"
)
async def start_order(
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
        reply_markup=platform_menu()
    )


# =========================================================
# PLATFORM TANLASH
# =========================================================

@dp.callback_query(
    OrderState.platform,
    F.data.startswith("platform:")
)
async def platform_selected(
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

        services = await api(
            "services"
        )

        if not isinstance(
            services,
            list
        ):
            raise Exception(
                "Services javobi noto‘g‘ri."
            )

        p = PLATFORMS[platform]

        filtered = []

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

            text = (
                name
                + " "
                + category
            )

            if any(
                word.lower() in text
                for word in p["words"]
            ):
                filtered.append(
                    service
                )

        if not filtered:

            await callback.message.edit_text(
                "😔 <b>Bu platforma uchun "
                "xizmat topilmadi.</b>\n\n"
                "Boshqa platformani tanlang.",
                reply_markup=platform_menu()
            )

            await callback.answer()
            return

        await state.update_data(
            services=filtered
        )

        b = InlineKeyboardBuilder()

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

            rate = float(
                service.get(
                    "rate",
                    0
                )
            )

            # 50% ustama
            sell_rate = rate * 1.50

            if len(name) > 35:
                name = name[:32] + "..."

            button_text = (
                f"⚡ {name} "
                f"— {sell_rate:,.2f}/1000"
            )

            b.row(
                InlineKeyboardButton(
                    text=button_text[:64],
                    callback_data=f"service:{sid}"
                )
            )

        b.row(
            InlineKeyboardButton(
                text="🔙 Platformalar",
                callback_data="order:platform"
            )
        )

        await state.set_state(
            OrderState.service
        )

        await callback.message.edit_text(
            f"{p['name']}\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "⚡ <b>Tarifni tanlang:</b>\n\n"
            "💰 Narxlar 50% ustama bilan "
            "ko‘rsatilgan.",
            reply_markup=b.as_markup()
        )

    except Exception as e:

        logging.exception(e)

        await callback.message.edit_text(
            "❌ <b>API xatosi.</b>\n\n"
            "SeenSMS API sozlamalarini tekshiring.",
            reply_markup=platform_menu()
        )

    await callback.answer()


# =========================================================
# XIZMAT TANLASH
# =========================================================

@dp.callback_query(
    OrderState.service,
    F.data.startswith("service:")
)
async def service_selected(
    callback: CallbackQuery,
    state: FSMContext
):

    service_id = callback.data.split(":")[1]

    data = await state.get_data()

    service = None

    for item in data.get(
        "services",
        []
    ):

        if str(
            item.get(
                "service"
            )
        ) == service_id:

            service = item
            break

    if not service:

        await callback.answer(
            "Xizmat topilmadi!",
            show_alert=True
        )

        return

    rate = float(
        service.get(
            "rate",
            0
        )
    )

    sell_rate = rate * 1.50

    await state.update_data(
        service_id=service_id,
        service_name=service.get(
            "name",
            "Xizmat"
        ),
        rate=rate,
        sell_rate=sell_rate,
        minimum=int(
            float(
                service.get(
                    "min",
                    0
                )
            )
        ),
        maximum=int(
            float(
                service.get(
                    "max",
                    0
                )
            )
        )
    )

    await state.set_state(
        OrderState.quantity
    )

    await callback.message.edit_text(
        "🔢 <b>MIQDORNI KIRITING</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⚡ {service.get('name')}\n\n"
        f"📊 Minimum: "
        f"<b>{service.get('min')}</b>\n"
        f"📈 Maximum: "
        f"<b>{service.get('max')}</b>\n"
        f"💰 Narx: "
        f"<b>{sell_rate:,.2f} so‘m / 1000</b>\n\n"
        "Masalan: <code>1000</code>",
        reply_markup=back_order()
    )

    await callback.answer()


# =========================================================
# MIQDOR
# =========================================================

@dp.message(
    OrderState.quantity
)
async def quantity(
    message: Message,
    state: FSMContext
):

    text = (message.text or "").strip()

    if not text.isdigit():

        await message.answer(
            "❌ Faqat son kiriting.\n\n"
            "Masalan: <code>1000</code>",
            reply_markup=back_order()
        )

        return

    quantity = int(text)

    data = await state.get_data()

    minimum = data["minimum"]
    maximum = data["maximum"]

    if quantity < minimum:

        await message.answer(
            f"❌ Minimum miqdor: "
            f"<b>{minimum}</b>"
        )

        return

    if quantity > maximum:

        await message.answer(
            f"❌ Maximum miqdor: "
            f"<b>{maximum}</b>"
        )

        return

    # 50% ustama bilan user narxi
    price = (
        data["sell_rate"]
        * quantity
        / 1000
    )

    await state.update_data(
        quantity=quantity,
        price=price
    )

    await state.set_state(
        OrderState.link
    )

    await message.answer(
        "🔗 <b>HAVOLANI KIRITING</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔢 Miqdor: "
        f"<b>{quantity:,}</b>\n"
        f"💰 To‘lov: "
        f"<b>{price:,.2f} so‘m</b>\n\n"
        "📎 Havolani yuboring:",
        reply_markup=back_order()
    )


# =========================================================
# HAVOLA
# =========================================================

@dp.message(
    OrderState.link
)
async def link(
    message: Message,
    state: FSMContext
):

    url = (message.text or "").strip()

    if not (
        url.startswith("https://")
        or url.startswith("http://")
    ):

        await message.answer(
            "❌ Havola noto‘g‘ri.\n\n"
            "https:// bilan boshlanadigan "
            "havola yuboring.",
            reply_markup=back_order()
        )

        return

    data = await state.get_data()

    domains = PLATFORMS[
        data["platform"]
    ]["domains"]

    if not any(
        domain in url.lower()
        for domain in domains
    ):

        await message.answer(
            "❌ Havola tanlangan platformaga "
            "mos emas.",
            reply_markup=back_order()
        )

        return

    await state.update_data(
        link=url
    )

    await state.set_state(
        OrderState.confirm
    )

    await message.answer(
        "🧾 <b>BUYURTMANI TEKSHIRING</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🌐 Platforma: "
        f"<b>{PLATFORMS[data['platform']]['name']}</b>\n\n"
        f"⚡ Xizmat:\n"
        f"<b>{data['service_name']}</b>\n\n"
        f"🔢 Miqdor: "
        f"<b>{data['quantity']:,}</b>\n\n"
        f"💰 To‘lov: "
        f"<b>{data['price']:,.2f} so‘m</b>\n\n"
        f"🔗 Havola:\n"
        f"<code>{url}</code>\n\n"
        "Buyurtmani tasdiqlaysizmi?",
        reply_markup=confirm_order()
    )


# =========================================================
# TASDIQLASH
# =========================================================

@dp.callback_query(
    OrderState.confirm,
    F.data == "order:confirm"
)
async def confirm(
    callback: CallbackQuery,
    state: FSMContext
):

    data = await state.get_data()

    user_id = callback.from_user.id
    price = float(data["price"])

    # Avval user balansini tekshirish
    balance = get_balance(user_id)

    if balance < price:

        await callback.message.edit_text(
            "❌ <b>BALANS YETARLI EMAS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 Kerak: "
            f"<b>{price:,.2f} so‘m</b>\n"
            f"💳 Sizda: "
            f"<b>{balance:,.2f} so‘m</b>\n\n"
            "Hisobni admin orqali to‘ldiring.",
            reply_markup=platform_menu()
        )

        await state.clear()
        await callback.answer()
        return

    # User balansidan yechish
    new_balance = charge_user(
        user_id,
        price
    )

    if new_balance is None or new_balance is False:

        await callback.message.edit_text(
            "❌ Balansni yechishda xatolik.",
            reply_markup=platform_menu()
        )

        await state.clear()
        await callback.answer()
        return

    await callback.message.edit_text(
        "⏳ <b>BUYURTMA YUBORILMOQDA...</b>"
    )

    try:

        result = await api(
            "add",
            service=data["service_id"],
            link=data["link"],
            quantity=data["quantity"]
        )

        if not isinstance(
            result,
            dict
        ):
            raise Exception(
                "API javobi noto‘g‘ri."
            )

        order_id = result.get(
            "order"
        )

        if not order_id:

            # API qabul qilmasa pulni qaytaramiz
            refund_user(
                user_id,
                price
            )

            error = result.get(
                "error",
                "Noma'lum API xatosi"
            )

            await callback.message.edit_text(
                "❌ <b>BUYURTMA YUBORILMADI</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📛 {error}\n\n"
                "💰 Mablag‘ingiz balansga qaytarildi.",
                reply_markup=platform_menu()
            )

            await state.clear()
            await callback.answer()
            return

        save_order(
            user_id,
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
            f"🆔 Buyurtma ID: "
            f"<code>{order_id}</code>\n"
            f"🌐 Platforma: "
            f"<b>{PLATFORMS[data['platform']]['name']}</b>\n"
            f"🔢 Miqdor: "
            f"<b>{data['quantity']:,}</b>\n"
            f"💰 To‘lov: "
            f"<b>{price:,.2f} so‘m</b>\n"
            f"💳 Qolgan balans: "
            f"<b>{new_balance:,.2f} so‘m</b>\n\n"
            "⏳ Buyurtma bajarilishi boshlanadi.",
            reply_markup=platform_menu()
        )

    except Exception as e:

        logging.exception(e)

        # API ishlamasa user pulini qaytarish
        refund_user(
            user_id,
            price
        )

        await callback.message.edit_text(
            "❌ <b>BUYURTMA YUBORILMADI</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "SeenSMS API bilan bog‘lanishda "
            "xatolik yuz berdi.\n\n"
            "💰 Mablag‘ingiz balansga qaytarildi.",
            reply_markup=platform_menu()
        )

    await state.clear()
    await callback.answer()


# =========================================================
# ORQAGA / BEKOR
# =========================================================

@dp.callback_query(
    F.data == "order:platform"
)
async def order_platform(
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
        reply_markup=platform_menu()
    )

    await callback.answer()


@dp.callback_query(
    F.data == "order:link"
)
async def order_link_back(
    callback: CallbackQuery,
    state: FSMContext
):

    await state.set_state(
        OrderState.link
    )

    await callback.message.edit_text(
        "🔗 <b>HAVOLANI KIRITING</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📎 Havolani yuboring:",
        reply_markup=back_order()
    )

    await callback.answer()


@dp.callback_query(
    F.data == "order:cancel"
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
# API
# =========================================================

async def api(action, **kwargs):

    payload = {
        "key": SEENSMS_API_KEY,
        "action": action
    }

    payload.update(kwargs)

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
                raise Exception(
                    f"HTTP {response.status}: {text}"
                )

            try:
                import json
                return json.loads(text)

            except Exception:
                raise Exception(
                    text[:500]
                )


# =========================================================
# HISOBNI TO‘LDIRISH
# =========================================================

@dp.message(
    F.text == "💳 Hisobni to‘ldirish"
)
async def deposit(
    message: Message
):

    b = InlineKeyboardBuilder()

    b.row(
        InlineKeyboardButton(
            text="👑 Admin bilan bog‘lanish",
            url=f"https://t.me/{ADMIN_USERNAME}"
        )
    )

    await message.answer(
        "💳 <b>HISOBNI TO‘LDIRISH</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Joriy balans: "
        f"<b>{get_balance(message.from_user.id):,.2f} so‘m</b>\n\n"
        "Balansni admin orqali to‘ldirish mumkin.\n\n"
        f"👑 Admin: @{ADMIN_USERNAME}",
        reply_markup=b.as_markup()
    )


# =========================================================
# KABINET
# =========================================================

@dp.message(
    F.text == "👤 Shaxsiy kabinet"
)
async def cabinet(
    message: Message
):

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*)
        FROM orders
        WHERE user_id=?
    """, (
        message.from_user.id,
    ))

    orders = cur.fetchone()[0]

    conn.close()

    username = (
        "@" + message.from_user.username
        if message.from_user.username
        else "username yo‘q"
    )

    await message.answer(
        "👤 <b>SHAXSIY KABINET</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📛 Ism: "
        f"<b>{message.from_user.first_name}</b>\n"
        f"👤 Username: "
        f"<b>{username}</b>\n"
        f"🆔 ID: "
        f"<code>{message.from_user.id}</code>\n\n"
        f"💰 Balans: "
        f"<b>{get_balance(message.from_user.id):,.2f} so‘m</b>\n"
        f"📦 Buyurtmalar: "
        f"<b>{orders}</b>",
        reply_markup=main_menu()
    )


# =========================================================
# YORDAM
# =========================================================

@dp.message(
    F.text == "🆘 Yordam"
)
async def help_menu(
    message: Message
):

    await message.answer(
        "🆘 <b>YORDAM</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🛒 <b>Buyurtma berish</b>\n"
        "Xizmat tanlaysiz → miqdor → havola "
        "→ tasdiqlaysiz.\n\n"
        "💳 <b>Hisobni to‘ldirish</b>\n"
        "Admin orqali amalga oshiriladi.\n\n"
        "👤 <b>Shaxsiy kabinet</b>\n"
        "Balans va buyurtmalarni ko‘rasiz.\n\n"
        f"👑 Admin: @{ADMIN_USERNAME}",
        reply_markup=main_menu()
    )


# =========================================================
# ADMIN PANEL
# =========================================================

def admin_menu():

    b = InlineKeyboardBuilder()

    b.row(
        InlineKeyboardButton(
            text="📊 Statistika",
            callback_data="admin:stats"
        )
    )

    b.row(
        InlineKeyboardButton(
            text="💳 Balans qo‘shish",
            callback_data="admin:add"
        ),
        InlineKeyboardButton(
            text="➖ Balans ayirish",
            callback_data="admin:remove"
        )
    )

    b.row(
        InlineKeyboardButton(
            text="🔎 Balans tekshirish",
            callback_data="admin:check"
        )
    )

    b.row(
        InlineKeyboardButton(
            text="📦 Buyurtmalar",
            callback_data="admin:orders"
        ),
        InlineKeyboardButton(
            text="📜 Balans tarixi",
            callback_data="admin:logs"
        )
    )

    b.row(
        InlineKeyboardButton(
            text="🔌 SeenSMS API",
            callback_data="admin:api"
        )
    )

    b.row(
        InlineKeyboardButton(
            text="📢 Reklama",
            callback_data="admin:broadcast"
        )
    )

    return b.as_markup()


def admin_allowed(user_id):
    return user_id == ADMIN_ID


@dp.message(Command("admin"))
async def admin_command(
    message: Message
):

    if not admin_allowed(
        message.from_user.id
    ):

        await message.answer(
            "⛔ Sizda admin huquqi yo‘q."
        )

        return

    await message.answer(
        "👑 <b>BEST1SMM ADMIN PANEL</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "👇 Kerakli bo‘limni tanlang:",
        reply_markup=admin_menu()
    )


# =========================================================
# ADMIN STATISTIKA
# =========================================================

@dp.callback_query(
    F.data == "admin:stats"
)
async def admin_stats(
    callback: CallbackQuery
):

    if not admin_allowed(
        callback.from_user.id
    ):
        return

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
        "SELECT COALESCE(SUM(balance),0) FROM users"
    )
    balances = float(
        cur.fetchone()[0]
    )

    cur.execute(
        "SELECT COALESCE(SUM(price),0) FROM orders"
    )
    sales = float(
        cur.fetchone()[0]
    )

    conn.close()

    await callback.message.edit_text(
        "📊 <b>STATISTIKA</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Userlar: <b>{users}</b>\n"
        f"📦 Buyurtmalar: <b>{orders}</b>\n"
        f"💳 User balanslari: "
        f"<b>{balances:,.2f} so‘m</b>\n"
        f"💰 Buyurtmalar summasi: "
        f"<b>{sales:,.2f} so‘m</b>",
        reply_markup=admin_menu()
    )

    await callback.answer()


# =========================================================
# ADMIN BALANS
# =========================================================

async def admin_balance_start(
    callback,
    state,
    operation
):

    if not admin_allowed(
        callback.from_user.id
    ):
        return

    await state.update_data(
        operation=operation
    )

    await state.set_state(
        AdminBalanceState.username
    )

    title = (
        "➕ BALANS QO‘SHISH"
        if operation == "add"
        else
        "➖ BALANS AYIRISH"
    )

    await callback.message.edit_text(
        f"👑 <b>{title}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "👤 User username'ini yuboring:\n\n"
        "Masalan:\n"
        "<code>@user123</code>\n\n"
        "⚠️ User botga avval /start bosgan "
        "bo‘lishi kerak."
    )

    await callback.answer()


@dp.callback_query(
    F.data == "admin:add"
)
async def admin_add(
    callback: CallbackQuery,
    state: FSMContext
):

    await admin_balance_start(
        callback,
        state,
        "add"
    )


@dp.callback_query(
    F.data == "admin:remove"
)
async def admin_remove(
    callback: CallbackQuery,
    state: FSMContext
):

    await admin_balance_start(
        callback,
        state,
        "remove"
    )


@dp.message(
    AdminBalanceState.username
)
async def admin_username(
    message: Message,
    state: FSMContext
):

    username = (
        message.text or ""
    ).strip().replace("@", "")

    user = find_username(
        username
    )

    if not user:

        await message.answer(
            "❌ User topilmadi.\n\n"
            f"🔎 @{username}\n\n"
            "User botga /start bosgan bo‘lishi kerak."
        )

        return

    await state.update_data(
        target_username=username,
        target_user_id=user[0],
        old_balance=float(user[3])
    )

    await state.set_state(
        AdminBalanceState.amount
    )

    data = await state.get_data()

    await message.answer(
        "💰 <b>SUMMA KIRITING</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 User: <b>@{username}</b>\n"
        f"💳 Hozirgi balans: "
        f"<b>{user[3]:,.2f} so‘m</b>\n\n"
        "Masalan: <code>50000</code>"
    )


@dp.message(
    AdminBalanceState.amount
)
async def admin_amount(
    message: Message,
    state: FSMContext
):

    try:

        amount = float(
            (message.text or "")
            .replace(" ", "")
            .replace(",", ".")
        )

        if amount <= 0:
            raise ValueError

    except Exception:

        await message.answer(
            "❌ To‘g‘ri summa kiriting."
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

        if new_balance < 0:

            await message.answer(
                "❌ Balans manfiy bo‘lishi mumkin emas."
            )

            return

        action = "➖ Ayiriladi"

    await state.update_data(
        amount=amount,
        new_balance=new_balance
    )

    await state.set_state(
        AdminBalanceState.confirm
    )

    b = InlineKeyboardBuilder()

    b.row(
        InlineKeyboardButton(
            text="✅ TASDIQLASH",
            callback_data="admin:balance_confirm"
        )
    )

    b.row(
        InlineKeyboardButton(
            text="❌ BEKOR QILISH",
            callback_data="admin:balance_cancel"
        )
    )

    await message.answer(
        "🧾 <b>TASDIQLASH</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 @{data['target_username']}\n"
        f"{action}: "
        f"<b>{amount:,.2f} so‘m</b>\n\n"
        f"💳 Eski: "
        f"<b>{data['old_balance']:,.2f}</b>\n"
        f"💰 Yangi: "
        f"<b>{new_balance:,.2f}</b>",
        reply_markup=b.as_markup()
    )


@dp.callback_query(
    F.data == "admin:balance_confirm"
)
async def admin_balance_confirm(
    callback: CallbackQuery,
    state: FSMContext
):

    if not admin_allowed(
        callback.from_user.id
    ):
        return

    data = await state.get_data()

    result = add_balance_username(
        data["target_username"],
        data["amount"],
        data["operation"]
    )

    if result is None:

        await callback.message.edit_text(
            "❌ User topilmadi.",
            reply_markup=admin_menu()
        )

        await state.clear()
        await callback.answer()
        return

    if result is False:

        await callback.message.edit_text(
            "❌ Balans yetarli emas.",
            reply_markup=admin_menu()
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
        "✅ <b>BALANS O‘ZGARTIRILDI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 @{result['username']}\n"
        f"{symbol} "
        f"<b>{data['amount']:,.2f} so‘m</b>\n"
        f"💰 Yangi balans: "
        f"<b>{result['new']:,.2f} so‘m</b>",
        reply_markup=admin_menu()
    )

    try:

        await bot.send_message(
            result["user_id"],
            "💳 <b>BALANSINGIZ YANGILANDI</b>\n\n"
            f"{symbol} "
            f"<b>{data['amount']:,.2f} so‘m</b>\n"
            f"💰 Yangi balans: "
            f"<b>{result['new']:,.2f} so‘m</b>"
        )

    except Exception:
        pass

    await state.clear()
    await callback.answer()


@dp.callback_query(
    F.data == "admin:balance_cancel"
)
async def admin_balance_cancel(
    callback: CallbackQuery,
    state: FSMContext
):

    await state.clear()

    await callback.message.edit_text(
        "❌ Operatsiya bekor qilindi.",
        reply_markup=admin_menu()
    )

    await callback.answer()


# =========================================================
# ADMIN USER BALANSINI TEKSHIRISH
# =========================================================

@dp.callback_query(
    F.data == "admin:check"
)
async def admin_check(
    callback: CallbackQuery,
    state: FSMContext
):

    await state.set_state(
        AdminCheckState.username
    )

    await callback.message.edit_text(
        "🔎 <b>BALANSNI TEKSHIRISH</b>\n\n"
        "@username yuboring:"
    )

    await callback.answer()


@dp.message(
    AdminCheckState.username
)
async def admin_check_username(
    message: Message,
    state: FSMContext
):

    username = (
        message.text or ""
    ).strip().replace("@", "")

    user = find_username(
        username
    )

    if not user:

        await message.answer(
            f"❌ @{username} topilmadi."
        )

        return

    await message.answer(
        "🔎 <b>USER BALANSI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 @{user[1]}\n"
        f"📛 {user[2]}\n"
        f"💰 Balans: "
        f"<b>{float(user[3]):,.2f} so‘m</b>",
        reply_markup=admin_menu()
    )

    await state.clear()


# =========================================================
# ADMIN API BALANCE
# =========================================================

@dp.callback_query(
    F.data == "admin:api"
)
async def admin_api(
    callback: CallbackQuery
):

    try:

        result = await api(
            "balance"
        )

        await callback.message.edit_text(
            "🔌 <b>SEENSMS API</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🟢 Status: <b>ONLINE</b>\n"
            f"💰 API balans: "
            f"<b>{result.get('balance')}</b>\n"
            f"💵 Valyuta: "
            f"<b>{result.get('currency')}</b>",
            reply_markup=admin_menu()
        )

    except Exception as e:

        await callback.message.edit_text(
            "🔴 <b>API XATOSI</b>\n\n"
            f"<code>{str(e)[:1000]}</code>",
            reply_markup=admin_menu()
        )

    await callback.answer()


# =========================================================
# ADMIN BUYURTMALAR
# =========================================================

@dp.callback_query(
    F.data == "admin:orders"
)
async def admin_orders(
    callback: CallbackQuery
):

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            api_order_id,
            user_id,
            platform,
            quantity,
            price,
            status
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

        text += "Hali buyurtma yo‘q."

    else:

        for row in rows:

            text += (
                f"🆔 <code>{row[0]}</code>\n"
                f"👤 <code>{row[1]}</code>\n"
                f"🌐 {row[2]}\n"
                f"🔢 {row[3]:,}\n"
                f"💰 {row[4]:,.2f}\n"
                f"📌 {row[5]}\n"
                "────────────\n"
            )

    await callback.message.edit_text(
        text[:4000],
        reply_markup=admin_menu()
    )

    await callback.answer()


# =========================================================
# BALANS TARIXI
# =========================================================

@dp.callback_query(
    F.data == "admin:logs"
)
async def admin_logs(
    callback: CallbackQuery
):

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            user_id,
            amount,
            operation,
            old_balance,
            new_balance
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

        text += "Tarix bo‘sh."

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
                "────────────\n"
            )

    await callback.message.edit_text(
        text[:4000],
        reply_markup=admin_menu()
    )

    await callback.answer()


# =========================================================
# BROADCAST
# =========================================================

@dp.callback_query(
    F.data == "admin:broadcast"
)
async def broadcast(
    callback: CallbackQuery,
    state: FSMContext
):

    await state.set_state(
        BroadcastState.message
    )

    await callback.message.edit_text(
        "📢 <b>REKLAMA</b>\n\n"
        "Yubormoqchi bo‘lgan xabaringizni "
        "keyingi xabarda yuboring."
    )

    await callback.answer()


@dp.message(
    BroadcastState.message
)
async def broadcast_send(
    message: Message,
    state: FSMContext
):

    if not admin_allowed(
        message.from_user.id
    ):
        return

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT user_id FROM users"
    )

    users = [
        x[0]
        for x in cur.fetchall()
    ]

    conn.close()

    sent = 0
    failed = 0

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
        "📢 <b>REKLAMA YAKUNLANDI</b>\n\n"
        f"✅ Yuborildi: <b>{sent}</b>\n"
        f"❌ Xato: <b>{failed}</b>",
        reply_markup=admin_menu()
    )


# =========================================================
# ISHGA TUSHIRISH
# =========================================================

async def main():

    init_db()

    await bot.delete_webhook(
        drop_pending_updates=True
    )

    logging.info(
        "🚀 BEST1SMM BOT ISHLADI"
    )

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
