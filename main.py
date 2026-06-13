import os
import logging
import sqlite3
import aiohttp
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

logging.basicConfig(level=logging.INFO)
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "https://your-local-or-render-url.com") 

# НАСТРОЙКИ CRYPTOBOT
CRYPTO_BOT_TOKEN = os.getenv("CRYPTO_BOT_TOKEN")

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{RENDER_URL.rstrip('/')}{WEBHOOK_PATH}"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- БАЗА ДАННЫХ (SQLite) ---
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0.0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            invoice_id TEXT PRIMARY KEY,
            user_id INTEGER,
            amount REAL,
            status TEXT DEFAULT 'pending'
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_user(user_id, username=""):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, balance FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (user_id, username, balance) VALUES (?, ?, ?)", (user_id, username, 0.0))
        conn.commit()
        user = (user_id, username, 0.0)
    conn.close()
    return user

# --- ИНТЕРФЕЙС / КНОПКИ ---
def get_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Купить номер", callback_query_data="buy_number")],
        [InlineKeyboardButton(text="💰 Профиль / Пополнить", callback_query_data="profile")],
        [InlineKeyboardButton(text="ℹ️ Инструкция", callback_query_data="help")]
    ])

@dp.message(CommandStart())
async def cmd_start(message: Message):
    get_user(message.from_user.id, message.from_user.username)
    await message.answer(
        "👋 Добро пожаловать в **SMSHero Bot**!\n\n"
        "Здесь вы можете купить виртуальные номера для приема СМС-активаций.",
        reply_markup=get_main_menu(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "main_menu")
async def back_to_menu(callback: CallbackQuery):
    await callback.message.edit_text("👋 Главное меню SMSHero:", reply_markup=get_main_menu())

@dp.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    # ИСПРАВЛЕНО: Теперь баланс берется строго как число из базы (индекс 2)
    text = f"👤 **Ваш профиль:**\n├ ID: `{callback.from_user.id}`\n└ Баланс: **{user[2]} руб.**"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💵 Пополнить баланс", callback_query_data="deposit")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_query_data="main_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "deposit")
async def choose_deposit_amount(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ 100 руб. (~1.1 USDT)", callback_query_data="pay_100")],
        [InlineKeyboardButton(text="➕ 300 руб. (~3.3 USDT)", callback_query_data="pay_300")],
        [InlineKeyboardButton(text="➕ 500 руб. (~5.5 USDT)", callback_query_data="pay_500")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_query_data="profile")]
    ])
    await callback.message.edit_text("Выберите сумму в рублях для пополнения баланса (оплата в USDT/крипте):", reply_markup=kb)

@dp.callback_query(F.data.startswith("pay_"))
async def create_payment(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) < 2:
        await callback.answer("⚠️ Ошибка создания платежа.", show_alert=True)
        return
        
    amount_rub = int(parts[1])
    amount_usd = round(amount_rub / 92.0, 2)
    
    headers = {"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}
    payload = {
        "amount": str(amount_usd),
        "asset": "USDT",
        "description": f"Пополнение баланса на {amount_rub} руб."
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post("https://cryptobot.app", json=payload, headers=headers) as resp:
            result = await resp.json()
            
            if result.get("ok"):
                invoice_data = result["result"]
                pay_url = invoice_data["bot_invoice_url"]
                crypto_invoice_id = str(invoice_data["invoice_id"])
                
                conn = sqlite3.connect("database.db")
                cursor = conn.cursor()
                cursor.execute("INSERT INTO invoices (invoice_id, user_id, amount) VALUES (?, ?, ?)", (crypto_invoice_id, callback.from_user.id, amount_rub))
                conn.commit()
                conn.close()
                
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💸 Оплатить в CryptoBot", url=pay_url)],
                    [InlineKeyboardButton(text="✅ Проверить оплату", callback_query_data=f"check_{crypto_invoice_id}")],
                    [InlineKeyboardButton(text="⬅️ Назад", callback_query_data="profile")]
                ])
                
                await callback.message.edit_text(
                    f"💸 **Счет на пополнение успешно создан!**\n\nСумма к зачислению: **{amount_rub} руб.**\nСтоимость: **{amount_usd} USDT**\n\nНажмите кнопку ниже, оплатите счет в открывшемся CryptoBot, а затем вернитесь сюда и нажмите кнопку проверки.",
                    reply_markup=kb,
                    parse_mode="Markdown"
                )
            else:
                await callback.message.answer("⚠️ Не удалось создать счет. Проверьте правильность CRYPTO_BOT_TOKEN в Render.")

@dp.callback_query(F.data.startswith("check_"))
async def check_payment_status(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) < 2:
        await callback.answer("⚠️ Ошибка проверки.", show_alert=True)
        return
        
    crypto_invoice_id = parts[1]
    headers = {"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}
    params = {"invoice_ids": crypto_invoice_id}
    
    async with aiohttp.ClientSession() as session:
        async with session.get("https://cryptobot.app", params=params, headers=headers) as resp:
            try:
                result = await resp.json()
                if result.get("ok") and result["result"]["items"]:
                    crypto_invoice = result["result"]["items"][0]
                    
                    if crypto_invoice["status"] == "paid":
                        conn = sqlite3.connect("database.db")
                        cursor = conn.cursor()
                        cursor.execute("SELECT user_id, amount, status FROM invoices WHERE invoice_id = ?", (crypto_invoice_id,))
                        local_invoice = cursor.fetchone()
                        
                        if local_invoice and local_invoice[2] == 'pending':
                            user_id = local_invoice[0]
                            amount_rub = local_invoice[1]
                            
                            cursor.execute("UPDATE invoices SET status = 'success' WHERE invoice_id = ?", (crypto_invoice_id,))
                            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount_rub, user_id))
                            conn.commit()
                            conn.close()
                            await callback.answer("✅ Баланс успешно пополнен!", show_alert=True)
                        else:
                            await callback.answer("⚠️ Этот счет уже обработан.", show_alert=True)
                    else:
                        await callback.answer("❌ Счет еще не оплачен.", show_alert=True)
            except Exception as e:
                logging.error(f"Ошибка проверки платежа: {e}")
                await callback.answer("⚠️ Произошла ошибка при проверке.", show_alert=True)

# --- БЛОК ДЛЯ СВЯЗИ С UPTIMEROBOT ---
async def handle_root(request):
    return web.Response(text="Бот запущен и работает! Статус: 200 OK", status=200)

async def on_startup(app):
    await bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)

async def init_app():
    app = web.Application()
    app.router.add_get("/", handle_root)
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    app.on_startup.append(on_startup)
    return app

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    web.run_app(init_app(), host="0.0.0.0", port=port)
