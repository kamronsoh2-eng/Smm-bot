import os
import sqlite3
import asyncio
import aiohttp

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SMM_API_URL = os.getenv("SMM_API_URL")
SMM_API_KEY = os.getenv("SMM_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN topilmadi")

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
            service_id TEXT,
            link TEXT,
            quantity INTEGER,
            status TEXT DEFAULT 'pending'
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

    return result[0] if result else 0


# ================= MENU =================

def main_menu():
    kb = InlineKeyboardBuilder()

    kb.button(text="🛒 Buyurtma berish", callback_data="order")
    kb.button(text="💰 Balans", callback_data="balance")
    kb.button(text="➕ Balans to‘ldirish", callback_data="deposit")
    kb.button(text="📦 Buyurtmalarim", callback_data="orders")

    kb.adjust(1)

    return kb.as_markup()


# ================= START =================

@dp.message(CommandStart())
async def start(message: Message):
    add_user(message.from_user.id)

    await message.answer(
        f"👋 Salom, {message.from_user.first_name}!\n\n"
        "🚀 SMM xizmatlar botiga xush kelibsiz!\n\n"
        "📱 Instagram\n"
        "📱 Telegram\n"
        "🎵 TikTok\n"
        "▶️ YouTube\n\n"
        "Kerakli bo‘limni tanlang:",
        reply_markup=main_menu()
    )


# ================= BALANCE =================

@dp.callback_query(F.data == "balance")
async def balance(call: CallbackQuery):
    balance = get_balance(call.from_user.id)

    await call.message.answer(
        f"💰 Sizning balansingiz:\n\n"
        f"💵 {balance:.2f} so‘m"
    )

    await call.answer()


# ================= DEPOSIT =================

@dp.callback_query(F.data == "deposit")
async def deposit(call: CallbackQuery):

    await call.message.answer(
        "➕ Balans to‘ldirish\n\n"
        "💳 To‘lov uchun admin bilan bog‘laning.\n\n"
        "👨‍💼 Admin: @YOUR_USERNAME"
    )

    await call.answer()


# ================= SERVICES =================

@dp.callback_query(F.data == "order")
async def order(call: CallbackQuery):

    kb = InlineKeyboardBuilder()

    kb.button(
        text="📸 Instagram Followers",
        callback_data="service_1"
    )

    kb.button(
        text="❤️ Instagram Likes",
        callback_data="service_2"
    )

    kb.button(
        text="👥 Telegram Members",
        callback_data="service_3"
    )

    kb.button(
        text="🎵 TikTok Followers",
        callback_data="service_4"
    )

    kb.button(
        text="▶️ YouTube Views",
        callback_data="service_5"
    )

    kb.adjust(1)

    await call.message.answer(
        "🛒 Xizmatni tanlang:",
        reply_markup=kb.as_markup()
    )

    await call.answer()


# ================= SERVICE =================

@dp.callback_query(F.data.startswith("service_"))
async def service(call: CallbackQuery):

    service_id = call.data.split("_")[1]

    await call.message.answer(
        f"✅ Xizmat ID: {service_id}\n\n"
        "🔗 Linkni yuboring:"
    )

    await call.answer()


# ================= ORDERS =================

@dp.callback_query(F.data == "orders")
async def orders(call: CallbackQuery):

    con = db()
    cur = con.cursor()

    cur.execute(
        """
        SELECT id, service_id, link, quantity, status
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
        await call.message.answer("📦 Sizda hali buyurtmalar yo‘q.")
        await call.answer()
        return

    text = "📦 Oxirgi buyurtmalaringiz:\n\n"

    for row in rows:
        text += (
            f"🆔 #{row[0]}\n"
            f"📌 Service: {row[1]}\n"
            f"🔗 {row[2]}\n"
            f"🔢 Miqdor: {row[3]}\n"
            f"📊 Status: {row[4]}\n\n"
        )

    await call.message.answer(text)
    await call.answer()


# ================= ADMIN =================

@dp.message(F.text == "/admin")
async def admin(message: Message):

    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Siz admin emassiz.")
        return

    await message.answer(
        "👨‍💼 ADMIN PANEL\n\n"
        "📊 /stats — statistika\n"
        "💰 /addbalance USER_ID SUM — balans qo‘shish"
    )


@dp.message(F.text.startswith("/addbalance"))
async def add_balance(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    try:
        parts = message.text.split()

        user_id = int(parts[1])
        amount = float(parts[2])

        con = db()
        cur = con.cursor()

        cur.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id=?",
            (amount, user_id)
        )

        con.commit()
        con.close()

        await message.answer(
            f"✅ {user_id} hisobiga {amount} so‘m qo‘shildi."
        )

    except Exception:
        await message.answer(
            "❌ Format:\n"
            "/addbalance USER_ID SUM"
        )


# ================= SMM API =================

async def smm_request(action, data=None):

    if not SMM_API_URL or not SMM_API_KEY:
        return None

    payload = {
        "key": SMM_API_KEY,
        "action": action
    }

    if data:
        payload.update(data)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                SMM_API_URL,
                data=payload,
                timeout=30
            ) as response:

                return await response.json()

    except Exception as e:
        print("API ERROR:", e)
        return None


# ================= API SERVICES =================

async def get_services():

    result = await smm_request("services")

    if not result:
        return []

    return result


# ================= MAIN =================

async def main():

    init_db()

    print("🤖 SMM BOT ISHLADI!")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
