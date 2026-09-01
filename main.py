import os
import logging
import sqlite3
import random
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
import aiohttp

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
CRYPTO_BOT_TOKEN = os.getenv("CRYPTO_BOT_TOKEN")

WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{RENDER_URL}{WEBHOOK_PATH}"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0.0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            invoice_id TEXT PRIMARY KEY,
            user_id TEXT,
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
    cursor.execute("SELECT user_id, username, balance FROM users WHERE user_id = ?", (str(user_id),))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (user_id, username, balance) VALUES (?, ?, 0.0)", (str(user_id), username))
        conn.commit()
        user = (str(user_id), username, 0.0)
    conn.close()
    return user

# --- МЕНЮ И КНОПКИ ---
def get_main_menu():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Купить номер", callback_data="buy_number")],
        [InlineKeyboardButton(text="💰 Профиль / Пополнить", callback_data="profile")],
        [InlineKeyboardButton(text="📖 Инструкция", callback_data="instructions")]
    ])
    return kb

@dp.message(CommandStart())
async def cmd_start(message: Message):
    get_user(message.from_user.id, message.from_user.username)
    await message.answer(
        f"👋 Добро пожаловать в **SMSHero Bot**!\n\n"
        f"Здесь вы можете купить виртуальные номера для приема СМС-активаций.",
        reply_markup=get_main_menu(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "main_menu")
async def back_to_menu(callback: CallbackQuery):
    await callback.message.edit_text("📱 Главное меню SMSHero:", reply_markup=get_main_menu())

@dp.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    balance_val = user[2]
    text = f"👤 **Ваш профиль:**\n\n💵 Баланс: {balance_val} руб."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="deposit")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "deposit")
async def choose_deposit_amount(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💵 100 руб. (~1.1 USDT)", callback_data="pay_100")],
        [InlineKeyboardButton(text="💵 300 руб. (~3.3 USDT)", callback_data="pay_300")],
        [InlineKeyboardButton(text="💵 500 руб. (~5.5 USDT)", callback_data="pay_500")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="profile")]
    ])
    await callback.message.edit_text("Выберите сумму в рублях для пополнения через CryptoBot:", reply_markup=kb)

# --- НОВЫЕ КОМАНДЫ ДЛЯ ЗВОНКОВ И ЧАТА ---

@dp.message(Command("call"))
async def call_cmd(message: Message):
    user_id = message.from_user.id
    room_id = f"polycall_secure_{user_id}_{random.randint(10000, 99999)}"
    call_url = f"https://jit.si{room_id}#config.enableEphemeralChatMessages=true"
    await message.answer(f"📞 Ваша ссылка на конфиденциальный звонок готова!\n\n🌐 **Войти в комнату:** {call_url}", parse_mode="Markdown")

@dp.message(Command("chat"))
async def chat_menu_cmd(message: Message):
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Создать комнату чата"), KeyboardButton(text="🚪 Войти в комнату")],
            [KeyboardButton(text="❌ Выйти из чата")]
        ],
        resize_keyboard=True, one_time_keyboard=True
    )
    await message.answer("💬 Управление секретным чатом. Выберите действие на кнопках ниже:", reply_markup=markup)

@dp.message(Command("share"))
async def share_cmd(message: Message):
    user_id = message.from_user.id
    bot_info = await bot.get_me()
    ref_url = f"https://t.me{bot_info.username}?start={user_id}"
    await message.answer(f"👑 **Ваша персональная реферальная ссылка:**\n{ref_url}\n\nПересылайте ссылку друзьям! Она станет частью вашей команды PolyCall.", parse_mode="Markdown")

@dp.message(F.text.in_({"➕ Создать комнату чата", "🚪 Войти в комнату", "❌ Выйти из чата"}))
async def handle_chat_buttons(message: Message):
    if message.text == "➕ Создать комнату чата":
        room_code = str(random.randint(1000, 9999))
        await message.answer(f"🔑 Комната чата создана! Код: `{room_code}`", parse_mode="Markdown")
    elif message.text == "🚪 Войти в комнату":
        await message.answer("⌨️ Введите 4-значный код комнаты:")
    elif message.text == "❌ Выйти из чата":
        await message.answer("🚪 Вы успешно вышли из секретного чата.")

# --- СИСТЕМА ОПЛАТЫ CRYPTOBOT ---

@dp.callback_query(F.data.startswith("pay_"))
async def create_payment(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) < 2:
        await callback.answer("⚠️ Ошибка создания платежа.", show_alert=True)
        return
    amount_rub = int(parts[1])
    amount_usd = round(amount_rub / 92.0, 2)
    
    headers = {"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}
    payload = {"asset": "USDT", "amount": str(amount_usd), "description": f"Пополнение баланса на {amount_rub} руб."}
    
    async with aiohttp.ClientSession() as session:
        async with session.post("https://cryptobot.app", json=payload, headers=headers) as resp:
            result = await resp.json()
            if result.get("ok"):
                invoice_data = result["result"]
                pay_url = invoice_data["bot_invoice_url"]
                crypto_invoice_id = str(invoice_data["invoice_id"])
                
                conn = sqlite3.connect("database.db")
                cursor = conn.cursor()
                cursor.execute("INSERT INTO invoices (invoice_id, user_id, amount) VALUES (?, ?, ?)", (crypto_invoice_id, str(callback.from_user.id), float(amount_rub)))
                conn.commit()
                conn.close()
                
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💳 Оплатить в CryptoBot", url=pay_url)],
                    [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_{crypto_invoice_id}")],
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="profile")]
                ])
                await callback.message.edit_text(f"💵 Счет на пополнение успешно создан!\n\nСумма: {amount_rub} руб. (~{amount_usd} USDT)", reply_markup=kb, parse_mode="Markdown")
            else:
                await callback.answer("⚠️ Не удалось создать счет.")

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
                            user_id = local_invoice[0]
                            amount_rub = local_invoice[1]
                            cursor.execute("UPDATE invoices SET status = 'paid' WHERE invoice_id = ?", (crypto_invoice_id,))
                            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount_rub, user_id))
                            conn.commit()
                            conn.close()
                            await callback.answer("✅ Баланс успешно пополнен!", show_alert=True)
                        else:
                            conn.close()
                            await callback.answer("⚠️ Этот счет уже обработан.")
                    else:
                        await callback.answer("❌ Счет еще не оплачен.", show_alert=True)
            except Exception as e:
                logging.error(f"Ошибка проверки платежа: {e}")
                await callback.answer("⚠️ Произошла ошибка при проверке.")

# --- СЛУЖЕБНЫЙ БЛОК ВЕБХУКОВ RENDER ---
async def handle_root(request):
    return web.Response(text="Бот запущен и работает! Статус: 200 OK", status=200)

