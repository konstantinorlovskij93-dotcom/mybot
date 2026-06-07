import os
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiohttp import web

# Состояния для ИИ-чата, чтобы он не перехватывал обычные сообщения
class ChatStates(StatesGroup):
    ai_mode = State()

# Попытка импорта нового SDK Gemini
try: from google import genai

except ImportError:
    genai = None

# Безопасное получение токенов. Первым аргументом идет имя переменной, вторым - значение по умолчанию
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
GEMINI_KEY = os.environ.get("GEMINI_KEY", "")
HEROSMS_KEY = os.environ.get("HEROSMS_KEY", "")
# Ссылки в кнопках Обязаны начинаться с https://
CRYPTO_BOT_URL = os.environ.get("CRYPTO_BOT_URL", "https://@online_sms_receive_bot ")

# Инициализация ИИ клиента
if genai and GEMINI_KEY:
    try:
        ai_client = genai.Client(api_key=GEMINI_KEY)
    except Exception:
        ai_client = None
else:
    ai_client = None

# Проверка наличия токена Telegram перед запуском
if not BOT_TOKEN:
    raise ValueError("ОШИБКА: Переменная BOT_TOKEN не заведена в файле .env или настройках хостинга!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


def get_main_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="📱 Купить номер для СМС", callback_data="buy_number"))
    builder.add(types.InlineKeyboardButton(text="💰 Баланс и Пополнение", callback_data="balance"))
    builder.add(types.InlineKeyboardButton(text="🤖 Поговорить с ИИ", callback_data="chat_ai"))
    builder.adjust(1)
    return builder.as_markup()

@dp.message(CommandStart())
async def command_start_handler(message: types.Message, state: FSMContext):
    await state.clear() # Сбрасываем режим ИИ при старте
    await message.answer(
        "🔥 Добро пожаловать в автоматический магазин СМС-номеров!\n\n"
        "Здесь вы можете купить виртуальные номера разных стран для активации Telegram, WhatsApp и других сервисов.\n\n"
        "Выберите нужное действие в меню ниже:",
        reply_markup=get_main_keyboard()
    )


@dp.callback_query(F.data == "buy_number")
async def process_buy_number(callback: types.CallbackQuery):
    await callback.answer()
    
    if not HEROSMS_KEY:
        await callback.message.answer("⚠️ Ошибка: Ключ API Hero-SMS не настроен в системе.")
        return

    clean_key = HEROSMS_KEY.replace(" ", "")
    # Исправлено: добавлен вопросительный знак или правильный параметр для API, подставь нужный по документации hero-sms
    url = f"https://hero-sms.com{clean_key}&action=getTopCountriesByService"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    builder = InlineKeyboardBuilder()
                    builder.add(types.InlineKeyboardButton(text="🇷🇺 Россия", callback_data="country_ru"))
                    builder.add(types.InlineKeyboardButton(text="🇰🇿 Казахстан", callback_data="country_kz"))
                    builder.add(types.InlineKeyboardButton(text="🇺🇸 США", callback_data="country_us"))
                    builder.add(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu"))
                    builder.adjust(2)
                    
                    await callback.message.edit_text(
                        "🌍 Выберите страну для покупки номера:",
                        reply_markup=builder.as_markup()
                    )
                else:
                    await callback.message.answer("⚠️ Ошибка подключения к базе номеров. Попробуйте позже.")
        except Exception:
            await callback.message.answer("⚠️ Сервис номеров временно недоступен.")


@dp.callback_query(F.data == "main_menu")
async def process_main_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(
        "Выберите нужное действие в меню ниже:",
        reply_markup=get_main_keyboard()
    )


@dp.callback_query(F.data == "balance")
async def process_balance(callback: types.CallbackQuery):
    await callback.answer()
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="💳 Пополнить (Crypto / Карта)", callback_data="deposit"))
    builder.add(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu"))
    builder.adjust(1)
    
    await callback.message.edit_text(
        "💰 Ваш баланс: 0.00 руб.\n\n"
        "Чтобы покупать номера, пополните баланс в боте.",
        reply_markup=builder.as_markup()
    )


@dp.callback_query(F.data == "deposit")
async def process_deposit(callback: types.CallbackQuery):
    await callback.answer()
    
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="📱 Подтвердить номер телефона", request_contact=True))
    
    await callback.message.answer(
        "🔒 Для проведения оплаты вам необходимо подтвердить свой аккаунт.\n\n"
        "Нажмите кнопку «📱 Подтвердить номер телефона» на вашей клавиатуре внизу.",
        reply_markup=builder.as_markup(resize_keyboard=True, one_time_keyboard=True)
    )


@dp.message(F.contact)
async def handle_contact_and_pay(message: types.Message):
    user_phone = message.contact.phone_number
    
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="💳 Перейти к оплате в CryptoBot", url=CRYPTO_BOT_URL))
    
    await message.answer(
         f"✅ Ваш номер телефона ({user_phone}) успешно проверен.\n\n"
         f"Теперь нажмите на кнопку ниже, чтобы перейти к оплате и пополнению баланса магазина:",
         reply_markup=builder.as_markup()
    )


@dp.callback_query(F.data == "chat_ai")
async def process_chat_ai(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ChatStates.ai_mode) # Включаем режим ожидания вопросов для ИИ
    
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="⬅️ Выйти из ИИ", callback_data="main_menu"))
    
    await callback.message.answer(
        "🤖 Режим ИИ включен! Просто напишите мне любой текстовый вопрос, и я отвечу.\n"
        "Для выхода нажмите кнопку ниже или введите /start.",
        reply_markup=builder.as_markup()
    )


# Этот хэндлер сработает только тогда, когда включен ai_mode
@dp.message(ChatStates.ai_mode, F.text)
async def ai_message_handler(message: types.Message):
    if not ai_client:
        await message.answer("ИИ временно недоступен или не настроен (проверьте GEMINI_KEY).")
        return
        
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=message.text,
        )
        await message.answer(response.text)
    except Exception:
        await message.answer("Я задумался. Задайте вопрос еще раз!")


# Заглушка для обычных сообщений вне контекста
@dp.message(F.text)
async def default_handler(message: types.Message):
    await message.answer("Пожалуйста, используйте меню для навигации.", reply_markup=get_main_keyboard())


async def handle(request):
    return web.Response(text="Bot is alive")

async def main():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
    await site.start()
    
    print("Бот успешно запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())

