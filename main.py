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
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


# =========================================================
#                    SOZLAMALAR
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "BOT_TOKENINGIZNI_SHU_YERGA")
SEEN_SMS_API_KEY = os.getenv("SEENSMS_API_KEY", "SEENSMS_API_KEYINGIZNI_SHU_YERGA")

API_URL = "https://seensms.uz/api/v1"

ADMIN_USERNAME = "rxk_17"

# Faqat kerakli platformalar
PLATFORMS = {
    "instagram": {
        "name": "📸 Instagram",
        "keywords": ["instagram", "insta"],
    },
    "tiktok": {
        "name": "🎵 TikTok",
        "keywords": ["tiktok", "tik tok"],
    },
    "youtube": {
        "name": "▶️ YouTube",
        "keywords": ["youtube", "youtu.be"],
    },
    "telegram": {
        "name": "✈️ Telegram",
        "keywords": ["telegram", "tg "],
    },
}


# =========================================================
#                       LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


# =========================================================
#                     BOT / DISPATCHER
# =========================================================

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher(storage=MemoryStorage())


# =========================================================
#                       FSM STATES
# =========================================================

class OrderState(StatesGroup):
    choosing_platform = State()
    choosing_service = State()
    entering_link = State()
    entering_quantity = State()
    confirming = State()


# =========================================================
#                    API FUNKSIYALARI
# =========================================================

async def seensms_request(data: dict) -> Any:
    """
    SeenSMS API bilan aloqa.
    """

    if not SEEN_SMS_API_KEY or "SEENSMS_API_KEYINGIZ" in SEEN_SMS_API_KEY:
        raise RuntimeError(
            "SeenSMS API key sozlanmagan."
        )

    payload = {
        "key": SEEN_SMS_API_KEY,
        **data
    }

    timeout = aiohttp.ClientTimeout(total=20)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(API_URL, data=payload) as response:

                text = await response.text()

                if response.status != 200:
                    raise RuntimeError(
                        f"API HTTP xatosi: {response.status}"
                    )

                try:
                    return await response.json()
                except Exception:
                    raise RuntimeError(
                        f"API noto'g'ri javob qaytardi: {text[:500]}"
                    )

    except asyncio.TimeoutError:
        raise RuntimeError("API javob berish uchun juda uzoq vaqt oldi.")

    except aiohttp.ClientError as e:
        raise RuntimeError(f"API ulanish xatosi: {e}")


async def get_services():
    """
    SeenSMS xizmatlarini olish.
    """
    return await seensms_request({
        "action": "services"
    })


async def add_order(service_id: int, link: str, quantity: int):
    """
    Buyurtma berish.
    """
    return await seensms_request({
        "action": "add",
        "service": service_id,
        "link": link,
        "quantity": quantity,
    })


async def get_balance():
    """
    SeenSMS balansini olish.
    """
    return await seensms_request({
        "action": "balance"
    })


async def get_order_status(order_id: int):
    """
    Buyurtma holatini olish.
    """
    return await seensms_request({
        "action": "status",
        "order": order_id,
    })


# =========================================================
#                     YORDAMCHI FUNKSIYALAR
# =========================================================

def main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="🛒 Buyurtma berish",
            callback_data="new_order"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="📦 Buyurtmam",
            callback_data="my_order"
        ),
        InlineKeyboardButton(
            text="💰 Balans",
            callback_data="balance"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="ℹ️ Yordam",
            callback_data="help"
        )
    )

    return builder.as_markup()


def platform_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for key, info in PLATFORMS.items():
        builder.add(
            InlineKeyboardButton(
                text=info["name"],
                callback_data=f"platform:{key}"
            )
        )

    builder.adjust(2)

    builder.row(
        InlineKeyboardButton(
            text="🔙 Orqaga",
            callback_data="back_main"
        )
    )

    return builder.as_markup()


