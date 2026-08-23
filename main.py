import os
import sqlite3
import asyncio
import aiohttp

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SMM_API_URL = os.getenv("SMM_API_URL", "https://socgrow.uz/api/v2")
SMM_API_KEY = os.getenv("SMM_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN topilmadi!")

if not SMM_API_KEY:
    raise ValueError("SMM_API_KEY topilmadi!")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

DB = "smm.db"


# ================= DATABASE =================

def db():
    return sqlite3.connect(DB)


def init_db():
    con = db()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance REAL DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            api_order TEXT,
            service_id TEXT,
            link TEXT,
            quantity INTEGER,
            charge REAL,
            status TEXT DEFAULT 'Pending'
        )
    """)

    con.commit()
    con.close()


def add_user(user_id):
    con = db()
    cur = con.cursor()

    cur.execute(
        "INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)",
        (user_id,)
    )

    con.commit()
    con.close()


def get_balance(user_id):
    con = db()
    cur = con.cursor()

    cur.execute(
        "SELECT balance FROM users WHERE user_id=?",
        (user_id,)
    )

    result = cur.fetchone()
    con.close()

    return float(result[0]) if result else 0


# ================= STATES =================

class OrderState(StatesGroup):
    choosing_service = State()
    waiting_link = State()
    waiting_quantity = State()


# ================= API =================

async def smm_request(action, method="GET", data=None):

    if not SMM_API_KEY:
        return {"error": "SMM_API_KEY sozlanmagan"}

    data = data or {}

    params = {
        "key": SMM_API_KEY,
        "action": action
    }

    try:
        async with aiohttp.ClientSession() as session:

            if method == "POST":
                async with session.post(
                    SMM_API_URL,
                    data={**params, **data},
                    timeout=30
                ) as response:
                    return await response.json()

            else:
                async with session.get(
                    SMM_API_URL,
                    params={**params, **data},
                    timeout=30
                ) as response:
                    return await response.json()

    except Exception as e:
        print("API ERROR:", e)
        return {"error": "API bilan aloqa qilib bo'lmadi"}


async def get_services():
    return await smm_request("services")


async def get_api_balance():
    return await smm_request("balance")


async def add_order(service_id, link, quantity):
    return await smm_request(
        "add",
        method="POST",
        data={
            "service": service_id,
            "link": link,
            "quantity": quantity
        }
    )


async def get_order_status(order_id):
    return await smm_request(
        "status",
        data={
            "order": order_id
        }
    )


# ================= MENU =================

def main_menu():

    kb = InlineKeyboardBuilder()

    kb.button(
        text="🛒 Buyurtma berish",
        callback_data="order"
    )

    kb.button(
        text="💰 Balans",
        callback_data="balance"
    )

    kb.button(
        text="📦 Buyurtmalarim",
        callback_data="orders"
    )

    kb.button(
        text="💳 Panel balansi",
        callback_data="panel_balance"
    )

    kb.adjust(1)

    return kb.as_markup()


# ================= START =================

@dp.message(CommandStart())
async def start(message: Message):

    add_user(message.from_user.id)

    await message.answer(
        f"👋 Salom, {message.from_user.first_name}!\n\n"
        "🚀 SMM xizmatlar botiga xush kelibsiz!\n\n"
        "📸 Instagram\n"
        "📱 Telegram\n"
        "🎵 TikTok\n"
        "▶️ YouTube\n\n"
        "Kerakli bo‘limni tanlang:",
        reply_markup=main_menu()
    )


# ================= USER BALANCE =================

@dp.callback_query(F.data == "balance")
async def balance(call: CallbackQuery):

    add_user(call.from_user.id)

    balance = get_balance(call.from_user.id)

    await call.message.answer(
        f"💰 Sizning balansingiz:\n\n"
        f"💵 {balance:.2f} so‘m"
    )

    await call.answer()


# ================= PANEL BALANCE =================

@dp.callback_query(F.data == "panel_balance")
async def panel_balance(call: CallbackQuery):

    result = await get_api_balance()

    if "error" in result:

        await call.message.answer(
            f"❌ Xatolik:\n{result['error']}"
        )

    else:

        await call.message.answer(
            f"💳 SocGrow panel balansi:\n\n"
            f"💰 {result.get('balance', 'Nomaʼlum')} "
            f"{result.get('currency', 'UZS')}"
        )

    await call.answer()


# ================= SERVICES =================

@dp.callback_query(F.data == "order")
async def order(call: CallbackQuery, state: FSMContext):

    result = await get_services()

    if not isinstance(result, list):

        await call.message.answer(
            f"❌ Xizmatlarni olishda xatolik:\n"
            f"{result.get('error', 'Nomaʼlum xatolik')}"
        )

        await call.answer()
        return

    kb = InlineKeyboardBuilder()

    count = 0

    for service in result:

        service_id = str(service.get("service", ""))

        name = service.get(
            "name",
            f"Service {service_id}"
        )

        if not service_id:
            continue

        kb.button(
            text=f"🛒 {name[:45]}",
            callback_data=f"service:{service_id}"
        )

        count += 1

        if count >= 50:
            break

    kb.adjust(1)

    if count == 0:

        await call.message.answer(
            "❌ Hozircha xizmatlar topilmadi."
        )

    else:

        await call.message.answer(
            "🛒 Kerakli xizmatni tanlang:",
            reply_markup=kb.as_markup()
        )

        await state.set_state(OrderState.choosing_service)

    await call.answer()


# ================= CHOOSE SERVICE =================

@dp.callback_query(
    OrderState.choosing_service,
    F.data.startswith("service:")
)
async def choose_service(
    call: CallbackQuery,
    state: FSMContext
):

    service_id = call.data.split(":", 1)[1]

    await state.update_data(
        service_id=service_id
    )

    await call.message.answer(
        f"✅ Xizmat tanlandi\n\n"
        f"🆔 Service ID: {service_id}\n\n"
        f"🔗 Endi buyurtma linkini yuboring:"
    )

    await state.set_state(
        OrderState.waiting_link
    )

    await call.answer()


# ================= LINK =================

@dp.message(OrderState.waiting_link)
async def get_link(
    message: Message,
    state: FSMContext
):

    link = message.text.strip()

    if not link:

        await message.answer(
            "❌ Link bo‘sh bo‘lishi mumkin emas."
        )
        return

    await state.update_data(
        link=link
    )

    await message.answer(
        "🔢 Endi miqdorni yuboring.\n\n"
        "Masalan:\n"
        "100\n"
        "500\n"
        "1000"
    )

    await state.set_state(
        OrderState.waiting_quantity
    )


# ================= QUANTITY =================

@dp.message(OrderState.waiting_quantity)
async def get_quantity(
    message: Message,
    state: FSMContext
):

    try:

        quantity = int(message.text.strip())

        if quantity <= 0:
            raise ValueError

    except ValueError:

        await message.answer(
            "❌ Miqdor faqat musbat son bo‘lishi kerak."
        )

        return

    data = await state.get_data()

    service_id = data["service_id"]
    link = data["link"]

    await message.answer(
        "⏳ Buyurtma tekshirilmoqda..."
    )

    # Avval xizmat ma'lumotini topamiz
    services = await get_services()

    if not isinstance(services, list):

        await message.answer(
            f"❌ API xatosi:\n"
            f"{services.get('error', 'Nomaʼlum')}"
        )

        await state.clear()
        return

    selected = None

    for service in services:

        if str(service.get("service")) == str(service_id):

            selected = service
            break

    if not selected:

        await message.answer(
            "❌ Bu xizmat topilmadi."
        )

        await state.clear()
        return

    name = selected.get(
        "name",
        f"Service {service_id}"
    )

    minimum = int(
        selected.get("min", 0) or 0
    )

    maximum = int(
        selected.get("max", 0) or 0
    )

    rate = float(
        selected.get("rate", 0) or 0
    )

    if minimum and quantity < minimum:

        await message.answer(
            f"❌ Minimal miqdor: {minimum}"
        )

        return

    if maximum and quantity > maximum:

        await message.answer(
            f"❌ Maksimal miqdor: {maximum}"
        )

        return

    # SocGrow rate odatda 1000 birlik narxi bo'ladi
    charge = (rate * quantity) / 1000

    user_balance = get_balance(
        message.from_user.id
    )

    if user_balance < charge:

        await message.answer(
            f"❌ Balansingiz yetarli emas.\n\n"
            f"💰 Narx: {charge:.2f} so‘m\n"
            f"💳 Balansingiz: {user_balance:.2f} so‘m\n\n"
            f"➕ Avval balansni to‘ldiring."
        )

        await state.clear()
        return

    # API orqali buyurtma
    result = await add_order(
        service_id,
        link,
        quantity
    )

    if "error" in result:

        await message.answer(
            f"❌ Buyurtma berilmadi:\n\n"
            f"{result['error']}"
        )

        await state.clear()
        return

    api_order = str(
        result.get("order", "")
    )

    real_charge = float(
        result.get("charge", charge)
    )

    # Balansdan yechish
    con = db()
    cur = con.cursor()

    cur.execute(
        """
        UPDATE users
        SET balance = balance - ?
        WHERE user_id=?
        """,
        (real_charge, message.from_user.id)
    )

    cur.execute(
        """
        INSERT INTO orders
        (user_id, api_order, service_id, link,
         quantity, charge, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            message.from_user.id,
            api_order,
            service_id,
            link,
            quantity,
            real_charge,
            "Pending"
        )
    )

    con.commit()
    con.close()

    await message.answer(
        f"✅ BUYURTMA QABUL QILINDI!\n\n"
        f"🆔 Buyurtma: #{api_order}\n"
        f"📦 Xizmat: {name}\n"
        f"🔗 Link: {link}\n"
        f"🔢 Miqdor: {quantity}\n"
        f"💰 Narx: {real_charge:.2f} so‘m\n"
        f"📊 Status: Pending"
    )

    await state.clear()


