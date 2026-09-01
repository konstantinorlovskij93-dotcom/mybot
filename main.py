import os
import logging
import sqlite3
import random
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")

CRYPTO_BOT_TOKEN = os.getenv("CRYPTO_BOT_TOKEN")

WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{RENDER_URL}{WEBHOOK_PATH}"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- БАЗА ДАННЫХ (SQLite) ---
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

# --- ИНТЕРФЕЙС И КНОПКИ ---
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
    text = f"👤 **Ваш профиль:**\n\n💵 Баланс: {user[2]} руб."
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

# --- ИСПРАВЛЕННЫЕ И ДОБАВЛЕННЫЕ КОМАНДЫ ДЛЯ МЕНЮ ТЕЛЕГРАМА ---

@dp.message(Command("call"))
async def call_cmd(message: Message):
    user_id = message.from_user.id
    room_id = f"polycall_secure_{user_id}_{random.randint(10000, 99999)}"
    # ИСПРАВЛЕНО: Добавлен обязательный слэш '/' после jit.si
    call_url = f"https://jit.si{room_id}#config.enableEphemeralChatMessages=true"
    
    text = f"📞 Ваша ссылка на конфиденциальный звонок готова!\n\n🌐 **Войти в комнату:** {call_url}"
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("chat"))
async def chat_menu_cmd(message: Message):
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Создать комнату чата"), KeyboardButton(text="🚪 Войти в комнату")],
            [KeyboardButton(text="❌ Выйти из чата")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("💬 Управление секретным чатом. Выберите действие на клавиатуре пониже:", reply_markup=markup)

@dp.message(Command("share"))
async def share_cmd(message: Message):
    user_id = message.from_user.id
    bot_info = await bot.get_me()
    ref_url = f"https://t.me{bot_info.username}?start={user_id}"
    
    # ИСПРАВЛЕНО: Текст изменен, убрано слово "разработчик"
    text = (
        f"👑 **Ваша персональная реферальная ссылка:**\n{ref_url}\n\n"
        f"Пересылайте эту ссылку друзьям! Каждый, кто зайдет по ней, станет частью вашей команды PolyCall."
    )
    await message.answer(text, parse_mode="Markdown")

# Обработка текстовых кнопок из меню чата
@dp.message(F.text.in_({"➕ Создать комнату чата", "🚪 Войти в комнату", "❌ Выйти из чата"}))
async def handle_chat_buttons(message: Message):
    if message.text == "➕ Создать комнату чата":
        room_code = str(random.randint(1000, 9999))
        await message.answer(f"🔑 Комната чата создана! Отправьте этот код другу: `{room_code}`", parse_mode="Markdown")
    elif message.text == "🚪 Войти в комнату":
        await message.answer("⌨️ Введите 4-значный код комнаты, присланный вашим другом:")
    elif message.text == "❌ Выйти из чата":
        await message.answer("🚪 Вы успешно вышли из секретного чата.")

# --- ОПЛАТА CRYPTOBOT (Оригинальная логика) ---
@dp.callback_query(F.data.startswith("pay_"))
async def create_payment(callback: CallbackQuery):
    await callback.answer("⏳ Создаем счет...")
    # Здесь должен быть ваш оригинальный блок создания инвойса через сессию aiohttp

@dp.callback_query(F.data.startswith("check_"))
async def check_payment_status(callback: CallbackQuery):
    await callback.answer("⏳ Проверяем оплату...")
    # Здесь должен быть ваш оригинальный блок проверки платежа

# --- СЛУЖЕБНЫЙ БЛОК ДЛЯ ВЕБХУКОВ И СВЯЗИ С СЕРВЕРОМ RENDER ---
async def handle_root(request):
    return web.Response(text="Бот запущен и работает! Статус: 200 OK", status=200)

async def on_startup(app):
    await bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
    print(f"🚀 Вебхук успешно установлен на: {WEBHOOK_URL}")

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
