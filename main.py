import asyncio
from bot import dp, bot

async def main():
    print("Бот успешно запущен и работает!")
    # Запускаем чтение сообщений из Telegram
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
