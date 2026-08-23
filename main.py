import os
import asyncio
import aiohttp

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
TOPSMM_API_KEY = os.getenv("TOPSMM_API_KEY")

TOPSMM_API_URL = "https://topsmm.uz/api/v2"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN Environment Variable topilmadi!")

if not TOPSMM_API_KEY:
    raise RuntimeError("TOPSMM_API_KEY Environment Variable topilmadi!")


# =========================================================
# BOT
# =========================================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# =========================================================
# USER STATES
# =========================================================

class OrderState(StatesGroup):
    waiting_link = State()
    waiting_quantity = State()


# =========================================================
# API REQUEST
# =========================================================

async def topsmm_api(action: str, **params):

    data = {
        "key": TOPSMM_API_KEY,
        "action": action,
        **params,
    }

    try:

        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(timeout=timeout) as session:

            async with session.post(
                TOPSMM_API_URL,
                data=data
            ) as response:

                text = await response.text()

                if response.status != 200:
                    return {
                        "error": f"API HTTP xatosi: {response.status}"
                    }

                try:
                    return await response.json()

                except Exception:
                    return {
                        "error": f"API noto'g'ri javob qaytardi:\n{text[:500]}"
                    }

    except asyncio.TimeoutError:

        return {
            "error": "API javob berish uchun juda ko'p vaqt oldi."
        }

    except aiohttp.ClientError as e:

        return {
            "error": f"Internet/API xatosi: {e}"
        }

    except Exception as e:

        return {
            "error": f"Noma'lum xatolik: {e}"
        }


# =========================================================
# MAIN MENU
# =========================================================

def main_menu():

    return InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="📋 Xizmatlar",
                    callback_data="services"
                )
            ],

            [
                InlineKeyboardButton(
                    text="🛒 Buyurtma berish",
                    callback_data="order"
                )
            ],

            [
                InlineKeyboardButton(
                    text="📊 Buyurtma statusi",
                    callback_data="status"
                )
            ],

            [
                InlineKeyboardButton(
                    text="💰 Balans",
                    callback_data="balance"
                )
            ],

            [
                InlineKeyboardButton(
                    text="ℹ️ Yordam",
                    callback_data="help"
                )
            ]

        ]
    )


# =========================================================
# START
# =========================================================

@dp.message(Command("start"))
async def start(message: Message):

    await message.answer(
        "🔥 <b>BEST SMM BOT</b>\n\n"
        "⚡ Tezkor SMM xizmatlari\n"
        "📸 Instagram\n"
        "🎵 TikTok\n"
        "▶️ YouTube\n"
        "✈️ Telegram\n\n"
        "👇 Kerakli bo'limni tanlang:",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )


# =========================================================
# SERVICES
# =========================================================

@dp.callback_query(F.data == "services")
async def show_services(callback: CallbackQuery):

    await callback.answer("⏳ Xizmatlar yuklanmoqda...")

    data = await topsmm_api("services")

    if isinstance(data, dict) and data.get("error"):

        await callback.message.answer(
            f"❌ <b>API xatosi</b>\n\n"
            f"{data['error']}",
            parse_mode="HTML"
        )

        return

    if not isinstance(data, list):

        await callback.message.answer(
            "❌ Xizmatlarni olishda xatolik yuz berdi."
        )

        return

    # Xizmatlarni kategoriyalar bo'yicha chiqaramiz

    text = "📋 <b>SMM XIZMATLARI</b>\n\n"

    for service in data[:40]:

        service_id = service.get("service", "-")
        name = service.get("name", "-")
        category = service.get("category", "-")
        rate = service.get("rate", "-")
        minimum = service.get("min", "-")
        maximum = service.get("max", "-")

        text += (
            f"🆔 <b>{service_id}</b>\n"
            f"📌 {name}\n"
            f"📂 {category}\n"
            f"💵 Narx: {rate}\n"
            f"📦 Min: {minimum} | Max: {maximum}\n"
            f"━━━━━━━━━━━━━━\n"
        )

    # Telegram xabar limiti sabab bo'lib qolmasligi uchun
    if len(text) > 4000:
        text = text[:3950] + "\n\n...davomi mavjud."

    await callback.message.answer(
        text,
        parse_mode="HTML"
    )


# =========================================================
# BALANCE
# =========================================================

@dp.callback_query(F.data == "balance")
async def show_balance(callback: CallbackQuery):

    await callback.answer("⏳")

    data = await topsmm_api("balance")

    if isinstance(data, dict) and data.get("error"):

        await callback.message.answer(
            f"❌ {data['error']}"
        )

        return

    balance = data.get("balance", "0")
    currency = data.get("currency", "USD")

    await callback.message.answer(
        "💰 <b>TOPSMM BALANS</b>\n\n"
        f"💵 Balans: <b>{balance}</b>\n"
        f"💳 Valyuta: <b>{currency}</b>",
        parse_mode="HTML"
    )


# =========================================================
# ORDER START
# =========================================================

@dp.callback_query(F.data == "order")
async def start_order(callback: CallbackQuery, state: FSMContext):

    await callback.answer()

    await state.clear()

    await callback.message.answer(
        "🛒 <b>BUYURTMA</b>\n\n"
        "Avval xizmat ID'sini yuboring.\n\n"
        "Masalan:\n"
        "<code>123</code>",
        parse_mode="HTML"
    )

    await state.update_data(step="service")

    # FSM'dan foydalanish uchun custom state
    await state.set_state(OrderState.waiting_link)


# =========================================================
# ORDER MESSAGE
# =========================================================

