import asyncio
import logging
import os
from typing import Any

import aiohttp

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


# ============================================================
#                    SOZLAMALAR
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
SEENSMS_API_KEY = os.getenv("SEENSMS_API_KEY")

SEENSMS_API_URL = "https://seensms.uz/api/v1"

ADMIN_USERNAME = "rxk_17"


# ============================================================
#                       LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("Best1SMM")


# ============================================================
#                    BOT / DISPATCHER
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
#                         STATES
# ============================================================

class OrderState(StatesGroup):
    choosing_platform = State()
    choosing_service = State()
    entering_quantity = State()
    entering_link = State()
    confirming = State()


# ============================================================
#                       PLATFORMS
# ============================================================

PLATFORMS = {
    "youtube": {
        "name": "▶️ YouTube",
        "keywords": ["youtube", "youtu.be"],
        "domains": ["youtube.com", "youtu.be"],
    },

    "telegram": {
        "name": "✈️ Telegram",
        "keywords": ["telegram", "t.me"],
        "domains": ["t.me", "telegram.me"],
    },

    "instagram": {
        "name": "📸 Instagram",
        "keywords": ["instagram", "insta"],
        "domains": ["instagram.com"],
    },

    "tiktok": {
        "name": "🎵 TikTok",
        "keywords": ["tiktok", "tik tok"],
        "domains": ["tiktok.com"],
    },
}


# ============================================================
#                    ASOSIY MENYU
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
#                 PLATFORMALAR MENYUSI
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


# ============================================================
#                  BEKOR / ORQAGA
# ============================================================

def back_order_menu():

    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="🔙 Orqaga",
            callback_data="back_platforms"
        )
    )

    return builder.as_markup()


def cancel_menu():

    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="❌ Bekor qilish",
            callback_data="cancel_order"
        )
    )

    return builder.as_markup()


# ============================================================
#                   TASDIQLASH MENYUSI
# ============================================================

def confirm_menu():

    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="✅ Buyurtma berish",
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
#                     SEENSMS API
# ============================================================

async def seensms_request(
    data: dict
) -> Any:

    if not SEENSMS_API_KEY:
        raise RuntimeError(
            "SEENSMS_API_KEY Render Environment Variables'da topilmadi."
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
                    f"SeenSMS HTTP error: {response.status}"
                )

            try:
                return await response.json()
            except Exception:
                raise RuntimeError(
                    f"SeenSMS JSON xatosi: {text[:500]}"
                )


async def get_services():

    return await seensms_request({
        "action": "services"
    })


async def add_order(
    service_id: int,
    link: str,
    quantity: int
):

    return await seensms_request({
        "action": "add",
        "service": service_id,
        "link": link,
        "quantity": quantity,
    })


async def get_balance():

    return await seensms_request({
        "action": "balance"
    })


async def get_order_status(
    order_id: int
):

    return await seensms_request({
        "action": "status",
        "order": order_id,
    })


# ============================================================
#                    YORDAMCHI FUNKSIYALAR
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
        return float(rate) * int(quantity) / 1000
    except Exception:
        return 0


def service_matches_platform(
    service: dict,
    platform: str
):

    platform_info = PLATFORMS.get(platform)

    if not platform_info:
        return False

    name = normalize(
        service.get("name", "")
    )

    category = normalize(
        service.get("category", "")
    )

    text = f"{name} {category}"

    return any(
        keyword in text
        for keyword in platform_info["keywords"]
    )


# ============================================================
#                  XIZMATLAR TUGMALARI
# ============================================================

def services_menu(services):

    builder = InlineKeyboardBuilder()

    for service in services:

        service_id = service.get("service")

        name = str(
            service.get(
                "name",
                "Noma'lum xizmat"
            )
        )

        if len(name) > 55:
            name = name[:52] + "..."

        builder.row(
            InlineKeyboardButton(
                text=f"⚡ {name}",
                callback_data=f"service:{service_id}"
            )
        )

    builder.row(
        InlineKeyboardButton(
            text="🔙 Platformalar",
            callback_data="back_platforms"
        )
    )

    return builder.as_markup()


# ============================================================
#                         START
# ============================================================

@dp.message(CommandStart())
async def start_handler(
    message: Message,
    state: FSMContext
):

    await state.clear()

    text = (
        "✨ <b>BEST1SMM</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🚀 SMM xizmatlarining zamonaviy paneli\n\n"
        "📈 Tezkor buyurtmalar\n"
        "💎 Qulay narxlar\n"
        "⚡ Avtomatik xizmat\n\n"
        "👇 <b>Kerakli bo‘limni tanlang:</b>"
    )

    await message.answer(
        text,
        reply_markup=main_menu()
    )


