import os
import sqlite3
import asyncio
import aiohttp
import logging
from math import ceil

from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder


# =========================================================
# CONFIG
# =========================================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SMM_API_URL = os.getenv(
    "SMM_API_URL",
    "https://seensms.uz/api/v1"
)
SMM_API_KEY = os.getenv("SMM_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

BOT_NAME = "Best1SMM"

DB_NAME = "best1smm.db"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi!")

if not SMM_API_KEY:
    raise RuntimeError("SMM_API_KEY topilmadi!")


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(BOT_NAME)


# =========================================================
# BOT
# =========================================================

bot = Bot(BOT_TOKEN)
dp = Dispatcher()


# =========================================================
# DATABASE
# =========================================================

def get_db():
    return sqlite3.connect(DB_NAME)


def init_db():

    con = get_db()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            api_order TEXT,
            service_id TEXT,
            service_name TEXT,
            category TEXT,
            link TEXT,
            quantity INTEGER,
            charge REAL,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    con.commit()
    con.close()


def register_user(user):

    con = get_db()
    cur = con.cursor()

    cur.execute("""
        INSERT OR IGNORE INTO users
        (user_id, username, first_name)
        VALUES (?, ?, ?)
    """, (
        user.id,
        user.username or "",
        user.first_name or ""
    ))

    cur.execute("""
        UPDATE users
        SET username=?, first_name=?
        WHERE user_id=?
    """, (
        user.username or "",
        user.first_name or "",
        user.id
    ))

    con.commit()
    con.close()


def get_user_balance(user_id):

    con = get_db()
    cur = con.cursor()

    cur.execute(
        "SELECT balance FROM users WHERE user_id=?",
        (user_id,)
    )

    row = cur.fetchone()

    con.close()

    return float(row[0]) if row else 0.0


def change_balance(user_id, amount):

    con = get_db()
    cur = con.cursor()

    cur.execute("""
        UPDATE users
        SET balance = balance + ?
        WHERE user_id=?
    """, (amount, user_id))

    con.commit()
    con.close()


# =========================================================
# FSM STATES
# =========================================================

class OrderState(StatesGroup):

    waiting_link = State()
    waiting_quantity = State()


class SearchState(StatesGroup):

    waiting_query = State()


class AdminState(StatesGroup):

    waiting_user_id = State()
    waiting_amount = State()


# =========================================================
# SEENSMS API
# =========================================================

async def api_request(action, **kwargs):

    payload = {
        "key": SMM_API_KEY,
        "action": action
    }

    payload.update(kwargs)

    try:

        timeout = aiohttp.ClientTimeout(total=40)

        async with aiohttp.ClientSession(
            timeout=timeout
        ) as session:

            async with session.post(
                SMM_API_URL,
                data=payload
            ) as response:

                text = await response.text()

                logger.info(
                    "API %s -> %s",
                    action,
                    response.status
                )

                try:
                    import json
                    return json.loads(text)

                except Exception:

                    return {
                        "error": text
                    }

    except asyncio.TimeoutError:

        return {
            "error": "API timeout"
        }

    except Exception as e:

        logger.exception(e)

        return {
            "error": "API bilan aloqa qilishda xatolik"
        }


async def api_services():

    return await api_request(
        "services"
    )


async def api_add_order(
    service,
    link,
    quantity
):

    return await api_request(
        "add",
        service=service,
        link=link,
        quantity=quantity
    )


async def api_status(order_id):

    return await api_request(
        "status",
        order=order_id
    )


async def api_refill(order_id):

    return await api_request(
        "refill",
        order=order_id
    )


async def api_cancel(order_id):

    return await api_request(
        "cancel",
        order=order_id
    )


async def api_balance():

    return await api_request(
        "balance"
    )


# =========================================================
# HELPERS
# =========================================================

def money(value):

    try:

        return f"{float(value):,.2f}".replace(
            ",", " "
        )

    except Exception:

        return "0.00"


def safe_text(text, limit=45):

    text = str(text)

    if len(text) > limit:

        return text[:limit - 3] + "..."

    return text


def is_admin(user_id):

    return user_id == ADMIN_ID


# =========================================================
# MAIN MENU
# =========================================================

def main_menu():

    kb = InlineKeyboardBuilder()

    kb.button(
        text="🛒 Yangi buyurtma",
        callback_data="new_order"
    )

    kb.button(
        text="📦 Buyurtmalarim",
        callback_data="my_orders"
    )

    kb.button(
        text="💰 Balansim",
        callback_data="my_balance"
    )

    kb.button(
        text="➕ Balans to‘ldirish",
        callback_data="deposit"
    )

    kb.button(
        text="🔎 Xizmat qidirish",
        callback_data="search_service"
    )

    kb.button(
        text="ℹ️ Yordam",
        callback_data="help"
    )

    kb.adjust(1)

    return kb.as_markup()


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start(message: Message):

    register_user(
        message.from_user
    )

    name = message.from_user.first_name

    await message.answer(
        f"""
✨ <b>BEST1SMM</b> ga xush kelibsiz! ✨

Assalomu alaykum, <b>{name}</b>! 👋

🚀 Bu yerda SMM xizmatlarini
tez va qulay buyurtma qilishingiz mumkin.

📸 Instagram
📱 Telegram
🎵 TikTok
▶️ YouTube

━━━━━━━━━━━━━━━━━━

💰 Balans: <b>{money(get_user_balance(message.from_user.id))} so‘m</b>

👇 Kerakli bo‘limni tanlang:
""",
        reply_markup=main_menu()
    )


# =========================================================
# BACK BUTTON
# =========================================================

def back_menu():

    kb = InlineKeyboardBuilder()

    kb.button(
        text="⬅️ Bosh menyu",
        callback_data="home"
    )

    return kb.as_markup()


@dp.callback_query(F.data == "home")
async def home(call: CallbackQuery, state: FSMContext):

    await state.clear()

    await call.message.edit_text(
        "🏠 <b>BEST1SMM</b>\n\n"
        "Kerakli bo‘limni tanlang:",
        reply_markup=main_menu()
    )

    await call.answer()


# =========================================================
# BALANCE
# =========================================================

@dp.callback_query(F.data == "my_balance")
async def my_balance(call: CallbackQuery):

    register_user(
        call.from_user
    )

    balance = get_user_balance(
        call.from_user.id
    )

    await call.message.edit_text(
        f"""
💰 <b>SIZNING BALANSINGIZ</b>

💵 {money(balance)} so‘m

━━━━━━━━━━━━━━━━━━

Balansni to‘ldirib xizmatlardan
foydalanishingiz mumkin.
""",
        reply_markup=back_menu()
    )

    await call.answer()


# =========================================================
# DEPOSIT
# =========================================================

@dp.callback_query(F.data == "deposit")
async def deposit(call: CallbackQuery):

    await call.message.edit_text(
        """
➕ <b>BALANS TO‘LDIRISH</b>

Balansni to‘ldirish uchun
administrator bilan bog‘laning.

👨‍💼 Admin:
@YOUR_ADMIN_USERNAME

━━━━━━━━━━━━━━━━━━

⚠️ To‘lovni faqat administrator
ko‘rsatgan rasmiy usul orqali amalga oshiring.
""",
        reply_markup=back_menu()
    )

    await call.answer()


# =========================================================
# LOAD SERVICES
# =========================================================

async def load_services():

    result = await api_services()

    if not isinstance(result, list):

        return []

    return result


# =========================================================
# CATEGORIES
# =========================================================

@dp.callback_query(F.data == "new_order")
async def new_order(call: CallbackQuery):

    services = await load_services()

    if not services:

        await call.message.edit_text(
            "❌ Xizmatlarni olishning iloji bo‘lmadi.\n"
            "Keyinroq qayta urinib ko‘ring.",
            reply_markup=back_menu()
        )

        await call.answer()
        return

    categories = sorted(
        set(
            str(
                x.get("category", "Boshqa")
            )
            for x in services
        )
    )

    kb = InlineKeyboardBuilder()

    for category in categories:

        kb.button(
            text=f"📂 {safe_text(category, 38)}",
            callback_data=f"cat:{category[:45]}"
        )

    kb.adjust(1)

    await call.message.edit_text(
        f"""
🛒 <b>YANGI BUYURTMA</b>

📦 Jami xizmatlar:
<b>{len(services)}</b>

👇 Kategoriyani tanlang:
""",
        reply_markup=kb.as_markup()
    )

    await call.answer()


# =========================================================
# CATEGORY SERVICES
# =========================================================

@dp.callback_query(F.data.startswith("cat:"))
async def category_services(call: CallbackQuery):

    category = call.data[4:]

    services = await load_services()

    filtered = [
        x for x in services
        if str(
            x.get("category", "Boshqa")
        )[:45] == category
    ]

    if not filtered:

        await call.message.edit_text(
            "❌ Bu kategoriyada xizmat topilmadi.",
            reply_markup=back_menu()
        )

        await call.answer()
        return

    await show_services(
        call,
        filtered,
        category,
        0
    )


# =========================================================
# SHOW SERVICES
# =========================================================

async def show_services(
    call,
    services,
    category,
    page
):

    per_page = 8

    total_pages = max(
        1,
        ceil(len(services) / per_page)
    )

    if page < 0:
        page = total_pages - 1

    if page >= total_pages:
        page = 0

    start = page * per_page

    current = services[
        start:start + per_page
    ]

    kb = InlineKeyboardBuilder()

    for service in current:

        sid = str(
            service.get("service", "")
        )

        name = safe_text(
            service.get("name", "Xizmat")
        )

        kb.button(
            text=f"🛒 {sid} | {name}",
            callback_data=f"view:{sid}"
        )

    if total_pages > 1:

        kb.button(
            text="◀️",
            callback_data=f"page:{category}:{page - 1}"
        )

        kb.button(
            text=f"{page + 1}/{total_pages}",
            callback_data="nothing"
        )

        kb.button(
            text="▶️",
            callback_data=f"page:{category}:{page + 1}"
        )

    kb.button(
        text="⬅️ Kategoriyalar",
        callback_data="new_order"
    )

    kb.adjust(1)

    await call.message.edit_text(
        f"""
📂 <b>{category}</b>

📦 Xizmatlar: {len(services)}

👇 Kerakli xizmatni tanlang:
""",
        reply_markup=kb.as_markup()
    )


# =========================================================
# PAGINATION
# =========================================================

@dp.callback_query(F.data.startswith("page:"))
async def pagination(call: CallbackQuery):

    _, category, page = call.data.split(
        ":",
        2
    )

    page = int(page)

    services = await load_services()

    filtered = [
        x for x in services
        if str(
            x.get("category", "Boshqa")
        )[:45] == category
    ]

    await show_services(
        call,
        filtered,
        category,
        page
    )

    await call.answer()


@dp.callback_query(F.data == "nothing")
async def nothing(call: CallbackQuery):

    await call.answer()


# =========================================================
# SERVICE DETAILS
# =========================================================

@dp.callback_query(F.data.startswith("view:"))
async def service_details(call: CallbackQuery):

    service_id = call.data.split(
        ":",
        1
    )[1]

    services = await load_services()

    service = next(
        (
            x for x in services
            if str(
                x.get("service")
            ) == service_id
        ),
        None
    )

    if not service:

        await call.answer(
            "Xizmat topilmadi!",
            show_alert=True
        )

        return

    name = service.get(
        "name",
        "Xizmat"
    )

    category = service.get(
        "category",
        "Boshqa"
    )

    rate = service.get(
        "rate",
        0
    )

    minimum = service.get(
        "min",
        0
    )

    maximum = service.get(
        "max",
        0
    )

    refill = service.get(
        "refill",
        False
    )

    cancel = service.get(
        "cancel",
        False
    )

    refill_text = (
        "✅ Mavjud"
        if refill
        else "❌ Yo‘q"
    )

    cancel_text = (
        "✅ Mavjud"
        if cancel
        else "❌ Yo‘q"
    )

    kb = InlineKeyboardBuilder()

    kb.button(
        text="🛒 BUYURTMA BERISH",
        callback_data=f"buy:{service_id}"
    )

    kb.button(
        text="⬅️ Orqaga",
        callback_data="new_order"
    )

    kb.adjust(1)

    await call.message.edit_text(
        f"""
📋 <b>XIZMAT MA'LUMOTI</b>

🆔 ID: <code>{service_id}</code>

📌 <b>{name}</b>

📂 Kategoriya:
{category}

💵 Narx:
<b>{rate}</b> so‘m / 1000

🔢 Minimum:
<b>{minimum}</b>

🔢 Maximum:
<b>{maximum}</b>

♻️ Refill:
{refill_text}

❌ Cancel:
{cancel_text}

━━━━━━━━━━━━━━━━━━

👇 Buyurtma berish uchun tugmani bosing:
""",
        reply_markup=kb.as_markup()
    )

    await call.answer()


# =========================================================
# BUY
# =========================================================

@dp.callback_query(F.data.startswith("buy:"))
async def buy_service(
    call: CallbackQuery,
    state: FSMContext
):

    service_id = call.data.split(
        ":",
        1
    )[1]

    services = await load_services()

    service = next(
        (
            x for x in services
            if str(
                x.get("service")
            ) == service_id
        ),
        None
    )

    if not service:

        await call.answer(
            "Xizmat topilmadi!",
            show_alert=True
        )

        return

    await state.update_data(
        service_id=service_id,
        service_name=service.get(
            "name",
            "Xizmat"
        ),
        category=service.get(
            "category",
            "Boshqa"
        ),
        rate=float(
            service.get(
                "rate",
                0
            )
        ),
        minimum=int(
            service.get(
                "min",
                0
            )
        ),
        maximum=int(
            service.get(
                "max",
                0
            )
        )
    )

    await call.message.answer(
        f"""
🔗 <b>HAVOLANI YUBORING</b>

📌 Xizmat:
{service.get('name', 'Xizmat')}

🆔 ID:
{service_id}

Misol:
<code>https://instagram.com/...</code>

👇 Linkni yuboring:
"""
    )

    await state.set_state(
        OrderState.waiting_link
    )

    await call.answer()


# =========================================================
# LINK
# =========================================================

@dp.message(OrderState.waiting_link)
async def order_link(
    message: Message,
    state: FSMContext
):

    link = (message.text or "").strip()

    if not link.startswith(
        ("http://", "https://")
    ):

        await message.answer(
            "❌ Iltimos, to‘g‘ri link yuboring."
        )

        return

    await state.update_data(
        link=link
    )

    data = await state.get_data()

    await message.answer(
        f"""
🔢 <b>MIQDORNI YUBORING</b>

Minimum: <b>{data['minimum']}</b>
Maximum: <b>{data['maximum']}</b>

Masalan:
<code>1000</code>
"""
    )

    await state.set_state(
        OrderState.waiting_quantity
    )


# =========================================================
# QUANTITY
# =========================================================

@dp.message(OrderState.waiting_quantity)
async def order_quantity(
    message: Message,
    state: FSMContext
):

    try:

        quantity = int(
            (message.text or "").strip()
        )

    except ValueError:

        await message.answer(
            "❌ Miqdor faqat raqam bo‘lishi kerak."
        )

        return

    data = await state.get_data()

    minimum = data["minimum"]
    maximum = data["maximum"]
    rate = data["rate"]

    if quantity < minimum:

        await message.answer(
            f"❌ Minimal miqdor: {minimum}"
        )

        return

    if quantity > maximum:

        await message.answer(
            f"❌ Maksimal miqdor: {maximum}"
        )

        return

    charge = (
        rate * quantity
    ) / 1000

    balance = get_user_balance(
        message.from_user.id
    )

    if balance < charge:

        await message.answer(
            f"""
❌ <b>BALANS YETARLI EMAS</b>

💰 Buyurtma narxi:
<b>{money(charge)} so‘m</b>

💳 Sizning balansingiz:
<b>{money(balance)} so‘m</b>

📉 Yetishmayapti:
<b>{money(charge - balance)} so‘m</b>

Avval balansni to‘ldiring.
""",
            reply_markup=main_menu()
        )

        await state.clear()

        return

    await message.answer(
        "⏳ <b>BUYURTMA YUBORILMOQDA...</b>"
    )

    result = await api_add_order(
        service=data["service_id"],
        link=data["link"],
        quantity=quantity
    )

    if not isinstance(result, dict):

        await message.answer(
            "❌ API noto‘g‘ri javob qaytardi."
        )

        await state.clear()

        return

    if "error" in result:

        await message.answer(
            f"""
❌ <b>BUYURTMA BERILMADI</b>

Sabab:
{result.get('error')}
"""
        )

        await state.clear()

        return

    api_order = result.get(
        "order"
    )

    if not api_order:

        await message.answer(
            "❌ API order ID qaytarmadi."
        )

        await state.clear()

        return

    # User balansidan yechish
    change_balance(
        message.from_user.id,
        -charge
    )

    # Database
    con = get_db()
    cur = con.cursor()

    cur.execute("""
        INSERT INTO orders
        (
            user_id,
            api_order,
            service_id,
            service_name,
            category,
            link,
            quantity,
            charge,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        message.from_user.id,
        str(api_order),
        data["service_id"],
        data["service_name"],
        data["category"],
        data["link"],
        quantity,
        charge,
        "Pending"
    ))

    con.commit()
    con.close()

    new_balance = get_user_balance(
        message.from_user.id
    )

    await message.answer(
        f"""
🎉 <b>BUYURTMA QABUL QILINDI!</b>

━━━━━━━━━━━━━━━━━━

🆔 Order:
<code>#{api_order}</code>

📦 Xizmat:
{data['service_name']}

🔢 Miqdor:
<b>{quantity}</b>

💰 Narx:
<b>{money(charge)} so‘m</b>

📊 Status:
<b>Pending</b>

━━━━━━━━━━━━━━━━━━

💳 Qolgan balans:
<b>{money(new_balance)} so‘m</b>

Buyurtma bajarilishi boshlanganda
status avtomatik yangilanadi.
""",
        reply_markup=main_menu()
    )

    await state.clear()


# =========================================================
# MY ORDERS
# =========================================================

@dp.callback_query(F.data == "my_orders")
async def my_orders(call: CallbackQuery):

    con = get_db()
    cur = con.cursor()

    cur.execute("""
        SELECT
            api_order,
            service_name,
            quantity,
            charge,
            status
        FROM orders
        WHERE user_id=?
        ORDER BY id DESC
        LIMIT 10
    """, (
        call.from_user.id,
    ))

    rows = cur.fetchall()

    con.close()

    if not rows:

        await call.message.edit_text(
            "📦 Sizda hali buyurtmalar yo‘q.",
            reply_markup=back_menu()
        )

        await call.answer()

        return

    text = "📦 <b>OXIRGI BUYURTMALAR</b>\n\n"

    for row in rows:

        order_id = row[0]
        name = safe_text(row[1], 35)
        quantity = row[2]
        charge = row[3]
        status = row[4]

        text += (
            f"🆔 <code>#{order_id}</code>\n"
            f"📌 {name}\n"
            f"🔢 {quantity}\n"
            f"💰 {money(charge)} so‘m\n"
            f"📊 {status}\n"
            f"────────────\n"
        )

    await call.message.edit_text(
        text,
        reply_markup=back_menu()
    )

    await call.answer()


# =========================================================
# SEARCH
# =========================================================

@dp.callback_query(F.data == "search_service")
async def search_service(
    call: CallbackQuery,
    state: FSMContext
):

    await call.message.edit_text(
        """
🔎 <b>XIZMAT QIDIRISH</b>

Xizmat nomini yoki ID'sini yuboring.

Masalan:
<code>instagram</code>

yoki:

<code>7</code>
"""
    )

    await state.set_state(
        SearchState.waiting_query
    )

    await call.answer()


@dp.message(SearchState.waiting_query)
async def search_result(
    message: Message,
    state: FSMContext
):

    query = (
        message.text or ""
    ).lower().strip()

    services = await load_services()

    results = []

    for service in services:

        name = str(
            service.get("name", "")
        ).lower()

        sid = str(
            service.get("service", "")
        ).lower()

        category = str(
            service.get("category", "")
        ).lower()

        if (
            query in name
            or query in sid
            or query in category
        ):

            results.append(service)

    if not results:

        await message.answer(
            "❌ Hech narsa topilmadi.",
            reply_markup=main_menu()
        )

        await state.clear()

        return

    kb = InlineKeyboardBuilder()

    for service in results[:30]:

        sid = str(
            service.get("service")
        )

        name = safe_text(
            service.get("name", "Xizmat")
        )

        kb.button(
            text=f"🛒 {sid} | {name}",
            callback_data=f"view:{sid}"
        )

    kb.adjust(1)

    await message.answer(
        f"🔎 <b>{len(results)}</b> ta natija topildi:",
        reply_markup=kb.as_markup()
    )

    await state.clear()


# =========================================================
# HELP
# =========================================================

@dp.callback_query(F.data == "help")
async def help_menu(call: CallbackQuery):

    await call.message.edit_text(
        """
ℹ️ <b>BEST1SMM YORDAM</b>

🛒 <b>Yangi buyurtma</b>
Xizmat tanlab, link va miqdorni yuborasiz.

💰 <b>Balans</b>
Hisobingizdagi mablag‘ni ko‘rasiz.

📦 <b>Buyurtmalarim</b>
Oldingi buyurtmalaringizni ko‘rasiz.

🔎 <b>Xizmat qidirish</b>
Xizmat nomi yoki ID orqali qidirasiz.

➕ <b>Balans to‘ldirish</b>
Administrator orqali amalga oshiriladi.

━━━━━━━━━━━━━━━━━━

👨‍💼 Support:
@YOUR_ADMIN_USERNAME
""",
        reply_markup=back_menu()
    )

    await call.answer()


# =========================================================
# STATUS COMMAND
# =========================================================

@dp.message(Command("status"))
async def status_command(message: Message):

    parts = (
        message.text or ""
    ).split()

    if len(parts) != 2:

        await message.answer(
            "❌ Misol:\n/status 12345"
        )

        return

    order_id = parts[1]

    result = await api_status(
        order_id
    )

    if "error" in result:

        await message.answer(
            f"❌ {result['error']}"
        )

        return

    await message.answer(
        f"""
📊 <b>BUYURTMA STATUSI</b>

🆔 Order:
<code>#{order_id}</code>

📊 Status:
<b>{result.get('status', 'Unknown')}</b>

🔢 Boshlang‘ich:
{result.get('start_count', '-')}

📉 Qoldiq:
{result.get('remains', '-')}

💰 Charge:
{result.get('charge', '-')}

💱 Valyuta:
{result.get('currency', 'UZS')}
"""
    )


# =========================================================
# ADMIN
# =========================================================

def admin_menu():

    kb = InlineKeyboardBuilder()

    kb.button(
        text="📊 Statistika",
        callback_data="admin_stats"
    )

    kb.button(
        text="💰 Balans qo‘shish",
        callback_data="admin_add_balance"
    )

    kb.button(
        text="💳 Panel balansi",
        callback_data="admin_panel_balance"
    )

    kb.button(
        text="📦 Buyurtmalar",
        callback_data="admin_orders"
    )

    kb.button(
        text="🏠 Bosh menyu",
        callback_data="home"
    )

    kb.adjust(1)

    return kb.as_markup()


@dp.message(Command("admin"))
async def admin_command(message: Message):

    if not is_admin(
        message.from_user.id
    ):

        await message.answer(
            "❌ Ruxsat yo‘q."
        )

        return

    await message.answer(
        """
👨‍💼 <b>BEST1SMM ADMIN PANEL</b>

Kerakli bo‘limni tanlang:
""",
        reply_markup=admin_menu()
    )


# =========================================================
# ADMIN STATS
# =========================================================

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(
    call: CallbackQuery
):

    if not is_admin(
        call.from_user.id
    ):

        await call.answer(
            "Ruxsat yo‘q!",
            show_alert=True
        )

        return

    con = get_db()
    cur = con.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM users"
    )

    users = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM orders"
    )

    orders = cur.fetchone()[0]

    cur.execute(
        "SELECT COALESCE(SUM(charge), 0) FROM orders"
    )

    revenue = cur.fetchone()[0]

    con.close()

    await call.message.edit_text(
        f"""
📊 <b>STATISTIKA</b>

👥 Foydalanuvchilar:
<b>{users}</b>

📦 Buyurtmalar:
<b>{orders}</b>

💰 Buyurtmalar summasi:
<b>{money(revenue)} so‘m</b>
""",
        reply_markup=admin_menu()
    )

    await call.answer()


# =========================================================
# ADMIN PANEL BALANCE
# =========================================================

@dp.callback_query(F.data == "admin_panel_balance")
async def admin_panel_balance(
    call: CallbackQuery
):

    if not is_admin(
        call.from_user.id
    ):

        return

    result = await api_balance()

    if "error" in result:

        await call.message.edit_text(
            f"❌ API xatosi:\n{result['error']}",
            reply_markup=admin_menu()
        )

        return

    await call.message.edit_text(
        f"""
💳 <b>SEENSMS PANEL BALANSI</b>

💰 {result.get('balance', '0')}

💱 {result.get('currency', 'UZS')}
""",
        reply_markup=admin_menu()
    )

    await call.answer()


# =========================================================
# ADMIN ADD BALANCE
# =========================================================

@dp.callback_query(F.data == "admin_add_balance")
async def admin_add_balance(
    call: CallbackQuery,
    state: FSMContext
):

    if not is_admin(
        call.from_user.id
    ):

        return

    await call.message.edit_text(
        """
💰 <b>BALANS QO‘SHISH</b>

Avval foydalanuvchining Telegram ID'sini yuboring.

Masalan:
<code>123456789</code>
"""
    )

    await state.set_state(
        AdminState.waiting_user_id
    )

    await call.answer()


@dp.message(AdminState.waiting_user_id)
async def admin_user_id(
    message: Message,
    state: FSMContext
):

    if not is_admin(
        message.from_user.id
    ):

        return

    try:

        user_id = int(
            message.text.strip()
        )

    except Exception:

        await message.answer(
            "❌ ID raqam bo‘lishi kerak."
        )

        return

    await state.update_data(
        user_id=user_id
    )

    await message.answer(
        """
💵 Endi qancha balans qo‘shamiz?

Masalan:
<code>10000</code>
"""
    )

    await state.set_state(
        AdminState.waiting_amount
    )


@dp.message(AdminState.waiting_amount)
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
            message.text.strip()
        )

    except Exception:

        await message.answer(
            "❌ Summani to‘g‘ri kiriting."
        )

        return

    if amount <= 0:

        await message.answer(
            "❌ Summa 0 dan katta bo‘lishi kerak."
        )

        return

    data = await state.get_data()

    user_id = data["user_id"]

    # Agar user mavjud bo'lmasa
    con = get_db()
    cur = con.cursor()

    cur.execute(
        "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
        (user_id,)
    )

    con.commit()
    con.close()

    change_balance(
        user_id,
        amount
    )

    await message.answer(
        f"""
✅ <b>BALANS QO‘SHILDI</b>

👤 User:
<code>{user_id}</code>

💰 Qo‘shildi:
<b>{money(amount)} so‘m</b>

💳 Yangi balans:
<b>{money(get_user_balance(user_id))} so‘m</b>
""",
        reply_markup=admin_menu()
    )

    await state.clear()


# =========================================================
# ADMIN ORDERS
# =========================================================

@dp.callback_query(F.data == "admin_orders")
async def admin_orders(
    call: CallbackQuery
):

    if not is_admin(
        call.from_user.id
    ):

        return

    con = get_db()
    cur = con.cursor()

    cur.execute("""
        SELECT
            api_order,
            user_id,
            service_name,
            quantity,
            charge,
            status
        FROM orders
        ORDER BY id DESC
        LIMIT 15
    """)

    rows = cur.fetchall()

    con.close()

    if not rows:

        text = "📦 Hali buyurtmalar yo‘q."

    else:

        text = "📦 <b>OXIRGI BUYURTMALAR</b>\n\n"

        for row in rows:

            text += (
                f"🆔 #{row[0]}\n"
                f"👤 {row[1]}\n"
                f"📌 {safe_text(row[2], 30)}\n"
                f"🔢 {row[3]}\n"
                f"💰 {money(row[4])}\n"
                f"📊 {row[5]}\n"
                f"──────────\n"
            )

    await call.message.edit_text(
        text,
        reply_markup=admin_menu()
    )

    await call.answer()


# =========================================================
# REFILL
# =========================================================

@dp.message(Command("refill"))
async def refill_command(
    message: Message
):

    parts = (
        message.text or ""
    ).split()

    if len(parts) != 2:

        await message.answer(
            "❌ Misol:\n/refill 12345"
        )

        return

    order_id = parts[1]

    result = await api_refill(
        order_id
    )

    if "error" in result:

        await message.answer(
            f"❌ Refill xatosi:\n{result['error']}"
        )

        return

    await message.answer(
        f"""
♻️ <b>REFILL YUBORILDI</b>

🆔 Order:
<code>#{order_id}</code>

Natija:
<code>{result}</code>
"""
    )


# =========================================================
# CANCEL
# =========================================================

@dp.message(Command("cancel"))
async def cancel_command(
    message: Message
):

    parts = (
        message.text or ""
    ).split()

    if len(parts) != 2:

        await message.answer(
            "❌ Misol:\n/cancel 12345"
        )

        return

    order_id = parts[1]

    result = await api_cancel(
        order_id
    )

    if "error" in result:

        await message.answer(
            f"❌ Cancel xatosi:\n{result['error']}"
        )

        return

    await message.answer(
        f"""
❌ <b>BEKOR QILISH SO‘ROVI YUBORILDI</b>

🆔 Order:
<code>#{order_id}</code>

Natija:
<code>{result}</code>
"""
    )


# =========================================================
# UNKNOWN COMMAND
# =========================================================

@dp.message(Command("help"))
async def command_help(
    message: Message
):

    await message.answer(
        """
ℹ️ <b>BEST1SMM</b>

/start — bosh menyu
/status ID — buyurtma statusi
/refill ID — refill
/cancel ID — cancel
/admin — admin panel
"""
    )


# =========================================================
# START BOT
# =========================================================

async def main():

    init_db()

    logger.info(
        "🚀 BEST1SMM BOT IS RUNNING"
    )

    await dp.start_polling(
        bot
    )


if __name__ == "__main__":

    try:

        asyncio.run(main())

    except KeyboardInterrupt:

        logger.info(
            "Bot stopped"
    )
