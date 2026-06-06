import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiohttp import web

# Получаем токен из настроек Render
BOT_TOKEN = os.environ.get('BOT_TOKEN')

# Инициализируем бота и диспетчер прямо здесь
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Обработчик команды /start
@dp.message(CommandStart())
async def command_start_handler(message: types.Message):
    await message.answer("Привет! Я проснулся и работаю на Render абсолютно бесплатно!")

# Обработчик всех остальных текстовых сообщений (Эхо-бот)
@dp.message()
async def echo_handler(message: types.Message):
    await message.answer(f"Ты написал: {message.text}")

# Веб-сервер для обмана Render (чтобы он видел открытый порт)
async def handle(request):
    return web.Response(text="Bot is alive")

async def main():
    app = web.Application()
    app.router.add_get('/', handle)
    
    # Запускаем веб-сервер на порту Render
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
    await site.start()
    
    print("Бот успешно запущен и работает!")
    
    # Запускаем опрос Telegram
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
