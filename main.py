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
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


# ============================================================
#                         SOZLAMALAR
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
SEENSMS_API_KEY = os.getenv("SEENSMS_API_KEY")

SEENSMS_API_URL = "https://seensms.uz/api/v1"

ADMIN_USERNAME = "rxk_17"


# ============================================================
#                         LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("Best1SMM")


# ============================================================
#                       BOT
# ============================================================

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    )
)

dp = Dispatcher(
    storage=MemoryStorage()
)


# ============================================================
#                       DATABASE
# ============================================================

DB_NAME = "best1smm.db"


def init_db():

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            joined_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            seensms_order_id TEXT,
            platform TEXT,
            service TEXT,
            quantity INTEGER,
            link TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


def save_user(user):

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO users
        (user_id, username, first_name, joined_at)
        VALUES (
            ?,
            ?,
            ?,
            COALESCE(
                (SELECT joined_at FROM users WHERE user_id = ?),
                ?
            )
        )
    """, (
        user.id,
        user.username or "",
        user.first_name or "",
        user.id,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()


def save_order(
    user_id,
    seensms_order_id,
    platform,
    service,
    quantity,
    link
):

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO orders
        (
            user_id,
            seensms_order_id,
            platform,
            service,
            quantity,
            link,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        str(seensms_order_id),
        platform,
        service,
        quantity,
        link,
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    ))

    conn.commit()
    conn.close()


def get_statistics():

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT COUNT(*) FROM users"
    )
    users = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM orders"
    )
    orders = cursor.fetchone()[0]

    conn.close()

    return users, orders


def get_users():

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT user_id FROM users"
    )

    users = [
        row[0]
        for row in cursor.fetchall()
    ]

    conn.close()

    return users


# ============================================================
#                         STATES
# ============================================================

class OrderState(StatesGroup):

    choosing_platform = State()
    choosing_service = State()
    entering_quantity = State()
    entering_link = State()
    confirming = State()


class AdminState(StatesGroup):

    broadcasting = State()


# ============================================================
#                       PLATFORMS
# ============================================================

PLATFORMS = {

    "youtube": {
        "name": "▶️ YouTube",
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
        "name": "✈️ Telegram",
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
        "name": "📸 Instagram",
        "keywords": [
            "instagram",
            "insta"
        ],
        "domains": [
            "instagram.com"
        ]
    },

    "tiktok": {
        "name": "🎵 TikTok",
        "keywords": [
            "tiktok",
            "tik tok"
        ],
        "domains": [
            "tiktok.com"
        ]
    }
}


# ============================================================
#                       MAIN MENU
# ============================================================

def main_menu():

    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="🛒 Buyurtma berish",
            callback_data="new_order"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="💰 Balans",
            callback_data="balance"
        ),
        InlineKeyboardButton(
            text="🆘 Yordam",
            callback_data="help"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="👤 Shaxsiy kabinet",
            callback_data="profile"
        )
    )

    return builder.as_markup()


# ============================================================
#                     ADMIN MENU
# ============================================================

def admin_menu():

    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="📊 Statistika",
            callback_data="admin_stats"
        ),
        InlineKeyboardButton(
            text="💰 API balans",
            callback_data="admin_balance"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="📦 Buyurtmalar",
            callback_data="admin_orders"
        ),
        InlineKeyboardButton(
            text="👥 Foydalanuvchilar",
            callback_data="admin_users"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="🔌 API tekshirish",
            callback_data="admin_api"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="📢 Reklama yuborish",
            callback_data="admin_broadcast"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="🔙 Asosiy menyu",
            callback_data="back_main"
        )
    )

    return builder.as_markup()


def admin_back():

    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="🔙 Admin panel",
            callback_data="admin_panel"
        )
    )

    return builder.as_markup()


# ============================================================
#                       API
# ============================================================

async def seensms_request(data):

    if not SEENSMS_API_KEY:

        raise RuntimeError(
            "SEENSMS_API_KEY topilmadi"
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
                    f"HTTP {response.status}"
                )

            try:

                return await response.json()

            except Exception:

                raise RuntimeError(
                    text[:500]
                )


async def get_services():

    return await seensms_request({
        "action": "services"
    })


async def get_balance():

    return await seensms_request({
        "action": "balance"
    })


async def add_order(
    service_id,
    link,
    quantity
):

    return await seensms_request({
        "action": "add",
        "service": service_id,
        "link": link,
        "quantity": quantity
    })


# ============================================================
#                  HELPER FUNCTIONS
# ============================================================

def normalize(value):

    return str(value).lower().strip()


def safe_int(value):

    try:
        return int(float(str(value)))
    except Exception:
        return None


def calculate_price(rate, quantity):

    try:

        return (
            float(rate)
            * int(quantity)
            / 1000
        )

    except Exception:

        return 0


def service_matches(
    service,
    platform
):

    info = PLATFORMS.get(platform)

    if not info:
        return False

    name = normalize(
        service.get("name", "")
    )

    category = normalize(
        service.get("category", "")
    )

    text = (
        name
        + " "
        + category
    )

    return any(
        keyword in text
        for keyword in info["keywords"]
    )


# ============================================================
#                    PLATFORM MENU
# ============================================================

def platform_menu():

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
            callback_data="back_main"
        )
    )

    return builder.as_markup()


def service_menu(services):

    builder = InlineKeyboardBuilder()

    for service in services:

        service_id = service.get(
            "service"
        )

        name = str(
            service.get(
                "name",
                "Noma'lum"
            )
        )

        if len(name) > 55:

            name = name[:52] + "..."

        builder.row(
            InlineKeyboardButton(
                text=f"⚡ {name}",
                callback_data=(
                    f"service:{service_id}"
                )
            )
        )

    builder.row(
        InlineKeyboardButton(
            text="🔙 Platformalar",
            callback_data="back_platforms"
        )
    )

    return builder.as_markup()


def cancel_menu():

    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="🔙 Orqaga",
            callback_data="back_platforms"
        ),
        InlineKeyboardButton(
            text="❌ Bekor qilish",
            callback_data="cancel_order"
        )
    )

    return builder.as_markup()


def confirm_menu():

    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="✅ BUYURTMA BERISH",
            callback_data="confirm_order"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="🔙 Orqaga",
            callback_data="back_link"
        ),
        InlineKeyboardButton(
            text="❌ Bekor qilish",
            callback_data="cancel_order"
        )
    )

    return builder.as_markup()


# ============================================================
#                         START
# ============================================================

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
        "🚀 SMM xizmatlarining zamonaviy paneli\n\n"
        "📈 Tezkor buyurtmalar\n"
        "⚡ Avtomatik xizmatlar\n"
        "💎 Qulay boshqaruv\n\n"
        "👇 <b>Kerakli bo‘limni tanlang:</b>",
        reply_markup=main_menu()
    )


# ============================================================
#                     BUYURTMA
# ============================================================

@dp.callback_query(
    F.data == "new_order"
)
async def new_order(
    callback: CallbackQuery,
    state: FSMContext
):

    await state.set_state(
        OrderState.choosing_platform
    )

    await callback.message.edit_text(
        "🛒 <b>BUYURTMA BERISH</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🌐 Platformani tanlang:",
        reply_markup=platform_menu()
    )

    await callback.answer()


# ============================================================
#                  PLATFORM TANLASH
# ============================================================

@dp.callback_query(
    OrderState.choosing_platform,
    F.data.startswith("platform:")
)
async def choose_platform(
    callback: CallbackQuery,
    state: FSMContext
):

    platform = callback.data.split(
        ":",
        1
    )[1]

    await state.update_data(
        platform=platform
    )

    await callback.message.edit_text(
        "⏳ <b>Tariflar yuklanmoqda...</b>"
    )

    try:

        services = await get_services()

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
                "😔 <b>Tarif topilmadi.</b>\n\n"
                "Boshqa platformani tanlang.",
                reply_markup=platform_menu()
            )

            await callback.answer()
            return

        await state.update_data(
            available_services=filtered
        )

        await state.set_state(
            OrderState.choosing_service
        )

        await callback.message.edit_text(
            f"{PLATFORMS[platform]['name']}\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "⚡ <b>Tarifni tanlang:</b>",
            reply_markup=service_menu(filtered)
        )

    except Exception as error:

        logger.exception(
            "Service error: %s",
            error
        )

        await callback.message.edit_text(
            "❌ <b>Tariflarni yuklab bo‘lmadi.</b>",
            reply_markup=platform_menu()
        )

    await callback.answer()


# ============================================================
#                     TARIF TANLASH
# ============================================================

@dp.callback_query(
    OrderState.choosing_service,
    F.data.startswith("service:")
)
async def choose_service(
    callback: CallbackQuery,
    state: FSMContext
):

    service_id = callback.data.split(
        ":",
        1
    )[1]

    data = await state.get_data()

    selected = None

    for service in data.get(
        "available_services",
        []
    ):

        if str(
            service.get("service")
        ) == str(service_id):

            selected = service
            break

    if not selected:

        await callback.answer(
            "❌ Tarif topilmadi!",
            show_alert=True
        )

        return

    await state.update_data(
        service_id=service_id,
        service_name=selected.get(
            "name",
            "Noma'lum"
        ),
        service_rate=selected.get(
            "rate"
        ),
        service_min=selected.get(
            "min"
        ),
        service_max=selected.get(
            "max"
        )
    )

    await state.set_state(
        OrderState.entering_quantity
    )

    await callback.message.edit_text(
        "🔢 <b>MIQDORNI KIRITING</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⚡ Tarif:\n"
        f"<b>{selected.get('name')}</b>\n\n"
        f"📊 Minimum: "
        f"<b>{selected.get('min')}</b>\n"
        f"📈 Maximum: "
        f"<b>{selected.get('max')}</b>\n\n"
        "💡 Masalan: <code>1000</code>\n\n"
        "👇 Nechta kerakligini yozing:",
        reply_markup=cancel_menu()
    )

    await callback.answer()


# ============================================================
#                    MIQDOR KIRITISH
# ============================================================

@dp.message(
    OrderState.entering_quantity
)
async def quantity(
    message: Message,
    state: FSMContext
):

    value = (
        message.text.strip()
        if message.text
        else ""
    )

    if not value.isdigit():

        await message.answer(
            "❌ <b>Faqat son kiriting!</b>\n\n"
            "Masalan: <code>1000</code>",
            reply_markup=cancel_menu()
        )

        return

    quantity_value = int(value)

    data = await state.get_data()

    minimum = safe_int(
        data.get("service_min")
    )

    maximum = safe_int(
        data.get("service_max")
    )

    if minimum and quantity_value < minimum:

        await message.answer(
            f"❌ Miqdor minimumdan kam.\n\n"
            f"📊 Minimum: <b>{minimum}</b>",
            reply_markup=cancel_menu()
        )

        return

    if maximum and quantity_value > maximum:

        await message.answer(
            f"❌ Miqdor maximumdan ko‘p.\n\n"
            f"📈 Maximum: <b>{maximum}</b>",
            reply_markup=cancel_menu()
        )

        return

    price = calculate_price(
        data.get("service_rate"),
        quantity_value
    )

    await state.update_data(
        quantity=quantity_value,
        calculated_price=price
    )

    await state.set_state(
        OrderState.entering_link
    )

    await message.answer(
        "🔗 <b>HAVOLANI KIRITING</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔢 Miqdor: "
        f"<b>{quantity_value:,}</b>\n"
        f"💰 Narx: "
        f"<b>{price:,.2f}</b>\n\n"
        "📎 Buyurtma beriladigan havolani yuboring.\n\n"
        "👇 Masalan:\n"
        "<code>https://instagram.com/...</code>",
        reply_markup=cancel_menu()
    )


# ============================================================
#                      HAVOLA
# ============================================================

@dp.message(
    OrderState.entering_link
)
async def link(
    message: Message,
    state: FSMContext
):

    link_value = (
        message.text.strip()
        if message.text
        else ""
    )

    if not (
        link_value.startswith("https://")
        or link_value.startswith("http://")
    ):

        await message.answer(
            "❌ <b>Noto‘g‘ri havola!</b>\n\n"
            "Havola http:// yoki https:// bilan "
            "boshlanishi kerak.",
            reply_markup=cancel_menu()
        )

        return

    data = await state.get_data()

    platform = data.get(
        "platform"
    )

    domains = PLATFORMS[
        platform
    ]["domains"]

    if not any(
        domain in link_value.lower()
        for domain in domains
    ):

        await message.answer(
            "❌ <b>Havola platformaga mos emas!</b>\n\n"
            f"Tanlangan: "
            f"<b>{PLATFORMS[platform]['name']}</b>",
            reply_markup=cancel_menu()
        )

        return

    await state.update_data(
        link=link_value
    )

    await state.set_state(
        OrderState.confirming
    )

    await message.answer(
        "🧾 <b>BUYURTMA TASDIG‘I</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🌐 Platforma:\n"
        f"<b>{PLATFORMS[platform]['name']}</b>\n\n"
        f"⚡ Tarif:\n"
        f"<b>{data.get('service_name')}</b>\n\n"
        f"🔢 Miqdor:\n"
        f"<b>{data.get('quantity'):,}</b>\n\n"
        f"🔗 Havola:\n"
        f"<code>{link_value}</code>\n\n"
        f"💰 Narx:\n"
        f"<b>{data.get('calculated_price'):,.2f}</b>\n\n"
        "👇 Ma’lumotlarni tekshiring:",
        reply_markup=confirm_menu()
    )


# ============================================================
#                BUYURTMA TASDIQLASH
# ============================================================

@dp.callback_query(
    OrderState.confirming,
    F.data == "confirm_order"
)
async def confirm_order(
    callback: CallbackQuery,
    state: FSMContext
):

    data = await state.get_data()

    await callback.message.edit_text(
        "⏳ <b>BUYURTMA YUBORILMOQDA...</b>\n\n"
        "🔄 SeenSMS API bilan bog‘lanilmoqda..."
    )

    try:

        response = await add_order(
            service_id=int(
                data["service_id"]
            ),
            link=data["link"],
            quantity=int(
                data["quantity"]
            )
        )

        if (
            isinstance(response, dict)
            and response.get("order")
        ):

            order_id = response["order"]

            save_order(
                user_id=callback.from_user.id,
                seensms_order_id=order_id,
                platform=data["platform"],
                service=data["service_name"],
                quantity=data["quantity"],
                link=data["link"]
            )

            await callback.message.edit_text(
                "🎉 <b>BUYURTMA QABUL QILINDI!</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🆔 ID: <code>{order_id}</code>\n\n"
                f"🌐 {PLATFORMS[data['platform']]['name']}\n"
                f"🔢 Miqdor: <b>{data['quantity']:,}</b>\n\n"
                "⏳ Buyurtma bajarilishi boshlanadi.",
                reply_markup=main_menu()
            )

        else:

            error = (
                response.get("error")
                or response.get("message")
                if isinstance(response, dict)
                else "Noma'lum xatolik"
            )

            await callback.message.edit_text(
                "❌ <b>BUYURTMA BERILMADI</b>\n\n"
                f"📛 Sabab:\n"
                f"<code>{error}</code>",
                reply_markup=main_menu()
            )

    except Exception as error:

        logger.exception(
            "Order error: %s",
            error
        )

        await callback.message.edit_text(
            "❌ <b>Texnik xatolik!</b>\n\n"
            "SeenSMS API bilan aloqa bo‘lmadi.",
            reply_markup=main_menu()
        )

    await state.clear()
    await callback.answer()


# ============================================================
#                       BEKOR QILISH
# ============================================================

@dp.callback_query(
    F.data == "cancel_order"
)
async def cancel_order(
    callback: CallbackQuery,
    state: FSMContext
):

    await state.clear()

    await callback.message.edit_text(
        "❌ <b>BUYURTMA BEKOR QILINDI</b>\n\n"
        "Asosiy menyuga qaytdingiz.",
        reply_markup=main_menu()
    )

    await callback.answer()


# ============================================================
#                     BALANS
# ============================================================

@dp.callback_query(
    F.data == "balance"
)
async def user_balance(
    callback: CallbackQuery
):

    try:

        response = await get_balance()

        if isinstance(response, dict):

            balance_value = response.get(
                "balance",
                "Noma'lum"
            )

            currency = response.get(
                "currency",
                ""
            )

            text = (
                "💰 <b>BALANS</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"💳 Balans: "
                f"<b>{balance_value}</b>\n"
                f"💵 Valyuta: "
                f"<b>{currency}</b>"
            )

        else:

            text = (
                "❌ Balansni olishda xatolik."
            )

        await callback.message.edit_text(
            text,
            reply_markup=main_menu()
        )

    except Exception:

        await callback.message.edit_text(
            "❌ API bilan bog‘lanib bo‘lmadi.",
            reply_markup=main_menu()
        )

    await callback.answer()


# ============================================================
#                   SHAXSIY KABINET
# ============================================================

@dp.callback_query(
    F.data == "profile"
)
async def profile(
    callback: CallbackQuery
):

    user = callback.from_user

    username = (
        f"@{user.username}"
        if user.username
        else "Username yo‘q"
    )

    await callback.message.edit_text(
        "👤 <b>SHAXSIY KABINET</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"👤 Username: <b>{username}</b>\n"
        f"📛 Ism: <b>{user.first_name}</b>\n\n"
        "📦 Buyurtmalar: <b>Ko‘rilmoqda</b>\n\n"
        "✨ <b>Best1SMM</b>",
        reply_markup=main_menu()
    )

    await callback.answer()


# ============================================================
#                         YORDAM
# ============================================================

@dp.callback_query(
    F.data == "help"
)
async def help_handler(
    callback: CallbackQuery
):

    await callback.message.edit_text(
        "🆘 <b>YORDAM</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🛒 <b>Buyurtma berish</b>\n"
        "Platforma → tarif → miqdor → havola.\n\n"
        "💰 <b>Balans</b>\n"
        "Panel balansini ko‘rsatadi.\n\n"
        "👤 <b>Shaxsiy kabinet</b>\n"
        "Profil ma’lumotlaringiz.\n\n"
        f"👨‍💻 Admin: @{ADMIN_USERNAME}",
        reply_markup=main_menu()
    )

    await callback.answer()


# ============================================================
#                    ADMIN TEKSHIRUV
# ============================================================

def is_admin(user):

    return (
        user.username
        and
        user.username.lower()
        == ADMIN_USERNAME.lower()
    )


# ============================================================
#                     /ADMIN
# ============================================================

@dp.message(
    Command("admin")
)
async def admin_command(
    message: Message
):

    if not is_admin(
        message.from_user
    ):

        await message.answer(
            "⛔ Sizda admin panelga ruxsat yo‘q."
        )

        return

    await message.answer(
        "👑 <b>BEST1SMM ADMIN PANEL</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Xush kelibsiz, admin!\n\n"
        "👇 Kerakli bo‘limni tanlang:",
        reply_markup=admin_menu()
    )


# ============================================================
#                    ADMIN PANEL
# ============================================================

@dp.callback_query(
    F.data == "admin_panel"
)
async def admin_panel(
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

    await callback.message.edit_text(
        "👑 <b>BEST1SMM ADMIN PANEL</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "👇 Kerakli bo‘limni tanlang:",
        reply_markup=admin_menu()
    )

    await callback.answer()


# ============================================================
#                    ADMIN STATISTIKA
# ============================================================

@dp.callback_query(
    F.data == "admin_stats"
)
async def admin_stats(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user
    ):
        return

    users, orders = get_statistics()

    await callback.message.edit_text(
        "📊 <b>STATISTIKA</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Foydalanuvchilar: "
        f"<b>{users}</b>\n\n"
        f"📦 Buyurtmalar: "
        f"<b>{orders}</b>\n\n"
        f"👑 Admin: @{ADMIN_USERNAME}",
        reply_markup=admin_back()
    )

    await callback.answer()


# ============================================================
#                  ADMIN API BALANS
# ============================================================

@dp.callback_query(
    F.data == "admin_balance"
)
async def admin_balance(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user
    ):
        return

    await callback.message.edit_text(
        "⏳ <b>SeenSMS balans tekshirilmoqda...</b>"
    )

    try:

        response = await get_balance()

        if isinstance(response, dict):

            balance_value = response.get(
                "balance",
                "Noma'lum"
            )

            currency = response.get(
                "currency",
                ""
            )

            text = (
                "💰 <b>SEENSMS BALANS</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"💳 Balans: <b>{balance_value}</b>\n"
                f"💵 Valyuta: <b>{currency}</b>"
            )

        else:

            text = (
                "❌ API noto‘g‘ri javob qaytardi."
            )

        await callback.message.edit_text(
            text,
            reply_markup=admin_back()
        )

    except Exception as error:

        await callback.message.edit_text(
            "❌ <b>API xatosi!</b>\n\n"
            f"<code>{error}</code>",
            reply_markup=admin_back()
        )

    await callback.answer()


# ============================================================
#                    ADMIN API TEST
# ============================================================

@dp.callback_query(
    F.data == "admin_api"
)
async def admin_api(
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

        response = await get_services()

        if isinstance(
            response,
            list
        ):

            await callback.message.edit_text(
                "🟢 <b>API ISHLAYAPTI</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"⚡ Xizmatlar: "
                f"<b>{len(response)}</b>\n\n"
                "🔗 SeenSMS API ulanishi muvaffaqiyatli.",
                reply_markup=admin_back()
            )

        else:

            await callback.message.edit_text(
                "🟡 <b>API JAVOBI SHUBHALI</b>\n\n"
                "API ishladi, lekin kutilgan formatda "
                "javob qaytmadi.",
                reply_markup=admin_back()
            )

    except Exception as error:

        await callback.message.edit_text(
            "🔴 <b>API ISHLAMAYAPTI</b>\n\n"
            f"<code>{error}</code>",
            reply_markup=admin_back()
        )

    await callback.answer()


# ============================================================
#                  ADMIN USERS
# ============================================================

@dp.callback_query(
    F.data == "admin_users"
)
async def admin_users(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user
    ):
        return

    users, orders = get_statistics()

    await callback.message.edit_text(
        "👥 <b>FOYDALANUVCHILAR</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Jami foydalanuvchilar: "
        f"<b>{users}</b>\n\n"
        "Foydalanuvchilar bazaga avtomatik "
        "saqlanadi.",
        reply_markup=admin_back()
    )

    await callback.answer()


# ============================================================
#                  ADMIN ORDERS
# ============================================================

@dp.callback_query(
    F.data == "admin_orders"
)
async def admin_orders(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user
    ):
        return

    conn = sqlite3.connect(
        DB_NAME
    )

    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            seensms_order_id,
            user_id,
            platform,
            quantity,
            created_at
        FROM orders
        ORDER BY id DESC
        LIMIT 10
    """)

    rows = cursor.fetchall()

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

            order_id = row[0]
            user_id = row[1]
            platform = row[2]
            quantity_value = row[3]
            created = row[4]

            text += (
                f"🆔 <code>{order_id}</code>\n"
                f"👤 <code>{user_id}</code>\n"
                f"🌐 {platform}\n"
                f"🔢 {quantity_value:,}\n"
                f"🕐 {created}\n"
                "──────────────\n"
            )

    await callback.message.edit_text(
        text,
        reply_markup=admin_back()
    )

    await callback.answer()


