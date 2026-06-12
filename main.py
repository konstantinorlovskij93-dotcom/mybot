
    
import os
import logging
import sqlite3
import uuid
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

# НАСТРОЙКИ SMS HERO (ИСПРАВЛЕНО)
SMS_API_KEY = os.getenv("SMS_API_KEY")
SMS_BASE_URL = "https://smshero.ru" 

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

def get_user_balance(user_id):
    user = get_user(user_id)
    return user[2]

def add_balance(user_id, amount):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

# --- ИНТЕРФЕЙС / КНОПКИ ---
def get_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Купить номер", callback_query_data="buy_number")],
        [InlineKeyboardButton(text="💰 Профиль / Пополнить", callback_query_data="profile")],
        [InlineKeyboardButton(text="ℹ️ Инструкция", callback_query_data="help")]
    ])

# --- ХЭНДЛЕРЫ БОТА ---

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
    balance = get_user_balance(callback.from_user.id)
    text = f"👤 **Ваш профиль:**\n├ ID: `{callback.from_user.id}`\n└ Баланс: **{balance} руб.**"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💵 Пополнить баланс", callback_query_data="deposit")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_query_data="main_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "deposit")
async def choose_deposit_amount(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ 100 руб.", callback_query_data="pay_100")],
        [InlineKeyboardButton(text="➕ 300 руб.", callback_query_data="pay_300")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_query_data="profile")]
    ])
    await callback.message.edit_text("Выберите сумму для пополнения (Тестовый режим):", reply_markup=kb)

@dp.callback_query(F.data.startswith("pay_"))
async def create_payment(callback: CallbackQuery):
    amount = int(callback.data.split("_")[1])
    invoice_id = str(uuid.uuid4())[:8]
    
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO invoices (invoice_id, user_id, amount) VALUES (?, ?, ?)", (invoice_id, callback.from_user.id, amount))
    conn.commit()
    conn.close()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить оплату (Тест)", callback_query_data=f"check_{invoice_id}")],
        [InlineKeyboardButton(text="⬅️ Отмена", callback_query_data="profile")]
    ])
    await callback.message.edit_text(f"Создана заявка на {amount} руб.\nДля теста нажмите 'Подтвердить'.", reply_markup=kb)

@dp.callback_query(F.data.startswith("check_"))
async def check_payment(callback: CallbackQuery):
    invoice_id = callback.data.split("_")[1]
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, amount, status FROM invoices WHERE invoice_id = ?", (invoice_id,))
    invoice = cursor.fetchone()
    
    if invoice and invoice[2] == 'pending':
        user_id = invoice[0]
        amount = invoice[1]
        cursor.execute("UPDATE invoices SET status = 'success' WHERE invoice_id = ?", (invoice_id,))
        conn.commit()
        conn.close()
        add_balance(user_id, amount)
        await callback.answer("✅ Баланс успешно пополнен!", show_alert=True)
        await show_profile(callback)
    else:
        conn.close()
        await callback.answer("❌ Оплата не найдена.", show_alert=True)

@dp.callback_query(F.data == "buy_number")
async def choose_service(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✈️ Telegram (35 руб.)", callback_query_data="order_tg_35")],
        [InlineKeyboardButton(text="💬 WhatsApp (25 руб.)", callback_query_data="order_wa_25")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_query_data="main_menu")]
    ])
    await callback.message.edit_text("Выберите сервис для покупки номера:", reply_markup=kb)

@dp.callback_query(F.data.startswith("order_"))
async def buy_sms_number(callback: CallbackQuery):
    data = callback.data.split("_")
    service_code = data[1]  
    price = float(data[2])  
    
    balance = get_user_balance(callback.from_user.id)
    if balance < price:
        await callback.answer("❌ Недостаточно средств на балансе!", show_alert=True)
        return
        
    await callback.answer("Запрашиваем номер у SMS Hero...", show_alert=False)
    
    url = f"{SMS_BASE_URL}?api_key={SMS_API_KEY}&action=getNumber&service={service_code}&country=0"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response_text = await response.text()
                
                if response_text.startswith("ACCESS_NUMBER"):
                    _, activation_id, phone_number = response_text.split(":")
                    
                    conn = sqlite3.connect("database.db")
                    cursor = conn.cursor()
                    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (price, callback.from_user.id))
                    conn.commit()
                    conn.close()
                    
                    text = (
                        f"📱 **Номер успешно получен!**\n\n"
                        f"Сервис: `{service_code.upper()}`\n"
                        f"Номер: `{phone_number}`\n"
                        f"ID Активации: `{activation_id}`\n\n"
                        f"Вставьте номер в приложение и нажмите кнопку ниже, чтобы проверить СМС-код."
                    )
                    
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔄 Получить СМС / Обновить", callback_query_data=f"sms_{activation_id}_{price}")],
                        [InlineKeyboardButton(text="❌ Отменить номер (Возврат)", callback_query_data=f"cancel_{activation_id}_{price}")]
                    ])
                    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
                else:
                    await callback.message.answer(f"⚠️ Ошибка сервиса SMS Hero: {response_text}. Возможно, нет доступных номеров.")
    except Exception as e:
        logging.error(f"Ошибка API: {e}")
        await callback.message.answer("💥 Произошла ошибка при связи с СМС-сервисом.")

@dp.callback_query(F.data.startswith("sms_"))
async def check_sms_status(callback: CallbackQuery):
    data = callback.data.split("_")
    activation_id = data[1]
    
    url = f"{SMS_BASE_URL}?api_key={SMS_API_KEY}&action=getStatus&id={activation_id}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            status_text = await response.text()
            
            if status_text.startswith("STATUS_OK"):
                sms_code = status_text.split(":")[1]
                await callback.message.edit_text(
                    f"🎉 **СМС Код получен!**\n\nКод: `{sms_code}`\n\nСпасибо за покупку!",
                    reply_markup=get_main_menu(),
                    parse_mode="Markdown"
                )
            elif status_text == "STATUS_WAIT_CODE":
                await callback.answer("⏳ СМС еще не пришло. Подождите немного и обновите еще раз.", show_alert=True)
            else:
                await callback.message.edit_text(f"Статус активации: {status_text}", reply_markup=get_main_menu())

@dp.callback_query(F.data.startswith("cancel_"))
async def cancel_sms_activation(callback: CallbackQuery):
    data = callback.data.split("_")
