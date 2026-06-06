
import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web

# Получаем токен из настроек Render
BOT_TOKEN = os.environ.get('BOT_TOKEN')

# Инициализируем бота и диспетчер
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Обработчик команды /start с кнопками
@dp.message(CommandStart())
async def command_start_handler(message: types.Message):
    # Создаем клавиатуру с кнопками
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(
        text="📱 Наш сайт", url="https://onrender.com")
    )
    builder.add(types.InlineKeyboardButton(
        text="🔥 Полезная функция", callback_data="btn_click")
    )
    # Располагаем кнопки одну под другой
    builder.adjust(1) 

    await message.answer(
        "Привет! Я работаю на Render бесплатно. Выбери нужное действие:",
        reply_markup=builder.as_markup()
    )

# Обработчик нажатия на кнопку "Полезная функция"
@dp.callback_query(F.data == "btn_click")
async def process_callback_button(callback_query: types.CallbackQuery):
    await callback_query.answer() # Убираем часы загрузки на кнопке
    await callback_query.message.answer("Вы нажали на кнопку! Здесь может быть ваше действие.")

# Веб-сервер для обмана Render
async def handle(request):
    return web.Response(text="Bot is alive")

async def main():
    app = web.Application()
    app.router.add_get('/', handle)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
    await site.start()
    
    print("Бот успешно запущен и работает!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
