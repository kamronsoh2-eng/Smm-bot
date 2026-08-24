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
from aiogram.types import Message, CallbackQuery
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


# ============================================================
#                    BEST1SMM SOZLAMALAR
# ============================================================

BOT_TOKEN = os.getenv(
    "BOT_TOKEN",
    "BU_YERGA_BOT_TOKENINGIZNI_YOZING"
)

SEENSMS_API_KEY = os.getenv(
    "SEENSMS_API_KEY",
    "BU_YERGA_SEENSMS_API_KEYINGIZNI_YOZING"
)

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
#                     BOT / DISPATCHER
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

    "instagram": {
        "name": "📸 Instagram",
        "keywords": [
            "instagram",
            "insta"
        ]
    },

    "tiktok": {
        "name": "🎵 TikTok",
        "keywords": [
            "tiktok",
            "tik tok"
        ]
    },

    "youtube": {
        "name": "▶️ YouTube",
        "keywords": [
            "youtube",
            "youtu.be"
        ]
    },

    "telegram": {
        "name": "✈️ Telegram",
        "keywords": [
            "telegram",
            "t.me"
        ]
    }
}


# ============================================================
#                    MAIN MENU
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


# ============================================================
#                  PLATFORM MENU
# ============================================================

def platform_keyboard():

    builder = InlineKeyboardBuilder()

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
            text="🔙 Orqaga",
            callback_data="back_main"
        )
    )

    return builder.as_markup()


# ============================================================
#                    CANCEL BUTTON
# ============================================================

def cancel_keyboard():

    builder = InlineKeyboardBuilder()

    builder.row(

        InlineKeyboardButton(
            text="❌ Bekor qilish",
            callback_data="cancel_order"
        )
    )

    return builder.as_markup()


# ============================================================
#                    CONFIRM BUTTON
# ============================================================

def confirm_keyboard():

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

    return builder.as_markup()


# ============================================================
#                   API REQUEST
# ============================================================

async def seensms_request(
    data: dict
) -> Any:

    if not SEENSMS_API_KEY:

        raise RuntimeError(
            "SeenSMS API key topilmadi."
        )

    payload = {
        "key": SEENSMS_API_KEY,
        **data
    }

    timeout = aiohttp.ClientTimeout(
        total=30
    )

    try:

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
                        "API JSON formatda javob bermadi: "
                        + text[:500]
                    )

    except asyncio.TimeoutError:

        raise RuntimeError(
            "SeenSMS API timeout."
        )

    except aiohttp.ClientError as error:

        raise RuntimeError(
            f"API connection error: {error}"
        )


# ============================================================
#                    GET SERVICES
# ============================================================

async def get_services():

    return await seensms_request({

        "action": "services"

    })


# ============================================================
#                      ADD ORDER
# ============================================================

async def add_order(
    service_id: int,
    link: str,
    quantity: int
):

    return await seensms_request({

        "action": "add",

        "service": service_id,

        "link": link,

        "quantity": quantity

    })


# ============================================================
#                       BALANCE
# ============================================================

async def get_balance():

    return await seensms_request({

        "action": "balance"

    })


# ============================================================
#                    ORDER STATUS
# ============================================================

async def get_order_status(
    order_id: int
):

    return await seensms_request({

        "action": "status",

        "order": order_id

    })


# ============================================================
#                    NORMALIZE TEXT
# ============================================================

def normalize(
    text: str
):

    return (
        str(text)
        .lower()
        .strip()
    )


# ============================================================
#                SERVICE PLATFORM CHECK
# ============================================================

def service_belongs_to_platform(
    service: dict,
    platform: str
):

    platform_data = PLATFORMS.get(
        platform
    )

    if not platform_data:
        return False

    service_name = normalize(
        service.get(
            "name",
            ""
        )
    )

    category = normalize(
        service.get(
            "category",
            ""
        )
    )

    full_text = (
        service_name
        + " "
        + category
    )

    for keyword in platform_data["keywords"]:

        if keyword in full_text:

            return True

    return False


# ============================================================
#                 SERVICES KEYBOARD
# ============================================================