def services_keyboard(services: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for service in services[:50]:

        service_id = service.get("service")
        name = str(service.get("name", "Noma'lum xizmat"))

        # Tugma juda uzun bo'lib ketmasligi uchun
        if len(name) > 55:
            name = name[:52] + "..."

        builder.add(
            InlineKeyboardButton(
                text=f"⚡ {name}",
                callback_data=f"service:{service_id}"
            )
        )

    builder.adjust(1)

    builder.row(
        InlineKeyboardButton(
            text="🔙 Platformalar",
            callback_data="new_order"
        )
    )

    return builder.as_markup()


def normalize(text: str) -> str:
    return text.lower().strip()


def service_belongs_to_platform(service: dict, platform: str) -> bool:
    """
    Xizmat nomi/kategoriyasi bo'yicha platformani aniqlaydi.
    """

    info = PLATFORMS.get(platform)

    if not info:
        return False

    name = normalize(str(service.get("name", "")))
    category = normalize(str(service.get("category", "")))

    full_text = f"{name} {category}"

    for keyword in info["keywords"]:
        if keyword in full_text:
            return True

    return False


def safe_int(value):
    try:
        return int(float(str(value)))
    except Exception:
        return None


def format_price(rate, quantity):
    try:
        r = float(rate)
        q = int(quantity)

        return r * q / 1000

    except Exception:
        return 0


# =========================================================
#                        START
# =========================================================

@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):

    await state.clear()

    user = message.from_user

    text = (
        "✨ <b>Best1SMM</b>\n\n"
        "🚀 SMM xizmatlarining qulay paneli\n\n"
        "📸 Instagram\n"
        "🎵 TikTok\n"
        "▶️ YouTube\n"
        "✈️ Telegram\n\n"
        "👇 Kerakli bo‘limni tanlang:"
    )

    await message.answer(
        text,
        reply_markup=main_menu()
    )


# =========================================================
#                    BUYURTMA BOSHLASH
# =========================================================

@dp.callback_query(F.data == "new_order")
async def new_order_callback(
    callback: CallbackQuery,
    state: FSMContext
):

    await state.set_state(OrderState.choosing_platform)

    await callback.message.edit_text(
        "🛒 <b>Yangi buyurtma</b>\n\n"
        "1️⃣ Platformani tanlang:",
        reply_markup=platform_keyboard()
    )

    await callback.answer()


# =========================================================
#                     PLATFORM TANLASH
# =========================================================

@dp.callback_query(
    OrderState.choosing_platform,
    F.data.startswith("platform:")
)
async def platform_selected(
    callback: CallbackQuery,
    state: FSMContext
):

    platform = callback.data.split(":", 1)[1]

    if platform not in PLATFORMS:
        await callback.answer(
            "❌ Platforma topilmadi.",
            show_alert=True
        )
        return

    await state.update_data(platform=platform)

    await callback.message.edit_text(
        "⏳ <b>Xizmatlar yuklanmoqda...</b>"
    )

    try:
        response = await get_services()

        if not isinstance(response, list):
            await callback.message.edit_text(
                "❌ SeenSMS API xizmatlar ro‘yxatini noto‘g‘ri qaytardi.\n\n"
                f"<code>{response}</code>",
                reply_markup=main_menu()
            )
            await callback.answer()
            return

        filtered = [
            service
            for service in response
            if service_belongs_to_platform(
                service,
                platform
            )
        ]

        if not filtered:
            await callback.message.edit_text(
                f"😔 <b>{PLATFORMS[platform]['name']}</b> uchun "
                "hozircha xizmat topilmadi.\n\n"
                "Administrator xizmatlarni tekshirishi kerak.",
                reply_markup=platform_keyboard()
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
            f"{PLATFORMS[platform]['name']}\n\n"
            "2️⃣ <b>Xizmatni tanlang:</b>",
            reply_markup=services_keyboard(filtered)
        )

    except Exception as e:

        logger.exception("Services error")

        await callback.message.edit_text(
            "❌ <b>Xatolik yuz berdi.</b>\n\n"
            "SeenSMS API bilan bog‘lanib bo‘lmadi.\n"
            "Bir ozdan keyin qayta urinib ko‘ring.",
            reply_markup=main_menu()
        )

    await callback.answer()