# ============================================================
#                   BUYURTMA BERISH
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
        "🌐 Kerakli platformani tanlang:\n\n"
        "👇 Quyidagilardan birini tanlang:",
        reply_markup=platform_menu()
    )

    await callback.answer()


# ============================================================
#                    PLATFORM TANLASH
# ============================================================

@dp.callback_query(
    OrderState.choosing_platform,
    F.data.startswith("platform:")
)
async def choose_platform(
    callback: CallbackQuery,
    state: FSMContext
):

    platform = callback.data.split(":", 1)[1]

    if platform not in PLATFORMS:

        await callback.answer(
            "❌ Platforma topilmadi!",
            show_alert=True
        )

        return

    await state.update_data(
        platform=platform
    )

    await callback.message.edit_text(
        "⏳ <b>Tariflar yuklanmoqda...</b>\n\n"
        "🔄 Iltimos, biroz kuting..."
    )

    try:

        services = await get_services()

        if not isinstance(services, list):

            await callback.message.edit_text(
                "❌ <b>Tariflarni olishda xatolik!</b>\n\n"
                "SeenSMS API noto‘g‘ri javob qaytardi.",
                reply_markup=platform_menu()
            )

            await callback.answer()
            return

        filtered = [
            service
            for service in services
            if service_matches_platform(
                service,
                platform
            )
        ]

        if not filtered:

            await callback.message.edit_text(
                f"😔 <b>"
                f"{PLATFORMS[platform]['name']}"
                f"</b> uchun tarif topilmadi.\n\n"
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
            "⚡ <b>Tarifni tanlang:</b>\n\n"
            "👇 Kerakli xizmatni bosing:",
            reply_markup=services_menu(filtered)
        )

    except Exception as error:

        logger.exception(
            "Services error: %s",
            error
        )

        await callback.message.edit_text(
            "❌ <b>Texnik xatolik!</b>\n\n"
            "Tariflarni yuklab bo‘lmadi.\n"
            "Keyinroq qayta urinib ko‘ring.",
            reply_markup=platform_menu()
        )

    await callback.answer()


# ============================================================
#                      TARIF TANLASH
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

    services = data.get(
        "available_services",
        []
    )

    selected = None

    for service in services:

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
            "Noma'lum xizmat"
        ),
        service_rate=selected.get("rate"),
        service_min=selected.get("min"),
        service_max=selected.get("max")
    )

    await state.set_state(
        OrderState.entering_quantity
    )

    await callback.message.edit_text(
        "🔢 <b>MIQDORNI KIRITING</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⚡ <b>{selected.get('name')}</b>\n\n"
        f"📊 Minimum: <b>{selected.get('min')}</b>\n"
        f"📈 Maximum: <b>{selected.get('max')}</b>\n\n"
        "💡 Masalan: <code>1000</code>\n\n"
        "👇 Nechta kerakligini yozing:",
        reply_markup=cancel_menu()
    )

    await callback.answer()


# ============================================================
#                     MIQDOR KIRITISH
# ============================================================

@dp.message(
    OrderState.entering_quantity
)
async def enter_quantity(
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
            "❌ <b>Noto‘g‘ri miqdor!</b>\n\n"
            "Faqat raqam kiriting.\n\n"
            "Masalan: <code>1000</code>",
            reply_markup=cancel_menu()
        )

        return

    quantity = int(value)

    data = await state.get_data()

    minimum = safe_int(
        data.get("service_min")
    )

    maximum = safe_int(
        data.get("service_max")
    )

    if minimum is not None and quantity < minimum:

        await message.answer(
            f"❌ <b>Miqdor juda kam!</b>\n\n"
            f"📊 Minimum: <b>{minimum}</b>\n\n"
            "Qaytadan kiriting:",
            reply_markup=cancel_menu()
        )

        return

    if maximum is not None and quantity > maximum:

        await message.answer(
            f"❌ <b>Miqdor juda ko‘p!</b>\n\n"
            f"📈 Maximum: <b>{maximum}</b>\n\n"
            "Qaytadan kiriting:",
            reply_markup=cancel_menu()
        )

        return

    price = calculate_price(
        data.get("service_rate"),
        quantity
    )

    await state.update_data(
        quantity=quantity,
        calculated_price=price
    )

    await state.set_state(
        OrderState.entering_link
    )

    await message.answer(
        "🔗 <b>HAVOLANI KIRITING</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔢 Miqdor: <b>{quantity:,}</b>\n"
        f"💰 Taxminiy narx: <b>{price:,.2f}</b>\n\n"
        "📎 Buyurtma beriladigan havolani yuboring.\n\n"
        "Masalan:\n"
        "<code>https://instagram.com/...</code>\n\n"
        "👇 Havolani yuboring:",
        reply_markup=back_order_menu()
    )