# ============================================================
#                  ADMIN BROADCAST
# ============================================================

@dp.callback_query(
    F.data == "admin_broadcast"
)
async def admin_broadcast(
    callback: CallbackQuery,
    state: FSMContext
):

    if not is_admin(
        callback.from_user
    ):
        return

    await state.set_state(
        AdminState.broadcasting
    )

    await callback.message.edit_text(
        "📢 <b>REKLAMA YUBORISH</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Yubormoqchi bo‘lgan xabaringizni "
        "keyingi xabarda yuboring.\n\n"
        "⚠️ Xabar bot foydalanuvchilariga yuboriladi.",
        reply_markup=admin_back()
    )

    await callback.answer()


# ============================================================
#                 BROADCAST SEND
# ============================================================

@dp.message(
    AdminState.broadcasting
)
async def broadcast_send(
    message: Message,
    state: FSMContext
):

    if not is_admin(
        message.from_user
    ):

        await state.clear()
        return

    users = get_users()

    sent = 0
    failed = 0

    await message.answer(
        f"📢 <b>Yuborish boshlandi...</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{len(users)}</b>"
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
        f"❌ Yuborilmadi: <b>{failed}</b>",
        reply_markup=admin_menu()
    )


# ============================================================
#                       BACK MAIN
# ============================================================