# =========================================================
#                      XIZMAT TANLASH
# =========================================================

@dp.callback_query(
    OrderState.choosing_service,
    F.data.startswith("service:")
)
async def service_selected(
    callback: CallbackQuery,
    state: FSMContext
):

    service_id = callback.data.split(":", 1)[1]

    data = await state.get_data()

    services = data.get("available_services", [])

    selected = None

    for service in services:

        if str(service.get("service")) == str(service_id):
            selected = service
            break

    if not selected:

        await callback.answer(
            "❌ Xizmat topilmadi.",
            show_alert=True
        )
        return

    await state.update_data(
        service_id=service_id,
        service_name=selected.get("name", "Noma'lum"),
        service_rate=selected.get("rate"),
        service_min=selected.get("min"),
        service_max=selected.get("max"),
    )

    min_count = selected.get("min", "?")
    max_count = selected.get("max", "?")

    await state.set_state(
        OrderState.entering_link
    )

    await callback.message.edit_text(
        "🔗 <b>Havolani yuboring</b>\n\n"
        f"⚡ Xizmat: <b>{selected.get('name')}</b>\n"
        f"📊 Minimum: <b>{min_count}</b>\n"
        f"📈 Maximum: <b>{max_count}</b>\n\n"
        "Masalan:\n"
        "<code>https://instagram.com/...</code>\n\n"
        "👇 Havolani yuboring:"
    )

    await callback.answer()


# =========================================================
#                       LINK QABUL QILISH
# =========================================================

@dp.message(OrderState.entering_link)
async def link_handler(
    message: Message,
    state: FSMContext
):

    link = message.text.strip() if message.text else ""

    if not link:
        await message.answer(
            "❌ Havola bo‘sh bo‘lishi mumkin emas.\n\n"
            "🔗 Havolani qayta yuboring."
        )
        return

    if not (
        link.startswith("https://")
        or link.startswith("http://")
    ):
        await message.answer(
            "❌ <b>Noto‘g‘ri havola.</b>\n\n"
            "Havola <code>https://</code> bilan boshlanishi kerak."
        )
        return

    data = await state.get_data()

    platform = data.get("platform")

    # Platformaga mos linkni tekshirish
    domains = {
        "instagram": ["instagram.com"],
        "tiktok": ["tiktok.com"],
        "youtube": ["youtube.com", "youtu.be"],
        "telegram": ["t.me", "telegram.me", "telegram.org"],
    }

    if platform in domains:
        if not any(
            domain in link.lower()
            for domain in domains[platform]
        ):
            await message.answer(
                f"❌ Bu havola <b>"
                f"{PLATFORMS[platform]['name']}</b> uchun mos emas.\n\n"
                "🔗 To‘g‘ri havolani yuboring."
            )
            return

    await state.update_data(link=link)

    await state.set_state(
        OrderState.entering_quantity
    )

    await message.answer(
        "🔢 <b>Soni</b>\n\n"
        f"Minimal: <b>{data.get('service_min')}</b>\n"
        f"Maksimal: <b>{data.get('service_max')}</b>\n\n"
        "Nechta kerakligini faqat son ko‘rinishida yuboring.\n\n"
        "Masalan: <code>1000</code>"
    )


# =========================================================
#                       SON QABUL QILISH
# =========================================================

