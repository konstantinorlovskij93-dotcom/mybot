import os
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

logging.basicConfig(level=logging.INFO)
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL") 
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{RENDER_URL}{WEBHOOK_PATH}"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Логика бота
@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer("Привет! Бот на Render успешно работает!")

@dp.message(F.text)
async def echo(message: Message):
    await message.answer(f"Вы написали: {message.text}")

async def on_startup(bot: Bot):
    await bot.set_webhook(url=WEBHOOK_URL)

def main():
    app = web.Application()
    
    # Ответ для вашего сайта-пингера (чтобы сервер не засыпал)
    async def handle_ping(request):
        return web.Response(text="Бот активен!")
    app.router.add_get("/", handle_ping)
    
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    
    dp.startup.register(on_startup)
    
    port = int(os.getenv("PORT", 10000))
    web.run_app(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