# ============================================================
#                     HAVOLA KIRITISH
# ============================================================

@dp.message(
    OrderState.entering_link
)
async def enter_link(
    message: Message,
    state: FSMContext
):

    link = (
        message.text.strip()
        if message.text
        else ""
    )

    if not link:

        await message.answer(
            "❌ Havola bo‘sh bo‘lishi mumkin emas!",
            reply_markup=back_order_menu()
        )

        return

    if not (
        link.startswith("https://")
        or link.startswith("http://")
    ):

        await message.answer(
            "❌ <b>Noto‘g‘ri havola!</b>\n\n"
            "Havola <code>https://</code> "
            "yoki <code>http://</code> bilan "
            "boshlanishi kerak.",
            reply_markup=back_order_menu()
        )

        return

    data = await state.get_data()

    platform = data.get(
        "platform"
    )

    domains = PLATFORMS[platform]["domains"]

    if not any(
        domain in link.lower()
        for domain in domains
    ):

        await message.answer(
            f"❌ <b>Havola noto‘g‘ri platformaga tegishli!</b>\n\n"
            f"Tanlangan platforma: "
            f"<b>{PLATFORMS[platform]['name']}</b>\n\n"
            "To‘g‘ri havolani yuboring.",
            reply_markup=back_order_menu()
        )

        return

    await state.update_data(
        link=link
    )

    await state.set_state(
        OrderState.confirming
    )

    price = data.get(
        "calculated_price",
        0
    )

    await message.answer(
        "🧾 <b>BUYURTMA MA'LUMOTLARI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🌐 Platforma:\n"
        f"<b>{PLATFORMS[platform]['name']}</b>\n\n"
        f"⚡ Tarif:\n"
        f"<b>{data.get('service_name')}</b>\n\n"
        f"🔢 Miqdor:\n"
        f"<b>{data.get('quantity'):,}</b>\n\n"
        f"🔗 Havola:\n"
        f"<code>{link}</code>\n\n"
        f"💰 Narx:\n"
        f"<b>{price:,.2f}</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👇 Hammasi to‘g‘ri bo‘lsa tasdiqlang:",
        reply_markup=confirm_menu()
    )


# ============================================================
#                HAVOLADAN ORQAGA QAYTISH
# ============================================================

@dp.callback_query(
    OrderState.entering_link,
    F.data == "back_platforms"
)
async def back_from_link(
    callback: CallbackQuery,
    state: FSMContext
):

    data = await state.get_data()

    platform = data.get(
        "platform"
    )

    services = data.get(
        "available_services",
        []
    )

    await state.set_state(
        OrderState.choosing_service
    )

    await callback.message.edit_text(
        f"{PLATFORMS[platform]['name']}\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "⚡ <b>Tarifni tanlang:</b>",
        reply_markup=services_menu(services)
    )

    await callback.answer()


# ============================================================
#                 TASDIQLASHDAN ORQAGA
# ============================================================

@dp.callback_query(
    OrderState.confirming,
    F.data == "back_link"
)
async def back_from_confirm(
    callback: CallbackQuery,
    state: FSMContext
):

    data = await state.get_data()

    await state.set_state(
        OrderState.entering_link
    )

    await callback.message.edit_text(
        "🔗 <b>HAVOLANI KIRITING</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔢 Miqdor: "
        f"<b>{data.get('quantity'):,}</b>\n\n"
        "👇 Havolani qaytadan yuboring:",
        reply_markup=back_order_menu()
    )

    await callback.answer()