@dp.message(OrderState.entering_quantity)
async def quantity_handler(
    message: Message,
    state: FSMContext
):

    text = message.text.strip() if message.text else ""

    if not text.isdigit():
        await message.answer(
            "❌ Faqat <b>son</b> yuboring.\n\n"
            "Masalan: <code>1000</code>"
        )
        return

    quantity = int(text)

    data = await state.get_data()

    minimum = safe_int(data.get("service_min"))
    maximum = safe_int(data.get("service_max"))

    if minimum is not None and quantity < minimum:
        await message.answer(
            f"❌ Juda kam.\n\n"
            f"Minimum: <b>{minimum}</b>"
        )
        return

    if maximum is not None and quantity > maximum:
        await message.answer(
            f"❌ Juda ko‘p.\n\n"
            f"Maksimum: <b>{maximum}</b>"
        )
        return

    price = format_price(
        data.get("service_rate"),
        quantity
    )

    await state.update_data(
        quantity=quantity,
        calculated_price=price
    )

    await state.set_state(
        OrderState.confirming
    )

    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="✅ BUYURTMA BERISH",
            callback_data="confirm_order"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="❌ Bekor qilish",
            callback_data="cancel_order"
        )
    )

    await message.answer(
        "🧾 <b>BUYURTMA TASDIG‘I</b>\n\n"
        f"🌐 Platforma: <b>"
        f"{PLATFORMS[data.get('platform')]['name']}</b>\n"
        f"⚡ Xizmat: <b>{data.get('service_name')}</b>\n"
        f"🔗 Havola: <code>{data.get('link')}</code>\n"
        f"🔢 Soni: <b>{quantity:,}</b>\n"
        f"💰 Taxminiy narx: <b>{price:,.2f}</b>\n\n"
        "⚠️ Ma’lumotlarni tekshirib, tasdiqlang:",
        reply_markup=builder.as_markup()
    )


# =========================================================
#                    BUYURTMANI TASDIQLASH
# =========================================================

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
        "⏳ <b>Buyurtma yuborilmoqda...</b>\n\n"
        "🔄 SeenSMS API bilan bog‘lanilmoqda."
    )

    try:

        response = await add_order(
            service_id=int(data["service_id"]),
            link=data["link"],
            quantity=int(data["quantity"])
        )

        logger.info("Add order response: %s", response)

        if isinstance(response, dict) and response.get("order"):

            order_id = response["order"]

            await state.update_data(
                order_id=order_id
            )

            await callback.message.edit_text(
                "🎉 <b>BUYURTMA QABUL QILINDI!</b>\n\n"
                f"🆔 Buyurtma ID: <code>{order_id}</code>\n"
                f"📱 Platforma: <b>"
                f"{PLATFORMS[data['platform']]['name']}</b>\n"
                f"⚡ Xizmat: <b>{data['service_name']}</b>\n"
                f"🔢 Soni: <b>{data['quantity']:,}</b>\n\n"
                "⏳ Buyurtma tez orada bajarila boshlaydi.",
                reply_markup=main_menu()
            )

        else:

            error_text = "Noma'lum API xatosi."

            if isinstance(response, dict):
                error_text = (
                    response.get("error")
                    or response.get("message")
                    or str(response)
                )

            await callback.message.edit_text(
                "❌ <b>BUYURTMA BERILMADI</b>\n\n"
                f"Sabab:\n<code>{error_text}</code>\n\n"
                "💡 Balans, xizmat limiti yoki havolani tekshiring.",
                reply_markup=main_menu()
            )

    except Exception as e:

        logger.exception("Order error")

        await callback.message.edit_text(
            "❌ <b>Texnik xatolik.</b>\n\n"
            "Buyurtma yuborilmadi.\n"
            "Iltimos, qayta urinib ko‘ring.",
            reply_markup=main_menu()
        )

    await state.clear()
    await callback.answer()


# =========================================================
#                         CANCEL
# =========================================================

@dp.callback_query(F.data == "cancel_order")
async def cancel_order(
    callback: CallbackQuery,
    state: FSMContext
):

    await state.clear()

    await callback.message.edit_text(
        "❌ <b>Buyurtma bekor qilindi.</b>\n\n"
        "Asosiy menyu:",
        reply_markup=main_menu()
    )

    await callback.answer()


# =========================================================
#                         BALANCE
# =========================================================

