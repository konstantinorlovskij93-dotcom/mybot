import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web
# Подключаем бесплатную библиотеку ИИ от Google
import google.generativeai as genai

BOT_TOKEN = os.environ.get('BOT_TOKEN')
# Сервер сам возьмет этот бесплатный ключ из настроек Render, которые мы только что сохранили
GEMINI_KEY = os.environ.get('GEMINI_KEY') 

# Настраиваем ИИ
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-pro')

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def command_start_handler(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="📱 Наш сайт", url="https://onrender.com"))
    builder.add(types.InlineKeyboardButton(text="🔥 Заработать / Помочь", callback_data="btn_click"))
    builder.adjust(1)
    await message.answer(
        "Привет! Я твой бот с искусственным интеллектом. Напиши мне любой вопрос, и я отвечу тебе как человек!",
        reply_markup=builder.as_markup()
    )

# Обработчик любых текстовых сообщений — отправляем их в ИИ
@dp.message(F.text)
async def ai_message_handler(message: types.Message):
    # Показываем пользователю статус "печатает...", пока ИИ думает
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    try:
        # Генерируем ответ с помощью бесплатного ИИ от Google
        response = model.generate_content(message.text)
        await message.answer(response.text)
    except Exception as e:
        await message.answer("Извини, я задумался. Попробуй еще раз чуть позже!")

# Код веб-сервера для Render
async def handle(request):
    return web.Response(text="Bot is alive")

async def main():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
    await site.start()
    print("Бот успешно запущен и работает с ИИ!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