def services_keyboard(
    services: list
):

    builder = InlineKeyboardBuilder()

    for service in services:

        service_id = service.get(
            "service"
        )

        service_name = str(
            service.get(
                "name",
                "Noma'lum xizmat"
            )
        )

        if len(service_name) > 55:

            service_name = (
                service_name[:52]
                + "..."
            )

        builder.row(

            InlineKeyboardButton(

                text=f"⚡ {service_name}",

                callback_data=(
                    f"service:{service_id}"
                )
            )
        )

    builder.row(

        InlineKeyboardButton(
            text="🔙 Platformalar",
            callback_data="new_order"
        )
    )

    return builder.as_markup()


# ============================================================
#                     SAFE INTEGER
# ============================================================

def safe_int(
    value
):

    try:

        return int(
            float(
                str(value)
            )
        )

    except Exception:

        return None


# ============================================================
#                    CALCULATE PRICE
# ============================================================

def calculate_price(
    rate,
    quantity
):

    try:

        return (
            float(rate)
            * int(quantity)
            / 1000
        )

    except Exception:

        return 0


# ============================================================
#                         START
# ============================================================

@dp.message(
    CommandStart()
)
async def start_handler(
    message: Message,
    state: FSMContext
):

    await state.clear()

    text = (

        "✨ <b>BEST1SMM</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"

        "🚀 SMM xizmatlar paneli\n\n"

        "📸 Instagram\n"
        "🎵 TikTok\n"
        "▶️ YouTube\n"
        "✈️ Telegram\n\n"

        "💎 Tez • Qulay • Avtomatik\n\n"

        "👇 <b>Kerakli bo‘limni tanlang:</b>"
    )

    await message.answer(

        text,

        reply_markup=main_menu()
    )


# ============================================================
#                  BUYURTMA BOSHLASH
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
        "━━━━━━━━━━━━━━━━━━\n\n"

        "🌐 Platformani tanlang:\n\n"

        "📸 Instagram\n"
        "🎵 TikTok\n"
        "▶️ YouTube\n"
        "✈️ Telegram",

        reply_markup=platform_keyboard()
    )

    await callback.answer()


# ============================================================
#                  PLATFORM TANLASH
# ============================================================

@dp.callback_query(
    OrderState.choosing_platform,
    F.data.startswith("platform:")
)
async def platform_selected(
    callback: CallbackQuery,
    state: FSMContext
):

    platform = callback.data.split(
        ":",
        1
    )[1]

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

        "⏳ <b>Xizmatlar yuklanmoqda...</b>\n\n"
        "🔄 SeenSMS bilan bog‘lanilmoqda..."
    )

    try:

        response = await get_services()

        if not isinstance(
            response,
            list
        ):

            await callback.message.edit_text(

                "❌ <b>Xizmatlarni olishda xatolik!</b>\n\n"

                "SeenSMS API noto‘g‘ri javob qaytardi.",

                reply_markup=main_menu()
            )

            await callback.answer()

            return

        filtered_services = [

            service

            for service in response

            if service_belongs_to_platform(
                service,
                platform
            )
        ]

        if not filtered_services:

            await callback.message.edit_text(

                "😔 <b>Xizmat topilmadi.</b>\n\n"

                f"{PLATFORMS[platform]['name']} "
                "uchun hozircha xizmat mavjud emas.",

                reply_markup=platform_keyboard()
            )

            await callback.answer()

            return

        await state.update_data(

            available_services=
            filtered_services
        )

        await state.set_state(

            OrderState.choosing_service
        )

        await callback.message.edit_text(

            f"{PLATFORMS[platform]['name']}\n"
            "━━━━━━━━━━━━━━━━━━\n\n"

            "⚡ <b>Xizmatni tanlang:</b>",

            reply_markup=
            services_keyboard(
                filtered_services
            )
        )

    except Exception as error:

        logger.exception(
            "Services error: %s",
            error
        )

        await callback.message.edit_text(

            "❌ <b>Xatolik!</b>\n\n"

            "SeenSMS API bilan bog‘lanib bo‘lmadi.\n\n"
            "🔄 Keyinroq qayta urinib ko‘ring.",

            reply_markup=main_menu()
        )

    await callback.answer()


