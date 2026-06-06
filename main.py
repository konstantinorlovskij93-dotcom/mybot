import asyncio
from bot import dp, bot

async def main():
    print("Бот успешно запущен и работает!")
    # Запускаем чтение сообщений из Telegram
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
import os
from aiogram import Bot, Dispatcher
# Этот кусочек кода просто откроет нужный для Render порт
if __name__ == '__main__':
    import asyncio
    from aiohttp import web
    async def handle(request):
        return web.Response(text="Bot is alive")
    app = web.Application()
    app.router.add_get('/', handle)
    # Запуск веб-сервера параллельно с ботом
    loop = asyncio.get_event_loop()
    loop.create_task(dp.start_polling(bot))
    web.run_app(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