# ================= ORDERS =================

@dp.callback_query(F.data == "orders")
async def orders(call: CallbackQuery):

    con = db()
    cur = con.cursor()

    cur.execute(
        """
        SELECT api_order, service_id, link,
               quantity, charge, status
        FROM orders
        WHERE user_id=?
        ORDER BY id DESC
        LIMIT 10
        """,
        (call.from_user.id,)
    )

    rows = cur.fetchall()

    con.close()

    if not rows:

        await call.message.answer(
            "📦 Sizda hali buyurtmalar yo‘q."
        )

        await call.answer()
        return

    text = "📦 Buyurtmalaringiz:\n\n"

    for row in rows:

        text += (
            f"🆔 #{row[0]}\n"
            f"📌 Service: {row[1]}\n"
            f"🔗 {row[2]}\n"
            f"🔢 Miqdor: {row[3]}\n"
            f"💰 Narx: {row[4]:.2f} so‘m\n"
            f"📊 {row[5]}\n\n"
        )

    await call.message.answer(text)

    await call.answer()


# ================= STATUS =================

@dp.message(F.text.startswith("/status"))
async def status_command(message: Message):

    parts = message.text.split()

    if len(parts) != 2:

        await message.answer(
            "❌ Format:\n/status ORDER_ID"
        )

        return

    order_id = parts[1]

    result = await get_order_status(
        order_id
    )

    if "error" in result:

        await message.answer(
            f"❌ Xatolik:\n{result['error']}"
        )

        return

    status = result.get(
        "status",
        "Nomaʼlum"
    )

    await message.answer(
        f"📦 Buyurtma: #{order_id}\n\n"
        f"📊 Status: {status}"
    )


