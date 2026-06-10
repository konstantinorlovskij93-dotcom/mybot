import os
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

# Настройка логов
logging.basicConfig(level=logging.INFO)
load_dotenv()

# Загрузка переменных
BOT_TOKEN = os.getenv("BOT_TOKEN")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL") 

if not BOT_TOKEN or not RENDER_URL:
    raise ValueError("Критические переменные BOT_TOKEN или RENDER_EXTERNAL_URL не найдены в .env!")

WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{RENDER_URL.rstrip('/')}{WEBHOOK_PATH}"

# Инициализация
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Логика бота
@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer("Привет! Бот на Render успешно работает!")

@dp.message(F.text)
async def echo(message: Message):
    await message.answer(f"Вы написали: {message.text}")

# Правильная установка вебхука при старте aiohttp
async def on_startup(app: web.Application):
    await bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)

# Правильное удаление вебхука при остановке
async def on_shutdown(app: web.Application):
    await bot.delete_webhook()
    await bot.session.close()

def main():
    app = web.Application()
    
    # Пинг-страница для Render (чтобы не засыпал)
    async def handle_ping(request):
        return web.Response(text="Бот активен!", content_type="text/plain")
    app.router.add_get("/", handle_ping)
    
    # Настройка обработчика вебхуков
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    
    # Связываем aiogram и aiohttp
    setup_application(app, dp, bot=bot)
    
    # Регистрируем хуки жизненного цикла сервера
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    
    # Запуск на порту Render
    port = int(os.getenv("PORT", 10000))
    web.run_app(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
