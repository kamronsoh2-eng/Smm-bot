    import asyncio, logging, sqlite3
    from aiogram import Bot, Dispatcher, F
    from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
    from aiogram.filters import CommandStart, Command
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.state import State, StatesGroup

    logging.basicConfig(level=logging.INFO)
    
    # 🔑 SIZNING BOT TOKENINGIZ VA ADMIN ID RAQAMINGIZ
    BOT_TOKEN = "8995891257:AAErSCtwPrz23xfae3oxWCraShOfKsgnCLO"
    ADMIN_ID = 8995891257

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # 🗄 MULTI-BAZA TIZIMI (SQLite3)
    conn = sqlite3.connect("smm_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        name TEXT,
        balance INTEGER DEFAULT 50000,
        orders_count INTEGER DEFAULT 0,
        auto_smm TEXT DEFAULT 'Faol emas ❌'
    )
    """)
    conn.commit()

    # 💰 PROFESSIONAL SMM NARXLARI (1 dona uchun so'mda)
    PRICES = {
        "yt_views": 12, "yt_subs": 60, "yt_likes": 30,
        "tt_views": 4, "tt_subs": 40, "tt_likes": 20,
        "tg_views": 2, "tg_subs": 35, "tg_likes": 15,
        "ins_views": 3, "ins_subs": 45, "ins_likes": 25,
        "auto_smm_monthly": 25000
    }

    class BotStates(StatesGroup):
        waiting_for_amount = State()
        waiting_for_link = State()
        waiting_for_deposit = State()
        waiting_for_broadcast = State()

    def db_get_user(user_id, name="Mijoz"):
        cursor.execute("SELECT name, balance, orders_count, auto_smm FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            cursor.execute("INSERT INTO users (user_id, name) VALUES (?, ?)", (user_id, name))
            conn.commit()
            return {"name": name, "balance": 50000, "orders": 0, "auto_smm": "Faol emas ❌"}
        return {"name": row[0], "balance": row[1], "orders": row[2], "auto_smm": row[3]}

    def db_update_balance(user_id, amount):
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()

    def db_increment_orders(user_id):
        cursor.execute("UPDATE users SET orders_count = orders_count + 1 WHERE user_id = ?", (user_id,))
        conn.commit()

    def db_set_auto_smm(user_id, status):
        cursor.execute("UPDATE users SET auto_smm = ? WHERE user_id = ?", (status, user_id))
        conn.commit()

    # 🌟 1. ASOSIY START MENYU
    @dp.message(CommandStart())
    async def cmd_start(message: Message):
        user = db_get_user(message.from_user.id, message.from_user.full_name)
        kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🛒 Buyurtma berish"), KeyboardButton(text="🚀 Avto SMM Premium")],
                [KeyboardButton(text="💳 Hisobni to'ldirish"), KeyboardButton(text="👤 Shaxsiy kabinet")]
            ],
            resize_keyboard=True
        )
        welcome = f"👑 **Salom, {user['name']}!**\n\n🔥 Dunyodagi eng tezkor va eng arzon **AVTO SMM IMPERIYA** botiga xush kelibsiz!\n⚡ Biz bilan ijtimoiy tarmoqlaringizni chaqmoq tezligida eng yuqori cho'qqiga olib chiqing.\n\n👇 Kerakli bo'limni tanlang:"
        await message.answer(welcome, reply_markup=kb, parse_mode="Markdown")

    # 👤 2. SHAXSIY KABINET
    @dp.message(F.text == "👤 Shaxsiy kabinet")
    async def view_cabinet(message: Message):
        user = db_get_user(message.from_user.id, message.from_user.full_name)
        cabinet = f"👤 **MIJOZ PROFILI (PANEL)**\n\n🆔 ID Raqamingiz: `{message.from_user.id}`\n💎 Ismingiz: {user['name']}\n💰 Balansingiz: {user['balance']:,} so'm\n📦 Jami buyurtmalar: {user['orders']} ta\n🚀 Avto SMM statusi: {user['auto_smm']}\n\n📈 _Xizmatlarimiz sizga eng yuqori sifatni kafolatlaydi!_"
        await message.answer(cabinet, parse_mode="Markdown")

    # 💳 3. HISOBNI TO'LDIRISH
    @dp.message(F.text == "💳 Hisobni to'ldirish")
    async def top_up_balance(message: Message):
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💳 Click / Payme (Avtomat)", callback_data="deposit_card")],
                [InlineKeyboardButton(text="🏦 Bank hisobi (Kassa)", callback_data="deposit_bank")]
            ]
        )
        text = "💰 **Hisobni to'ldirish tizimi**\n\nTo'lov uslubini tanlang. Mablag'ingiz balansingizga lahzada qo'shiladi:"
        await message.answer(text, reply_markup=kb, parse_mode="Markdown")

    @dp.callback_query(F.data == "deposit_card")
    async def deposit_card_info(callback: CallbackQuery, state: FSMContext):
        await callback.message.answer("💸 **To'lov cheki yuborish tizimi:**\n\nKartaga pul o'tkazing: `8600555544443333` (SMM Ma'muri)\n\nO'tkazgan summani (masalan: 50000) faqat raqamda botga yozing:")
        await state.set_state(BotStates.waiting_for_deposit)
        await callback.answer()

    @dp.message(BotStates.waiting_for_deposit)
    async def process_deposit(message: Message, state: FSMContext):
        if not message.text.isdigit():
            await message.answer("❌ Xato! Faqat raqam kiriting:")
            return
        amount = int(message.text)
        db_update_balance(message.from_user.id, amount)
        user = db_get_user(message.from_user.id)
        await message.answer(f"✅ Muvaffaqiyatli! Balansingizga {amount:,} so'm qo'shildi!\nHozirgi jami balans: {user['balance']:,} so'm.")
        await state.clear()

    # 🚀 4. AVTO SMM PREMIUM ULTRA MODELI
    @dp.message(F.text == "🚀 Avto SMM Premium")
    async def auto_smm_menu(message: Message):
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔥 Aktivlashtirish (25,000 so'm/oy)", callback_data="activate_premium")]]
        )
        text = f"🚀 **AVTO SMM PREMIUM TIZIMI**\n\nBu tizim orqali bot barcha kanallaringizni avtomatik nazorat qiladi. Yangi post joylashingiz bilanoq hech qanday buyurtmasiz bot o'zi unga ko'rishlar, layklar haydav beradi!\n\n💵 Oylik obuna narxi: *25,000 so'm*"
        await message.answer(text, reply_markup=kb, parse_mode="Markdown")

    @dp.callback_query(F.data == "activate_premium")
    async def run_premium(callback: CallbackQuery):
        user = db_get_user(callback.from_user.id)
        if user["balance"] < PRICES["auto_smm_monthly"]:
            await callback.message.answer("❌ Balansingizda yetarli mablag' mavjud emas. Iltimos hisobni to'ldiring!")
        else:
            db_update_balance(callback.from_user.id, -PRICES["auto_smm_monthly"])
            db_set_auto_smm(callback.from_user.id, "Faol 🔥 (Premium)")
            await callback.message.answer("🚀 Dahshat! Avto SMM Premium tizimi 1 oyga muvaffaqiyatli yoqildi!")
        await callback.answer()

    # 🛒 5. BUYURTMA BERISH PANEL
    @dp.message(F.text == "🛒 Buyurtma berish")
    async def init_order(message: Message):
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔴 YouTube", callback_data="net_yt"), InlineKeyboardButton(text="🔵 Telegram", callback_data="net_tg")],
                [InlineKeyboardButton(text="⚫ TikTok", callback_data="net_tt"), InlineKeyboardButton(text="🟣 Instagram", callback_data="net_ins")]
            ]
        )
        await message.answer("🌐 Buyurtma bermoqchi bo'lgan ijtimoiy tarmoqni tanlang:", reply_markup=kb)

    @dp.callback_query(F.data.startswith("net_"))
    async def choose_service(callback: CallbackQuery):
        net = callback.data.split("_")[1]
        kb_list = []
        if net == "yt":
            kb_list = [
                [InlineKeyboardButton(text="👁 Ko'rishlar (12 so'm)", callback_data="select_yt_views")],
                [InlineKeyboardButton(text="👥 Obunachilar (60 so'm)", callback_data="select_yt_subs")],
                [InlineKeyboardButton(text="❤️ Layklar (30 so'm)", callback_data="select_yt_likes")]
            ]
        elif net == "tt":
            kb_list = [
                [InlineKeyboardButton(text="👁 Ko'rishlar (4 so'm)", callback_data="select_tt_views")],
                [InlineKeyboardButton(text="👥 Obunachilar (40 so'm)", callback_data="select_tt_subs")],
                [InlineKeyboardButton(text="❤️ Layklar (20 so'm)", callback_data="select_tt_likes")]
            ]
        elif net == "tg":
            kb_list = [
                [InlineKeyboardButton(text="👁 Ko'rishlar (2 so'm)", callback_data="select_tg_views")],
                [InlineKeyboardButton(text="👥 Obunachilar (35 so'm)", callback_data="select_tg_subs")],
                [InlineKeyboardButton(text="❤️ Reaksiyalar (15 so'm)", callback_data="select_tg_likes")]
            ]
        elif net == "ins":
            kb_list = [
                [InlineKeyboardButton(text="👁 Ko'rishlar (3 so'm)", callback_data="select_ins_views")],
                [InlineKeyboardButton(text="👥 Obunachilar (45 so'm)", callback_data="select_ins_subs")],
                [InlineKeyboardButton(text="❤️ Layklar (25 so'm)", callback_data="select_ins_likes")]
            ]
        kb = InlineKeyboardMarkup(inline_keyboard=kb_list)
        await callback.message.answer("⚙️ Kerakli SMM xizmati turini tanlang:", reply_markup=kb)
        await callback.answer()

    @dp.callback_query(F.data.startswith("select_"))
    async def ask_amount(callback: CallbackQuery, state: FSMContext):
        service = callback.data.replace("select_", "")
        await state.update_data(current_service=service)
        await callback.message.answer("🔢 Qancha miqdorda buyurtma qilmoqchisiz?\n(Faqat raqam kiriting, masalan: 1000):")
        await state.set_state(BotStates.waiting_for_amount)
        await callback.answer()

    @dp.message(BotStates.waiting_for_amount)
    async def check_finances(message: Message, state: FSMContext):
        if not message.text.isdigit():
await message.answer("❌ Faqat raqam kiriting:")
return
amount = int(message.text)
data = await state.get_data()
service = data.get("current_service")
cost_per_one = PRICES.get(service, 10)
total_cost = amount * cost_per_one
user = db_get_user(message.from_user.id)
if user["balance"] < total_cost:
await message.answer(f"❌ Buyurtma rad etildi! Mablag' yetarli emas.\n💰 Jami narx: {total_cost:,} so'm.\n💳 Balansingiz: {user['balance']:,} so'm.")
await state.clear()
else:
await state.update_data(final_amount=amount, final_cost=total_cost)
await message.answer(f"📊 Miqdor: {amount} ta\n💰 Jami summa: {total_cost:,} so'm daxshat!\n\n🔗 Endi xizmat bajarilishi kerak bo'lgan havola (LINK) manzilini yuboring:")
await state.set_state(BotStates.waiting_for_link)
@dp.message(BotStates.waiting_for_link)
async def execute_smm_order(message: Message, state: FSMContext):
link = message.text
data = await state.get_data()
amount = data.get("final_amount")
cost = data.get("final_cost")
db_update_balance(message.from_user.id, -cost)
db_increment_orders(message.from_user.id)
user = db_get_user(message.from_user.id)
success = f"🚀 ZOOOR! BUYURTMA MUVAFFAQIYATLI QABUL QILINDI! ✅\n\n📊 Miqdori: {amount} ta\n🔗 Havola: {link}\n💸 Balansdan chegirildi: {cost:,} so'm\n💳 Qolgan jami balansingiz: {user['balance']:,} so'm\n\n⏱ Xizmat yaqin daqiqalar ichida to'liq yakunlanadi!"
await message.answer(success, parse_mode="Markdown")
await state.clear()
# 👑 6. MAXFIY ADMIN PANEL
@dp.message(Command("admin"))
async def admin_panel(message: Message):
if message.from_user.id != ADMIN_ID:
return
cursor.execute("SELECT COUNT(*) FROM users")
total_users = cursor.fetchone()
kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📣 Reklama tarqatish (Rassilka)", callback_data="admin_broadcast")]])
await message.answer(f"👑 XUSH KELIBSIZ, ADMIN!\n\n📊 Botdagi jami a'zolar: {total_users[0]} ta", reply_markup=kb)
@dp.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
await callback.message.answer("📣 Reklama matnini yuboring:")
await state.set_state(BotStates.waiting_for_broadcast)
await callback.answer()
@dp.message(BotStates.waiting_for_broadcast)
async def send_broadcast(message: Message, state: FSMContext):
cursor.execute("SELECT user_id FROM users")
all_users = cursor.fetchall()
count = 0
for u in all_users:
try:
await bot.send_message(chat_id=u[0], text=message.text)
count += 1
await asyncio.sleep(0.05)
except:
continue
await message.answer(f"✅ Reklama {count} ta foydalanuvchiga muvaffaqiyatli yuborildi!")
await state.clear()
async def main():
await dp.start_polling(bot)
if name == "main":
asyncio.run(main())