# ============================================================
#                    SERVICE TANLASH
# ============================================================

@dp.callback_query(
    OrderState.choosing_service,
    F.data.startswith("service:")
)
async def service_selected(
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

    selected_service = None

    for service in services:

        if str(
            service.get("service")
        ) == str(service_id):

            selected_service = service

            break

    if not selected_service:

        await callback.answer(

            "❌ Xizmat topilmadi!",

            show_alert=True
        )

        return

    await state.update_data(

        service_id=service_id,

        service_name=
        selected_service.get(
            "name",
            "Noma'lum"
        ),

        service_rate=
        selected_service.get(
            "rate"
        ),

        service_min=
        selected_service.get(
            "min"
        ),

        service_max=
        selected_service.get(
            "max"
        )
    )

    await state.set_state(

        OrderState.entering_quantity
    )

    await callback.message.edit_text(

        "🔢 <b>MIQDORNI KIRITING</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"

        f"⚡ Xizmat:\n"
        f"<b>{selected_service.get('name')}</b>\n\n"

        f"📊 Minimum: "
        f"<b>{selected_service.get('min')}</b>\n"

        f"📈 Maximum: "
        f"<b>{selected_service.get('max')}</b>\n\n"

        "👇 Kerakli miqdorni yuboring:\n\n"

        "Masalan:\n"
        "<code>1000</code>",

        reply_markup=cancel_keyboard()
    )

    await callback.answer()


# ============================================================
#                    MIQDOR KIRITISH
# ============================================================

@dp.message(
    OrderState.entering_quantity
)
async def quantity_handler(
    message: Message,
    state: FSMContext
):

    text = (
        message.text.strip()
        if message.text
        else ""
    )

    if not text.isdigit():

        await message.answer(

            "❌ <b>Noto‘g‘ri miqdor!</b>\n\n"

            "Faqat raqam yuboring.\n\n"

            "Masalan:\n"
            "<code>1000</code>",

            reply_markup=cancel_keyboard()
        )

        return

    quantity = int(text)

    data = await state.get_data()

    minimum = safe_int(
        data.get(
            "service_min"
        )
    )

    maximum = safe_int(
        data.get(
            "service_max"
        )
    )

    if minimum is not None:

        if quantity < minimum:

            await message.answer(

                "❌ <b>Miqdor juda kam!</b>\n\n"

                f"📊 Minimum: "
                f"<b>{minimum}</b>\n\n"

                "Qaytadan kiriting:",

                reply_markup=
                cancel_keyboard()
            )

            return

    if maximum is not None:

        if quantity > maximum:

            await message.answer(

                "❌ <b>Miqdor juda ko‘p!</b>\n\n"

                f"📈 Maximum: "
                f"<b>{maximum}</b>\n\n"

                "Qaytadan kiriting:",

                reply_markup=
                cancel_keyboard()
            )

            return

    price = calculate_price(

        data.get(
            "service_rate"
        ),

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
        "━━━━━━━━━━━━━━━━━━\n\n"

        f"🔢 Miqdor: "
        f"<b>{quantity:,}</b>\n"

        f"💰 Narx: "
        f"<b>{price:,.2f}</b>\n\n"

        "👇 Buyurtma havolasini yuboring:\n\n"

        "Masalan:\n"
        "<code>https://instagram.com/...</code>",

        reply_markup=cancel_keyboard()
    )


# ============================================================
#                    HAVOLA KIRITISH
# ============================================================

@dp.message(
    OrderState.entering_link
)
async def link_handler(
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

            reply_markup=cancel_keyboard()
        )

        return

    if not (
        link.startswith(
            "https://"
        )
        or
        link.startswith(
            "http://"
        )
    ):

        await message.answer(

            "❌ <b>Noto‘g‘ri havola!</b>\n\n"

            "Havola <code>https://</code> "
            "yoki <code>http://</code> bilan "
            "boshlanishi kerak.",

            reply_markup=cancel_keyboard()
        )

        return

    data = await state.get_data()

    platform = data.get(
        "platform"
    )

    platform_domains = {

        "instagram": [
            "instagram.com"
        ],

        "tiktok": [
            "tiktok.com"
        ],

        "youtube": [
            "youtube.com",
            "youtu.be"
        ],

        "telegram": [
            "t.me",
            "telegram.me"
        ]
    }

    allowed_domains = platform_domains.get(
        platform,
        []
    )

    if allowed_domains:

        if not any(
            domain in link.lower()
            for domain in allowed_domains
        ):

            await message.answer(

                "❌ <b>Havola mos emas!</b>\n\n"

                f"Bu buyurtma "
                f"<b>{PLATFORMS[platform]['name']}</b> "
                "uchun.\n\n"

                "To‘g‘ri havolani yuboring.",

                reply_markup=
                cancel_keyboard()
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

        "🧾 <b>BUYURTMA TASDIG‘I</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"

        f"🌐 Platforma:\n"
        f"<b>{PLATFORMS[platform]['name']}</b>\n\n"

        f"⚡ Xizmat:\n"
        f"<b>{data.get('service_name')}</b>\n\n"

        f"🔢 Miqdor:\n"
        f"<b>{data.get('quantity'):,}</b>\n\n"

        f"🔗 Havola:\n"
        f"<code>{link}</code>\n\n"

        f"💰 Narx:\n"
        f"<b>{price:,.2f}</b>\n\n"

        "━━━━━━━━━━━━━━━━━━\n"

        "👇 Ma’lumotlarni tekshiring:",

        reply_markup=
        confirm_keyboard()
    )


# ============================================================
#                  BUYURTMANI TASDIQLASH
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
            "SeenSMS order response: %s",
            response
        )

        if (
            isinstance(
                response,
                dict
            )
            and
            response.get("order")
        ):

            order_id = response.get(
                "order"
            )

            await state.update_data(

                order_id=order_id
            )

            await callback.message.edit_text(

                "🎉 <b>BUYURTMA QABUL QILINDI!</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"

                f"🆔 Buyurtma ID:\n"
                f"<code>{order_id}</code>\n\n"

                f"📱 Platforma:\n"
                f"<b>{PLATFORMS[data['platform']]['name']}</b>\n\n"

                f"⚡ Xizmat:\n"
                f"<b>{data['service_name']}</b>\n\n"

                f"🔢 Miqdor:\n"
                f"<b>{data['quantity']:,}</b>\n\n"

                "⏳ Buyurtma bajarilishi "
                "tez orada boshlanadi.\n\n"

                "✨ <b>Best1SMM</b>",

                reply_markup=main_menu()
            )

        else:

            if isinstance(
                response,
                dict
            ):

                error_text = (
                    response.get("error")
                    or
                    response.get("message")
                    or
                    "Noma'lum API xatosi"
                )

            else:

                error_text = (
                    "Noma'lum API xatosi"
                )

            await callback.message.edit_text(

                "❌ <b>BUYURTMA BERILMADI</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"

                f"📛 Sabab:\n"
                f"<code>{error_text}</code>\n\n"

                "💡 Balans, xizmat limiti yoki "
                "havolani tekshiring.",

                reply_markup=main_menu()
            )

    except Exception as error:

        logger.exception(
            "Order error: %s",
            error
        )

        await callback.message.edit_text(

            "❌ <b>Texnik xatolik!</b>\n\n"

            "Buyurtma yuborilmadi.\n"
            "Bir ozdan keyin qayta urinib ko‘ring.",

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

    await callback.answer(
        "Buyurtma bekor qilindi."
    )


# ============================================================
#                         BALANCE
# ============================================================

@dp.callback_query(
    F.data == "balance"
)
async def balance_callback(
    callback: CallbackQuery
):

    await callback.message.edit_text(

        "⏳ <b>Balans tekshirilmoqda...</b>"
    )

    try:

        response = await get_balance()

        if isinstance(
            response,
            dict
        ):

            balance = response.get(
                "balance",
                "Noma'lum"
            )

            currency = response.get(
                "currency",
                ""
            )

            await callback.message.edit_text(

                "💰 <b>SEENSMS BALANS</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"

                f"💳 Balans: "
                f"<b>{balance}</b>\n"

                f"💵 Valyuta: "
                f"<b>{currency}</b>",

                reply_markup=main_menu()
            )

        else:

            await callback.message.edit_text(

                "❌ Balansni olishda xatolik.",

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
#                       MY ORDER
# ============================================================

@dp.callback_query(
    F.data == "my_order"
)
async def my_order_callback(
    callback: CallbackQuery,
    state: FSMContext
):

    data = await state.get_data()

    order_id = data.get(
        "order_id"
    )

    if not order_id:

        await callback.message.edit_text(

            "📦 <b>BUYURTMAM</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"

            "Hozirgi sessiyada buyurtma topilmadi.\n\n"

            "🛒 Yangi buyurtma berishingiz mumkin.",

            reply_markup=main_menu()
        )

        await callback.answer()

        return

    await callback.message.edit_text(

        "⏳ <b>Buyurtma holati tekshirilmoqda...</b>"
    )

    try:

        response = await get_order_status(
            int(order_id)
        )

        if isinstance(
            response,
            dict
        ):

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

                "📦 <b>BUYURTMA HOLATI</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"

                f"🆔 ID:\n"
                f"<code>{order_id}</code>\n\n"

                f"📊 Holat:\n"
                f"<b>{status}</b>\n\n"

                f"🚀 Boshlang‘ich:\n"
                f"<b>{start_count}</b>\n\n"

                f"📉 Qoldiq:\n"
                f"<b>{remains}</b>",

                reply_markup=main_menu()
            )

        else:

            await callback.message.edit_text(

                "❌ Buyurtma holatini olishda xatolik.",

                reply_markup=main_menu()
            )

    except Exception as error:

        logger.exception(
            "Status error: %s",
            error
        )

        await callback.message.edit_text(

            "❌ <b>API xatosi!</b>\n\n"
            "Buyurtma holatini olish imkoni bo‘lmadi.",

            reply_markup=main_menu()
        )

    await callback.answer()


# ============================================================
#                          HELP
# ============================================================

@dp.callback_query(
    F.data == "help"
)
async def help_callback(
    callback: CallbackQuery
):

    await callback.message.edit_text(

        "ℹ️ <b>BEST1SMM YORDAM</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"

        "🛒 <b>Buyurtma berish</b>\n"
        "Xizmat tanlab, miqdor va havolani "
        "kiritib buyurtma berasiz.\n\n"

        "📦 <b>Buyurtmam</b>\n"
        "Oxirgi buyurtmangiz holatini ko‘rasiz.\n\n"

        "💰 <b>Balans</b>\n"
        "SeenSMS balansini ko‘rsatadi.\n\n"

        f"👨‍💻 Admin: @{ADMIN_USERNAME}",

        reply_markup=main_menu()
    )

    await callback.answer()


# ============================================================
#                        BACK MAIN
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
        "━━━━━━━━━━━━━━━━━━\n\n"

        "👇 Kerakli bo‘limni tanlang:",

        reply_markup=main_menu()
    )

    await callback.answer()


# ============================================================
#                 UNKNOWN MESSAGE HANDLER
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
#                        RUN BOT
# ============================================================

async def main():

    logger.info(
        "🚀 Best1SMM bot ishga tushmoqda..."
    )

    if (
        not BOT_TOKEN
        or
        "BU_YERGA" in BOT_TOKEN
    ):

        raise RuntimeError(
            "BOT_TOKEN kiritilmagan!"
        )

    if (
        not SEENSMS_API_KEY
        or
        "BU_YERGA" in SEENSMS_API_KEY
    ):

        raise RuntimeError(
            "SEENSMS_API_KEY kiritilmagan!"
        )

    await bot.delete_webhook(
        drop_pending_updates=True
    )

    await dp.start_polling(
        bot
    )


# ============================================================
#                         START
# ============================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        logger.info(
            "🛑 Bot to‘xtatildi."
    )
