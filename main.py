import os
import logging
import sqlite3
import uuid
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
import aiohttp

# Настройка логирования
logging.basicConfig(level=logging.INFO)
load_dotenv()

# Инициализация токенов из окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
SMS_API_KEY = os.getenv("SMS_API_KEY")
SMS_BASE_URL = "https://smshero.ru"
CRYPTO_BOT_TOKEN = os.getenv("CRYPTO_BOT_TOKEN")

# Инициализация бота и диспетчера
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
        cursor.execute("INSERT INTO users (user_id, username, balance) VALUES (?, ?, 0.0)", (user_id, username))
        conn.commit()
        user = (user_id, username, 0.0)
    conn.close()
    return user

def add_balance(user_id, amount):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

# --- ИНТЕРФЕЙС / КНОПКИ ---
def get_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Купить номер", callback_data="buy_number")],
        [InlineKeyboardButton(text="👤 Профиль / Пополнить", callback_data="profile")],
        [InlineKeyboardButton(text="ℹ️ Инструкция", callback_data="help")]
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
    await callback.message.edit_text("🔝 Главное меню SMSHero:", reply_markup=get_main_menu())

@dp.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    text = f"👤 **Ваш профиль:**\n\n🆔 ID: `{callback.from_user.id}`\n💰 Баланс: **{user[2]} руб.**"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="deposit")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "deposit")
async def choose_deposit_amount(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔹 100 руб. (~1.1 USDT)", callback_data="pay_100")],
        [InlineKeyboardButton(text="🔹 300 руб. (~3.3 USDT)", callback_data="pay_300")],
        [InlineKeyboardButton(text="🔹 500 руб. (~5.5 USDT)", callback_data="pay_500")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="profile")]
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
                pay_url = invoice_data["pay_url"]
                crypto_invoice_id = str(invoice_data["invoice_id"])
                
                conn = sqlite3.connect("database.db")
                cursor = conn.cursor()
                cursor.execute("INSERT INTO invoices (invoice_id, user_id, amount) VALUES (?, ?, ?)", (crypto_invoice_id, callback.from_user.id, amount_rub))
                conn.commit()
                conn.close()
                
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💸 Оплатить в CryptoBot", url=pay_url)],
                    [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_{crypto_invoice_id}")],
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="profile")]
                ])
                
                await callback.message.edit_text(
                    f"🎰 **Счет на пополнение успешно создан!**\n\nСумма к зачислению: **{amount_rub} руб.** (~{amount_usd} USDT)",
                    reply_markup=kb,
                    parse_mode="Markdown"
                )
            else:
                await callback.answer("⚠️ Не удалось создать счет. Проверьте CRYPTO_BOT_TOKEN.", show_alert=True)

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
                        
                        if local_invoice and local_invoice[2] == "pending":
                            user_id, amount_rub, _ = local_invoice
                            cursor.execute("UPDATE invoices SET status = 'paid' WHERE invoice_id = ?", (crypto_invoice_id,))
                            conn.commit()
                            conn.close()
                            
                            add_balance(user_id, amount_rub)
                            await callback.answer("✅ Оплата получена! Баланс пополнен.", show_alert=True)
                            await show_profile(callback)
                        else:
                            await callback.answer("ℹ️ Этот счет уже был обработан.", show_alert=True)
                    else:
                        await callback.answer("⏳ Счет еще не оплачен.", show_alert=True)
                else:
                    await callback.answer("❌ Счет не найден в CryptoBot.", show_alert=True)
            except Exception as e:
                logging.error(f"Ошибка проверки платежа: {e}")
                await callback.answer("⚠️ Произошла ошибка при проверке. Попробуйте позже.")

# --- ЗАПУСК БОТА (Long Polling) ---
async def main():
    # Удаляем вебхук, если он был установлен ранее, чтобы включить Long Polling
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Бот запущен в режиме Long Polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