@dp.message(OrderState.waiting_link)
async def order_process(message: Message, state: FSMContext):

    data = await state.get_data()

    # -----------------------------------------------------
    # SERVICE ID
    # -----------------------------------------------------

    if data.get("service") is None:

        service_id = message.text.strip()

        if not service_id.isdigit():

            await message.answer(
                "❌ Xizmat ID faqat raqam bo'lishi kerak.\n\n"
                "Masalan: <code>123</code>",
                parse_mode="HTML"
            )

            return

        await state.update_data(service=service_id)

        await message.answer(
            "🔗 Endi <b>link</b> yuboring.\n\n"
            "Masalan:\n"
            "<code>https://instagram.com/example</code>",
            parse_mode="HTML"
        )

        return

    # -----------------------------------------------------
    # LINK
    # -----------------------------------------------------

    if data.get("link") is None:

        link = message.text.strip()

        if not (
            link.startswith("http://")
            or link.startswith("https://")
        ):

            await message.answer(
                "❌ Link noto'g'ri.\n\n"
                "Link <code>https://</code> bilan boshlanishi kerak.",
                parse_mode="HTML"
            )

            return

        await state.update_data(link=link)

        await message.answer(
            "🔢 Endi miqdorni yuboring.\n\n"
            "Masalan:\n"
            "<code>100</code>",
            parse_mode="HTML"
        )

        return

    # -----------------------------------------------------
    # QUANTITY
    # -----------------------------------------------------

    quantity_text = message.text.strip()

    if not quantity_text.isdigit():

        await message.answer(
            "❌ Miqdor faqat raqam bo'lishi kerak.\n\n"
            "Masalan: <code>100</code>",
            parse_mode="HTML"
        )

        return

    quantity = int(quantity_text)

    if quantity <= 0:

        await message.answer(
            "❌ Miqdor 0 dan katta bo'lishi kerak."
        )

        return

    service_id = data["service"]
    link = data["link"]

    await message.answer(
        "⏳ <b>Buyurtma yuborilmoqda...</b>",
        parse_mode="HTML"
    )

    result = await topsmm_api(
        "add",
        service=service_id,
        link=link,
        quantity=quantity
    )

    await state.clear()

    # API ERROR

    if isinstance(result, dict) and result.get("error"):

        await message.answer(
            "❌ <b>Buyurtma berilmadi!</b>\n\n"
            f"{result['error']}",
            parse_mode="HTML"
        )

        return

    # ORDER ID

    order_id = result.get("order")

    if not order_id:

        await message.answer(
            "⚠️ API buyurtma ID qaytarmadi.\n\n"
            f"Javob: <code>{result}</code>",
            parse_mode="HTML"
        )

        return

    await message.answer(
        "✅ <b>BUYURTMA QABUL QILINDI!</b>\n\n"
        f"🆔 Order ID: <code>{order_id}</code>\n"
        f"📦 Miqdor: <b>{quantity}</b>\n"
        f"🔗 Link: {link}\n\n"
        "📊 Statusni tekshirish uchun:\n"
        f"<code>/status {order_id}</code>",
        parse_mode="HTML"
    )


# =========================================================
# STATUS
# =========================================================

@dp.callback_query(F.data == "status")
async def status_help(callback: CallbackQuery):

    await callback.answer()

    await callback.message.answer(
        "📊 <b>BUYURTMA STATUSI</b>\n\n"
        "Order ID yuboring.\n\n"
        "Masalan:\n"
        "<code>/status 123456</code>",
        parse_mode="HTML"
    )


@dp.message(Command("status"))
async def status_command(message: Message):

    parts = message.text.split()

    if len(parts) != 2:

        await message.answer(
            "❌ To'g'ri format:\n\n"
            "<code>/status ORDER_ID</code>",
            parse_mode="HTML"
        )

        return

    order_id = parts[1]

    await message.answer(
        "⏳ Status tekshirilmoqda..."
    )

    result = await topsmm_api(
        "status",
        order=order_id
    )

    if isinstance(result, dict) and result.get("error"):

        await message.answer(
            f"❌ {result['error']}"
        )

        return

    status = result.get("status", "Noma'lum")
    charge = result.get("charge", "0")
    start_count = result.get("start_count", "0")
    remains = result.get("remains", "0")

    await message.answer(
        "📊 <b>BUYURTMA STATUSI</b>\n\n"
        f"🆔 ID: <code>{order_id}</code>\n"
        f"📌 Status: <b>{status}</b>\n"
        f"🚀 Start: {start_count}\n"
        f"📉 Qoldi: {remains}\n"
        f"💰 Xarajat: {charge}",
        parse_mode="HTML"
    )


# =========================================================
# HELP
# =========================================================

@dp.callback_query(F.data == "help")
async def help_menu(callback: CallbackQuery):

    await callback.answer()

    await callback.message.answer(
        "ℹ️ <b>YORDAM</b>\n\n"
        "📋 Xizmatlar — mavjud xizmatlarni ko'rish\n"
        "🛒 Buyurtma — yangi buyurtma berish\n"
        "📊 Status — buyurtma holatini ko'rish\n"
        "💰 Balans — panel balansini ko'rish\n\n"
        "Muammo bo'lsa admin bilan bog'laning.",
        parse_mode="HTML"
    )


# =========================================================
# UNKNOWN COMMAND
# =========================================================

@dp.message()
async def unknown_message(message: Message):

    await message.answer(
        "🤖 Menyudan foydalaning 👇",
        reply_markup=main_menu()
    )


# =========================================================
# START BOT
# =========================================================

async def main():

    print("================================")
    print("🔥 BEST SMM BOT ISHLAMOQDA")
    print("================================")

    await bot.delete_webhook(drop_pending_updates=True)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