# ============================================================
#                   BUYURTMA TASDIQLASH
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

        logger.info(
            "Order response: %s",
            response
        )

        if (
            isinstance(response, dict)
            and response.get("order")
        ):

            order_id = response["order"]

            await state.update_data(
                order_id=order_id
            )

            await callback.message.edit_text(
                "🎉 <b>BUYURTMA QABUL QILINDI!</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🆔 Buyurtma ID:\n"
                f"<code>{order_id}</code>\n\n"
                f"🌐 Platforma: "
                f"<b>{PLATFORMS[data['platform']]['name']}</b>\n\n"
                f"🔢 Miqdor: "
                f"<b>{data['quantity']:,}</b>\n\n"
                "⚡ Buyurtma tizimga yuborildi.\n"
                "⏳ Bajarilishi tez orada boshlanadi.\n\n"
                "✨ <b>Best1SMM</b>",
                reply_markup=main_menu()
            )

        else:

            if isinstance(response, dict):

                error = (
                    response.get("error")
                    or response.get("message")
                    or "Noma'lum xatolik"
                )

            else:

                error = "Noma'lum API xatosi"

            await callback.message.edit_text(
                "❌ <b>BUYURTMA BERILMADI</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📛 Sabab:\n"
                f"<code>{error}</code>\n\n"
                "Qaytadan urinib ko‘rishingiz mumkin.",
                reply_markup=main_menu()
            )

    except Exception as error:

        logger.exception(
            "Order error: %s",
            error
        )

        await callback.message.edit_text(
            "❌ <b>Texnik xatolik!</b>\n\n"
            "SeenSMS API bilan bog‘lanib bo‘lmadi.\n"
            "Keyinroq qayta urinib ko‘ring.",
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
#                       BALANS
# ============================================================

@dp.callback_query(
    F.data == "balance"
)
async def balance(
    callback: CallbackQuery
):

    await callback.message.edit_text(
        "⏳ <b>Balans tekshirilmoqda...</b>"
    )

    try:

        response = await get_balance()

        if isinstance(response, dict):

            value = response.get(
                "balance",
                "Noma'lum"
            )

            currency = response.get(
                "currency",
                ""
            )

            await callback.message.edit_text(
                "💰 <b>BALANS</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"💳 Balans: <b>{value}</b>\n"
                f"💵 Valyuta: <b>{currency}</b>",
                reply_markup=main_menu()
            )

        else:

            await callback.message.edit_text(
                "❌ Balansni olib bo‘lmadi.",
                reply_markup=main_menu()
            )

    except Exception as error:

        logger.exception(
            "Balance error: %s",
            error
        )

        await callback.message.edit_text(
            "❌ <b>API xatosi!</b>\n\n"
            "Balansni olib bo‘lmadi.",
            reply_markup=main_menu()
        )

    await callback.answer()


# ============================================================
#                  SHAXSIY KABINET
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
        "📦 Buyurtmalar: <b>—</b>\n"
        "💰 Balans: <b>—</b>\n\n"
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
        "Kerakli platforma va tarifni tanlang.\n"
        "Keyin miqdor va havolani kiriting.\n\n"
        "💰 <b>Balans</b>\n"
        "Panel balansini ko‘rish.\n\n"
        "👤 <b>Shaxsiy kabinet</b>\n"
        "Profil ma’lumotlarini ko‘rish.\n\n"
        f"👨‍💻 Admin: @{ADMIN_USERNAME}",
        reply_markup=main_menu()
    )

    await callback.answer()


# ============================================================
#                      ASOSIY MENYUGA
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
#                  PLATFORMALARGA ORQAGA
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
#                    UNKNOWN MESSAGE
# ============================================================

@dp.message()
async def unknown_message(
    message: Message
):

    await message.answer(
        "🤖 <b>BEST1SMM</b>\n\n"
        "Kerakli bo‘limni tugmalar orqali tanlang:",
        reply_markup=main_menu()
    )


# ============================================================
#                       RUN BOT
# ============================================================

async def main():

    if not BOT_TOKEN:

        raise RuntimeError(
            "❌ Render'da BOT_TOKEN Environment Variable "
            "topilmadi!"
        )

    if not SEENSMS_API_KEY:

        raise RuntimeError(
            "❌ Render'da SEENSMS_API_KEY Environment Variable "
            "topilmadi!"
        )

    logger.info(
        "🚀 Best1SMM ishga tushmoqda..."
    )

    await bot.delete_webhook(
        drop_pending_updates=True
    )

    await dp.start_polling(
        bot
    )


if __name__ == "__main__":

    try:

        asyncio.run(main())

    except KeyboardInterrupt:

        logger.info(
            "Bot to‘xtatildi."
)
