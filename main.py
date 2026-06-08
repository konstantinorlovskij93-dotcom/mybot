import os
import sys
import asyncio
import logging
import aiohttp
from aiogram import Bot, Dispatcher, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiohttp import web

# Пробуем импортировать Gemini
try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

# ==================== ЗАГРУЗКА НАСТРОЕК С RENDER ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
GEMINI_KEY = os.environ.get("GEMINI_KEY", "")
HEROSMS_KEY = os.environ.get("HEROSMS_KEY", "")

# Список ID администраторов бота
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip().isdigit()]

# Ссылки на оплату Crypto Bot
CRYPTO_BOT_URL = os.environ.get("CRYPTO_BOT_URL", "https://t.me")

# Инициализация ИИ клиента
ai_client = None
if HAS_GEMINI and GEMINI_KEY:
    try:
        genai.configure(api_key=GEMINI_KEY)
        ai_client = genai.GenerativeModel("gemini-2.5-flash")
    except Exception:
        ai_client = None

# Проверка наличия токена Telegram перед запуском
if not BOT_TOKEN:
    logging.error("КРИТИЧЕСКАЯ ОШИБКА: Переменная BOT_TOKEN не найдена на Render!")
    sys.exit(1)

# Включаем логирование
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Состояния для ИИ-чата
class ChatStates(StatesGroup):
    ai_node = State()

# ==================== КЛАВИАТУРЫ ====================
def get_main_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="📱 Купить номер для СМС", callback_data="buy_number"))
    builder.add(types.InlineKeyboardButton(text="💳 Баланс и Пополнение", callback_data="balance"))
    builder.add(types.InlineKeyboardButton(text="💬 Поговорить с ИИ", callback_data="chat_ai"))
    builder.adjust(1)
    return builder.as_markup()

# ==================== ХЭНДЛЕРЫ КОМАНД ====================
@dp.message(CommandStart() if 'CommandStart' in locals() else F.text == "/start")
@dp.message(F.text == "/start")
async def command_start_handler(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        text="👋 Добро пожаловать в автоматический магазин СМС-номеров!\n"
             "Здесь вы можете купить виртуальные номера разных стран для активации.\n"
             "Выберите нужное действие в меню ниже 👇",
        reply_markup=get_main_keyboard()
    )

# ==================== ХЭНДЛЕРЫ КНОПОК И МЕНЮ ====================
@dp.callback_query(F.data == "buy_number")
async def process_buy_number(callback: types.CallbackQuery):
    await callback.answer()
    
    if not HEROSMS_KEY:
        await callback.message.answer(text="⚠️ Ошибка: Ключ API Hero-SMS не настроен на сервере.")
        return

    clean_key = HEROSMS_KEY.replace(" ", "")
    url = f"https://hero-sms.com{clean_key}&action=getTopCountriesByServices"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    builder = InlineKeyboardBuilder()
                    # Кнопки выбора популярных стран
                    builder.add(types.InlineKeyboardButton(text="🇷🇺 Россия", callback_data="country_ru"))
                    builder.add(types.InlineKeyboardButton(text="🇰🇿 Казахстан", callback_data="country_kz"))
                    builder.add(types.InlineKeyboardButton(text="🇺🇸 США", callback_data="country_us"))
                    builder.add(types.InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"))
                    builder.adjust(2)
                    
                    await callback.message.edit_text(
                        text="🌍 Выберите страну для покупки номера:",
                        reply_markup=builder.as_markup()
                    )
                else:
                    await callback.message.answer(text="⚠️ Ошибка подключения к СМС-сервису. Код ответа не 200.")
    except Exception:
        await callback.message.answer(text="⚠️ Сервис номеров временно недоступен. Попробуйте позже.")

@dp.callback_query(F.data == "main_menu")
async def process_main_menu(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        text="Выберите нужное действие в меню ниже:",
        reply_markup=get_main_keyboard()
    )

@dp.callback_query(F.data == "balance")
async def process_balance(callback: types.CallbackQuery):
    await callback.answer()
    
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="💵 Пополнить (Crypto / Карта)", callback_data="deposit"))
    builder.add(types.InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"))
    builder.adjust(1)
    
    user_balance = "0.00 руб." # Здесь вы сможете подключить вашу базу данных
    
    await callback.message.edit_text(
        text=f"💳 Ваш баланс: {user_balance}\n\nЧтобы покупать номера, пополните баланс в боте.",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "deposit")
async def process_deposit(callback: types.CallbackQuery):
    await callback.answer()
    
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="📱 Подтвердить номер телефона", request_contact=True))
    
    await callback.message.answer(
        text="Для проведения оплаты вам необходимо подтвердить свой аккаунт.\n"
             "Нажмите кнопку «Подтвердить номер телефона» на вашей клавиатуре ниже.",
        reply_markup=builder.as_markup(resize_keyboard=True, one_time_keyboard=True)
    )

@dp.message(F.contact)
async def handle_contact_and_pay(message: types.Message):
    user_phone = message.contact.phone_number
    
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="💳 Перейти к оплате в CryptoBot", url=CRYPTO_BOT_URL))
    builder.add(types.InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu"))
    builder.adjust(1)
    
    await message.answer(
        text=f"✅ Ваш номер телефона ({user_phone}) успешно проверен.\n\n"
             f"Теперь нажмите на кнопку ниже, чтобы перейти к оплате и пополнить баланс.",
        reply_markup=builder.as_markup()
    )

# ==================== ЧАТ С НЕЙРОСЕТЬЮ (ИИ) ====================
@dp.callback_query(F.data == "chat_ai")
async def process_chat_ai_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ChatStates.ai_node)
    
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="❌ Выйти из ИИ", callback_data="main_menu"))
    builder.adjust(1)
    
    await callback.message.edit_text(
        text="🤖 Режим ИИ включен! Просто напишите мне любой текстовый вопрос.\n"
             "Для выхода нажмите кнопку ниже или введите /start.",
        reply_markup=builder.as_markup()
    )

@dp.message(ChatStates.ai_node, F.text)
async def ai_message_handler(message: types.Message):
    if not ai_client:
        await message.answer("🤖 ИИ временно недоступен или не настроен разработчиком.")
        return
        
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    try:
        response = ai_client.generate_content(message.text)
        await message.answer(response.text)
    except Exception:
        await message.answer("⚠️ Я задумался. Задайте вопрос еще раз!")

@dp.message(F.text)
async def default_handler(message: types.Message):
    await message.answer("Пожалуйста, используйте меню для навигации.", reply_markup=get_main_keyboard())

# ==================== РАБОТА С СЕРВЕРОМ AIOHTTP ДЛЯ RENDER ====================
async def handle(request):
    return web.Response(text="Bot is alive")

async def main():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    
    print("Бот успешно запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