# ================= ADMIN =================

@dp.message(F.text == "/admin")
async def admin(message: Message):

    if message.from_user.id != ADMIN_ID:

        await message.answer(
            "❌ Siz admin emassiz."
        )

        return

    await message.answer(
        "👨‍💼 ADMIN PANEL\n\n"
        "/stats — statistika\n"
        "/addbalance USER_ID SUM — balans qo‘shish"
    )


@dp.message(F.text == "/stats")
async def stats(message: Message):

    if message.from_user.id != ADMIN_ID:
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

    orders_count = cur.fetchone()[0]

    con.close()

    await message.answer(
        f"📊 STATISTIKA\n\n"
        f"👤 Userlar: {users}\n"
        f"📦 Buyurtmalar: {orders_count}"
    )


@dp.message(F.text.startswith("/addbalance"))
async def add_balance(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    try:

        parts = message.text.split()

        user_id = int(parts[1])
        amount = float(parts[2])

        add_user(user_id)

        con = db()
        cur = con.cursor()

        cur.execute(
            """
            UPDATE users
            SET balance = balance + ?
            WHERE user_id=?
            """,
            (amount, user_id)
        )

        con.commit()
        con.close()

        await message.answer(
            f"✅ {user_id} hisobiga "
            f"{amount:.2f} so‘m qo‘shildi."
        )

    except Exception:

        await message.answer(
            "❌ To‘g‘ri format:\n\n"
            "/addbalance USER_ID SUM"
        )


# ================= RUN =================

async def main():

    init_db()

    print("🤖 SMM BOT ISHLADI!")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
