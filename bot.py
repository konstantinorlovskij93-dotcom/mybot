import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# 👇 ПОДСТАВЬТЕ ВАШИ КЛЮЧИ ПРЯМО МЕЖДУ КАВЫЧКАМИ ЧЕТКО В ЭТИ ДВЕ СТРОЧКИ:
TOKEN =8958929445:AAEZCXENcybY0tnLcrZVx6l18WvVKRqcK3M
CRYPTO_TOKEN =8958929445:AAEZCXENcybY0tnLcrZVx6l18WvVKRqcK3M

# =====================================================================
# ДАЛЬШЕ НИЧЕГО НЕ ТРОГАЙТЕ И НЕ ИЗМЕНЯЙТЕ, КОД СДЕЛАЕТ ВСЁ САМ
# =====================================================================

bot = Bot(token=TOKEN)
dp = Dispatcher()
PAID_USERS = set()

async def create_invoice(amount: float, currency: str = "USDT"):
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}
    payload = {
        "asset": currency,
        "amount": str(amount),
        "description": "Оплата доступа к платному боту",
        "max_invoice_assignments": 1
    }
    async with aiohttp.ClientSession() as session:
        url = "https://cryptoboti.am"
        async with session.post(url, json=payload, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get("ok"):
                    result = data["result"]
                    return result["invoice_id"], result["bot_invoice_url"]
    return None, None

async def check_invoice(invoice_id: int):
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}
    payload = {"invoice_ids": str(invoice_id)}
    async with aiohttp.ClientSession() as session:
        url = "https://cryptoboti.am"
        async with session.post(url, json=payload, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get("ok") and data["result"]["items"]:
                    return data["result"]["items"][0]["status"] == "paid"
    return False

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    if user_id in PAID_USERS:
        await message.answer(
            "💎 **Добро пожаловать в платный раздел!**\n\n"
            "Вам открыт полный доступ. Напишите вашу команду или выберите действие в меню."
        )
    else:
        kb = [[types.InlineKeyboardButton(text="💳 Купить доступ (1 USDT)", callback_data="buy_now")]]
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=kb)
        await message.answer(
            "👋 Привет! Это закрытый платный Telegram-бот.\n\n"
            "Чтобы получить вечный доступ ко всем функциям, вам нужно оплатить входной билет.",
            reply_markup=keyboard
        )

@dp.callback_query(lambda c: c.data == "buy_now")
async def process_buy(callback: types.CallbackQuery):
    await callback.answer("Создаю счет на оплату...")
    invoice_id, invoice_url = await create_invoice(amount=1.00, currency="USDT")
    if not invoice_url:
        await callback.message.answer("❌ Ошибка платежной системы. Проверьте правильность токена CRYPTO_TOKEN.")
        return
    kb = [
        [types.InlineKeyboardButton(text="🔗 Перейти к оплате", url=invoice_url)],
        [types.InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"check_{invoice_id}")]
    ]
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=kb)
    await callback.message.answer(
        "📥 **Ваш чек готов!**\n\n"
        "Перейдите по ссылке ниже, выберите удобный способ (можно оплатить рублями прямо внутри Telegram) "
        "и после оплаты обязательно нажмите кнопку **«Проверить оплату»**.",
        reply_markup=keyboard
    )

@dp.callback_query(lambda c: c.data.startswith("check_"))
async def process_check(callback: types.CallbackQuery):
    invoice_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    is_paid = await check_invoice(invoice_id)
    if is_paid:
        PAID_USERS.add(user_id)
        await callback.answer("🎉 Оплата подтверждена!", show_alert=True)
        await callback.message.edit_text(
            "✅ **Спасибо за покупку!**\n\n"
            "Доступ успешно активирован. Отправьте команду /start, чтобы открыть меню."
        )
    else:
        await callback.answer("❌ Оплата еще не поступила. Пожалуйста, сначала оплатите счет.", show_alert=True)
