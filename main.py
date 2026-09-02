import os
import logging
import asyncio
import sqlite3
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web
import aiohttp

# Настройка логирования
logging.basicConfig(level=logging.INFO)
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Список стран и языков
LANGUAGES = {
    "🇷🇺 Россия / Русский": "ru",
    "🇺🇸 США / Английский": "en",
    "🇩🇪 Германия / Немецкий": "de",
    "🇫🇷 Франция / Французский": "fr",
    "🇪🇸 Испания / Испанский": "es",
    "🇮🇹 Италия / Итальянский": "it",
    "🇹🇷 Турция / Турецкий": "tr",
    "🇵🇱 Польша / Польский": "pl",
    "🇨🇳 Китай / Китайский": "zh",
    "🇦🇪 ОАЭ / Арабский": "ar"
}

class BotStates(StatesGroup):
    choosing_lang = State()
    typing_target_user = State()
    chatting = State()
    entering_admin_pass = State()
    admin_mailing = State()

# --- БАЗА ДАННЫХ (SQLite) ---
def init_db():
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            target_lang TEXT DEFAULT 'en',
            referrer_id INTEGER DEFAULT NULL,
            ref_count INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

init_db()

def register_user(user_id, username, referrer_id=NULL):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        if referrer_id and referrer_id != user_id:
            cursor.execute("INSERT INTO users (user_id, username, referrer_id) VALUES (?, ?, ?)", (user_id, username, referrer_id))
            cursor.execute("UPDATE users SET ref_count = ref_count + 1 WHERE user_id = ?", (referrer_id,))
        else:
            cursor.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
        conn.commit()
    conn.close()

def get_user_lang(user_id):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT target_lang FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else "en"

def set_user_lang(user_id, lang_code):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET target_lang = ? WHERE user_id = ?", (lang_code, user_id))
    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    conn.close()
    return total_users

def get_all_users():
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users

# --- ИИ ПЕРЕВОДЧИК ---
async def translate_text(text: str, target_lang: str) -> str:
    url = f"https://googleapis.com{target_lang}&dt=t&q={text}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    result = await response.json()
                    return "".join([part[0] for part in result[0] if part[0]])
    except Exception as e:
        logging.error(f"Ошибка ИИ перевода: {e}")
    return text

# --- КНОПКИ ---
def get_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Выбрать язык перевода", callback_data="select_language")],
        [InlineKeyboardButton(text="💬 Начать диалог (Ввести ID)", callback_data="connect_user")],
        [InlineKeyboardButton(text="👥 Реферальная система", callback_data="ref_program")],
        [InlineKeyboardButton(text="ℹ️ Как устроен мост?", callback_data="help_info")]
    ])

