import asyncio, aiohttp, os
from telebot.async_telebot import AsyncTeleBot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from threading import Thread

# Render port xatosini to'g'rilash uchun kichik veb-server
app = Flask('')
@app.route('/')
def home(): return "Bot faol!"

def run_web():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))

BOT_TOKEN = os.environ.get("BOT_TOKEN")
API_KEY = os.environ.get("TOPSMM_API_KEY")
API_URL = "https://topsmm.uz"

bot = AsyncTeleBot(BOT_TOKEN)
user_sessions, services_cache = {}, []

def main_menu():
    m = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    m.add(KeyboardButton("🚀 Yangi Buyurtma"), KeyboardButton("💰 Balans"))
    m.add(KeyboardButton("📊 Holatni Tekshirish"), KeyboardButton("❌ Bekor qilish"))
    return m

async def call_api(payload):
    payload['key'] = API_KEY
    async with aiohttp.ClientSession() as s:
        try:
            async with s.post(API_URL, data=payload) as r:
                return await r.json() if r.status == 200 else None
        except: return None

@bot.message_handler(commands=['start'])
async def start(m):
    global services_cache
    await bot.reply_to(m, "👋 *TopSMM Botiga Xush Kelibsiz!*\nKategoriyani ko'rish uchun tugmani bosing:", parse_mode="Markdown", reply_markup=main_menu())
    res = await call_api({'action': 'services'})
    if res: services_cache = res

@bot.message_handler(func=lambda m: m.text == "💰 Balans")
async def balance(m):
    res = await call_api({'action': 'balance'})
    txt = f"💳 Balans: `{res['balance']}` {res.get('currency', 'UZS')}" if res and 'balance' in res else "❌ API xato."
    await bot.reply_to(m, txt, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "📊 Holatni Tekshirish")
async def status_start(m):
    user_sessions[m.chat.id] = {'act': 'status'}
    await bot.reply_to(m, "🔢 *Buyurtma ID* raqamini kiriting:", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🚀 Yangi Buyurtma")
async def order_start(m):
    global services_cache
    if not services_cache:
        res = await call_api({'action': 'services'})
        if res: services_cache = res
    if not services_cache:
        await bot.reply_to(m, "⚠️ Xizmatlarni yuklab bo'lmadi. Qayta start bosing.")
        return
    cats = sorted(list(set([i['category'] for i in services_cache if 'category' in i])))[:12]
    markup = InlineKeyboardMarkup(row_width=1)
    for c in cats: markup.add(InlineKeyboardButton(text=c[:40], callback_data=f"c_{c[:25]}"))
    await bot.reply_to(m, "📂 Yo'nalishni tanlang:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("c_"))
async def handle_cat(c):
    sel, markup, count = c.data[2:], InlineKeyboardMarkup(row_width=1), 0
    for i in services_cache:
        if i.get('category', '').startswith(sel):
            markup.add(InlineKeyboardButton(text=f"ID: {i['service']} | {i['rate']} UZS", callback_data=f"s_{i['service']}"))
            count += 1
            if count >= 10: break
    await bot.edit_message_text("💎 Xizmatni tanlang:", c.message.chat.id, c.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("s_"))
async def handle_srv(c):
    user_sessions[c.message.chat.id] = {'act': 'order', 'srv': c.data[2:], 'step': 'lnk'}
    await bot.delete_message(c.message.chat.id, c.message.message_id)
    await bot.send_message(c.message.chat.id, "🔗 Buyurtma obyekti *Havolasini (Link)* yuboring:", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.chat.id in user_sessions)
async def inputs(m):
    cid = m.chat.id
    sess = user_sessions[cid]
    if m.text == "❌ Bekor qilish":
        user_sessions.pop(cid, None)
        await bot.reply_to(m, "🔄 Bekor qilindi.", reply_markup=main_menu())
        return
    if sess['act'] == 'status':
        if not m.text.isdigit(): return
        res = await call_api({'action': 'status', 'order': m.text})
        if res and 'status' in res:
            await bot.reply_to(m, f"📊 Holati: *{res['status']}*\n💰 Narxi: {res.get('charge','0')} UZS\n🔄 Qoldi: {res.get('remains','0')}", parse_mode="Markdown", reply_markup=main_menu())
            user_sessions.pop(cid, None)
        else: await bot.reply_to(m, "❌ ID topilmadi.")
    elif sess['act'] == 'order':
        if sess['step'] == 'lnk':
            sess['lnk'], sess['step'] = m.text, 'qty'
            await bot.reply_to(m, "🔢 Kerakli *Miqdorni* kiriting (Faqat raqam):", parse_mode="Markdown")
        elif sess['step'] == 'qty':
            if not m.text.isdigit(): return
            await bot.reply_to(m, "⏳ Panelga yuborilmoqda...")
            res = await call_api({'action': 'add', 'service': sess['srv'], 'link': sess['lnk'], 'quantity': m.text})
            if res and 'order' in res:
                await bot.send_message(cid, f"🎉 *Muvaffaqiyatli!*\n🆔 Buyurtma ID: `{res['order']}`", parse_mode="Markdown", reply_markup=main_menu())
            else:
                await bot.send_message(cid, f"❌ Rad etildi: {res.get('error', 'Xato miqdor yoki mablag\' yetarsiz')}", reply_markup=main_menu())
            user_sessions.pop(cid, None)

if __name__ == '__main__':
    Thread(target=run_web).start()
    asyncio.run(bot.infinity_polling())