@dp.callback_query(
    F.data == "back_main"
)
async def back_main(
    callback: CallbackQuery,
    state: FSMContext
):

    await state.clear()

    await callback.message.edit_text(
        "🏠 <b>BEST1SMM</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "👇 Kerakli bo‘limni tanlang:",
        reply_markup=main_menu()
    )

    await callback.answer()


# ============================================================
#                    BACK PLATFORMS
# ============================================================

@dp.callback_query(
    F.data == "back_platforms"
)
async def back_platforms(
    callback: CallbackQuery,
    state: FSMContext
):

    await state.set_state(
        OrderState.choosing_platform
    )

    await callback.message.edit_text(
        "🛒 <b>BUYURTMA BERISH</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🌐 Platformani tanlang:",
        reply_markup=platform_menu()
    )

    await callback.answer()


# ============================================================
#                       RUN
# ============================================================

async def main():

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN Render Environment Variables'da yo‘q!"
        )

    if not SEENSMS_API_KEY:
        raise RuntimeError(
            "SEENSMS_API_KEY Render Environment Variables'da yo‘q!"
        )

    init_db()

    logger.info(
        "🚀 Best1SMM ishga tushdi"
    )

    await bot.delete_webhook(
        drop_pending_updates=True
    )

    await dp.start_polling(
        bot
    )


if __name__ == "__main__":

    asyncio.run(main())