def get_languages_keyboard():
    buttons = []
    # Делаем удобные кнопки в 2 ряда
    row = []
    for lang_name, lang_code in LANGUAGES.items():
        row.append(InlineKeyboardButton(text=lang_name.split()[0], callback_data=f"setlang_{lang_code}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="⬅️ Главное меню", callback_data="to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- ПРИВЕТСТВИЕ И СТАРТ ---
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    
    # Реферальный код из ссылки
    args = message.text.split()
    referrer_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
    
    register_user(message.from_user.id, message.from_user.username, referrer_id)
    
    bot_info = await bot.get_me()
    ref_link = f"https://t.me{bot_info.username}?start={message.from_user.id}"
    
    welcome_text = (
        "🔥 **Добро пожаловать в будущее коммуникаций!** 🔥\n\n"
        "🤖 **AI Translation Bridge** — это первый в мире умный мост-переводчик, стирающий любые языковые границы в реальном времени!\n\n"
        "💡 **Как это работает:**\n"
        "Вы общаетесь в этом чате на своем языке, а ваш собеседник получает сообщения уже переведенными на его родной язык! Без барьеров, задержек и недопониманий.\n\n"
        f"🆔 **Твой личный ID:** `{message.from_user.id}`\n"
        "Поделись этим ID с иностранным другом, чтобы запустить синхронный перевод чата.\n\n"
        "🚀 Выбери язык и начни общение нового уровня прямо сейчас!"
    )
    await message.answer(welcome_text, reply_markup=get_main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🤖 **Главное меню AI-Переводчика:**", reply_markup=get_main_menu(), parse_mode="Markdown")

# --- РЕФЕРАЛЬНАЯ ПРОГРАММА ---
@dp.callback_query(F.data == "ref_program")
async def show_ref(callback: CallbackQuery):
    bot_info = await bot.get_me()
    ref_link = f"https://t.me{bot_info.username}?start={callback.from_user.id}"
    
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT ref_count FROM users WHERE user_id = ?", (callback.from_user.id,))
    refs = cursor.fetchone()[0]
    conn.close()
    
    text = (
        "👥 **Реферальная программа AI Bridge**\n\n"
        "Помоги нам собрать миллион подписчиков и общайся со всем миром бесплатно!\n\n"
        f"🔗 **Твоя пригласительная ссылка:**\n`{ref_link}`\n\n"
        f"📊 Вы пригласили партнеров: **{refs}**\n\n"
        "Перешли эту ссылку друзьям. Когда они запустят бота, они автоматически станут твоими рефералами!"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="to_menu")]])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

# --- НАСТРОЙКА ЯЗЫКОВ ---
@dp.callback_query(F.data == "select_language")
async def show_languages(callback: CallbackQuery):
    await callback.message.edit_text("🌍 Выберите целевой язык, на который ИИ должен переводить ваши сообщения:", reply_markup=get_languages_keyboard())

@dp.callback_query(F.data.startswith("setlang_"))
async def change_language(callback: CallbackQuery):
    lang_code = callback.data.split("_")[1]
    set_user_lang(callback.from_user.id, lang_code)
    
    lang_name = next((k for k, v in LANGUAGES.items() if v == lang_code), lang_code)
    await callback.answer(f"✅ Установлен язык перевода: {lang_name}", show_alert=True)
    await callback.message.edit_text(f"🤖 Текущий язык перевода изменен на: **{lang_name}**", reply_markup=get_main_menu(), parse_mode="Markdown")

# --- СВЯЗЬ С СОБЕСЕДНИКОМ ---
@dp.callback_query(F.data == "connect_user")
async def ask_target_user(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("⌨️ **Введи Telegram ID** человека, с которым хочешь открыть мост-перевод:")
    await state.set_state(BotStates.typing_target_user)
    await callback.answer()

@dp.message(BotStates.typing_target_user)
async def establish_connection(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ ID должен состоять только из цифр. Попробуй еще раз:")
        return
    
    target_id = int(message.text.strip())
    await state.update_data(partner_id=target_id)
    await state.set_state(BotStates.chatting)
    
    await message.answer(
        f"🤝 **Синхронный перевод активирован!**\n\n"
        f"Пиши сообщения на своем языке — собеседник `{target_id}` получит их уже переведенными.\n"
        f" Чтобы выйти из режима перевода чата, отправь команду `/stop`.",
        parse_mode="Markdown"
    )

@dp.message(Command("stop"))
async def stop_chat(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🛑 Работа моста остановлена. Ты вернулся в меню.", reply_markup=get_main_menu())

# --- ОБРАБОТКА И ПЕРЕВОД СООБЩЕНИЙ ---
@dp.message(BotStates.chatting, F.text)
async def handle_chat_text(message: Message, state: FSMContext):
    if message.text == "/stop":
        await stop_chat(message, state)
        return

    data = await state.get_data()
    partner_id = data.get("partner_id")
    target_lang = get_user_lang(message.from_user.id)
    
    translated_text = await translate_text(message.text, target_lang)
    
    try:
        await bot.send_message(
            chat_id=partner_id,
