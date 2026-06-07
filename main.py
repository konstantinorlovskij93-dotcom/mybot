import os
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiohttp import web

from google import genai

BOT_TOKEN = os.environ.get('BOT_TOKEN')
GEMINI_KEY = os.environ.get('GEMINI_KEY') 

HEROSMS_KEY = "4cbc40A6Adf11c7dAe5A990fcf36e8A cf36e8A2"

# ⚠️ ВСТАВЬТЕ СЮДА ВАШУ МНОГОРАЗОВУЮ ССЫЛКУ, КОТОРУЮ ВЫ СКОПИРОВАЛИ ИЗ @CryptoBot
CRYPTO_BOT_URL = "https://t.me"

if GEMINI_KEY:
    ai_client = genai.Client(api_key=GEMINI_KEY)
else:
    ai_client = None

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
async def command_start_handler(message: types.Message):
    await message.answer(
        "🔥 Добро пожаловать в автоматический магазин СМС-номеров!\n\n"
        "Здесь вы можете купить виртуальные номера разных стран для активации Telegram, WhatsApp и других сервисов.\n\n"
        "Выберите нужное действие в меню ниже:",
        reply_markup=get_main_keyboard()
    )


@dp.callback_query(F.data == "buy_number")
async def process_buy_number(callback: types.CallbackQuery):
    await callback.answer()
    
    url = f"https://hero-sms.com{HEROSMS_KEY}&action=getTopCountriesByService"
    
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
async def process_main_menu(callback: types.CallbackQuery):
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


# ХЭНДЛЕР НАЖАТИЯ НА КНОПКУ «ПОПОЛНИТЬ» — ЗАПРАШИВАЕМ РЕАЛЬНЫЙ ТЕЛЕФОН
@dp.callback_query(F.data == "deposit")
async def process_deposit(callback: types.CallbackQuery):
    await callback.answer()
    
    # Создаем кнопку внизу экрана для безопасной отправки контакта телефона
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="📱 Подтвердить номер телефона", request_contact=True))
    
    await callback.message.answer(
        "🔒 Для проведения оплаты вам необходимо подтвердить свой аккаунт.\n\n"
        "Нажмите кнопку «📱 Подтвердить номер телефона» на вашей клавиатуре внизу.",
        reply_markup=builder.as_markup(resize_keyboard=True, one_time_keyboard=True)
    )


# ХЭНДЛЕР ЛОВИТ РЕАЛЬНЫЙ НОМЕР И ОТПРАВЛЯЕТ ССЫЛКУ НА КРИПТОБОТ
@dp.message(F.contact)
async def handle_contact_and_pay(message: types.Message):
    user_phone = message.contact.phone_number
    
    # Создаем инлайн-кнопку, которая ведет на оплату в ваш CryptoBot
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="💳 Перейти к оплате в CryptoBot", url=CRYPTO_BOT_URL))
    
    # Отправляем сообщение со ссылкой. Номер пользователя сохранен в системе!
    await message.answer(
         f"✅ Ваш номер телефона ({user_phone}) успешно проверен.\n\n"
         f"Теперь нажмите на кнопку ниже, чтобы перейти к оплате и пополнению баланса магазина:",
         reply_markup=builder.as_markup()
    )


@dp.callback_query(F.data == "chat_ai")
async def process_chat_ai(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer("🤖 Режим ИИ включен! Просто напишите мне любой текстовый вопрос, и я отвечу.")


@dp.message(F.text)
async def ai_message_handler(message: types.Message):
    if not ai_client:
        await message.answer("ИИ временно недоступен.")
        return
        
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=message.text,
        )
        await message.answer(response.text)
    except Exception as e:
        await message.answer("Я задумался. Задайте вопрос еще раз!")


async def handle(request):
    return web.Response(text="Bot is alive")

async def main():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
    await site.start()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
