import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from openai import AsyncOpenAI

# Инициализация OpenRouter клиента
client = AsyncOpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

# Инициализация бота
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет! Я твой умный бот!\n\n"
        "Я могу:\n"
        "• Отвечать на любые вопросы\n"
        "• Помогать с задачами\n"
        "• Обсуждать любую тему\n\n"
        "Напиши что-нибудь, и я отвечу!"
    )


@dp.message()
async def handle_message(message: types.Message):
    user_text = (message.text or "").strip()
    
    if not user_text:
        return
    
    # Простые ответы без вызова API
    simple_responses = {
        "привет": "Привет! Как дела?",
        "как дела": "У меня всё отлично, спасибо! А у тебя?",
        "кто ты": "Я умный Telegram-бот с подключением к OpenRouter!",
        "погода": "Я не могу проверять погоду напрямую, но могу рассказать о климате любой страны!",
    }
    
    # Проверка простых ответов
    for keyword, response in simple_responses.items():
        if keyword in user_text.lower():
            await message.answer(response)
            return
    
    # Если текст не пустой и не простой ответ - используем OpenRouter
    if len(user_text) > 3:
        try:
            # Формируем запрос к OpenRouter
            response = await client.chat.completions.create(
                model="meta-llama/llama-3.1-8b-instruct",  # Самая дешёвая модель (~$0.15/1M токенов)
                messages=[
                    {
                        "role": "system",
                        "content": "Ты дружелюбный и умный помощник. Отвечай кратко, интересно и по делу."
                    },
                    {
                        "role": "user", 
                        "content": user_text
                    }
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            ai_response = response.choices[0].message.content
            
            # Отправляем ответ пользователю
            await message.answer(ai_response)
            
        except Exception as e:
            print(f"Ошибка OpenRouter: {e}")
            await message.answer(
                "Извини, сейчас не могу ответить. Попробуй позже!"
            )
    else:
        # Короткие сообщения - простой ответ
        await message.answer("Интересно! Расскажи подробнее.")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