@dp.callback_query(F.data == "balance")
async def balance_callback(
    callback: CallbackQuery
):

    try:

        response = await get_balance()

        if isinstance(response, dict):

            balance = response.get("balance", "Noma'lum")
            currency = response.get("currency", "UZS")

            await callback.message.edit_text(
                "💰 <b>SeenSMS balans</b>\n\n"
                f"💳 Balans: <b>{balance}</b>\n"
                f"💵 Valyuta: <b>{currency}</b>",
                reply_markup=main_menu()
            )

        else:

            await callback.message.edit_text(
                "❌ Balansni olishda xatolik.",
                reply_markup=main_menu()
            )

    except Exception:

        logger.exception("Balance error")

        await callback.message.edit_text(
            "❌ SeenSMS API bilan aloqa bo‘lmadi.",
            reply_markup=main_menu()
        )

    await callback.answer()


# =========================================================
#                       MY ORDER
# =========================================================

@dp.callback_query(F.data == "my_order")
async def my_order_callback(
    callback: CallbackQuery,
    state: FSMContext
):

    data = await state.get_data()

    order_id = data.get("order_id")

    if not order_id:

        await callback.message.edit_text(
            "📦 <b>Buyurtmam</b>\n\n"
            "Hozirgi sessiyada saqlangan buyurtma topilmadi.",
            reply_markup=main_menu()
        )

        await callback.answer()
        return

    try:

        response = await get_order_status(
            int(order_id)
        )

        if isinstance(response, dict):

            status = response.get(
                "status",
                "Noma'lum"
            )

            remains = response.get(
                "remains",
                "Noma'lum"
            )

            start_count = response.get(
                "start_count",
                "Noma'lum"
            )

            await callback.message.edit_text(
                "📦 <b>BUYURTMA HOLATI</b>\n\n"
                f"🆔 ID: <code>{order_id}</code>\n"
                f"📊 Holat: <b>{status}</b>\n"
                f"🚀 Boshlang‘ich: <b>{start_count}</b>\n"
                f"📉 Qoldiq: <b>{remains}</b>",
                reply_markup=main_menu()
            )

        else:

            await callback.message.edit_text(
                "❌ Buyurtma holatini olishda xatolik.",
                reply_markup=main_menu()
            )

    except Exception:

        logger.exception("Status error")

        await callback.message.edit_text(
            "❌ API bilan bog‘lanib bo‘lmadi.",
            reply_markup=main_menu()
        )

    await callback.answer()


# =========================================================
#                          HELP
# =========================================================

@dp.callback_query(F.data == "help")
async def help_callback(
    callback: CallbackQuery
):

    await callback.message.edit_text(
        "ℹ️ <b>Best1SMM yordam</b>\n\n"
        "🛒 <b>Buyurtma berish</b> — xizmat tanlab buyurtma berasiz.\n\n"
        "📦 <b>Buyurtmam</b> — oxirgi buyurtma holatini ko‘rasiz.\n\n"
        "💰 <b>Balans</b> — SeenSMS API balansini ko‘rasiz.\n\n"
        "⚠️ Buyurtma berishda faqat ochiq va to‘g‘ri "
        "havolalardan foydalaning.\n\n"
        f"👨‍💻 Admin: @{ADMIN_USERNAME}",
        reply_markup=main_menu()
    )

    await callback.answer()


# =========================================================
#                         BACK
# =========================================================

@dp.callback_query(F.data == "back_main")
async def back_main(
    callback: CallbackQuery,
    state: FSMContext
):

    await state.clear()

    await callback.message.edit_text(
        "🏠 <b>Best1SMM</b>\n\n"
        "👇 Kerakli bo‘limni tanlang:",
        reply_markup=main_menu()
    )

    await callback.answer()


# =========================================================
#                   NOMA'LUM BUYRUQLAR
# =========================================================

@dp.message()
async def unknown_message(message: Message):

    await message.answer(
        "🤖 <b>Best1SMM</b>\n\n"
        "Kerakli bo‘limni tugmalar orqali tanlang:",
        reply_markup=main_menu()
    )


# =========================================================
#                         START BOT
# =========================================================

async def main():

    logger.info("Best1SMM bot ishga tushmoqda...")

    await bot.delete_webhook(
        drop_pending_updates=True
    )

    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        logger.info("Bot to'xtatildi.")
