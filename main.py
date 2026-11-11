import asyncio
import json
import os

import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = os.getenv("MODEL", "meta-llama/llama-3.1-8b-instruct")
SYSTEM_PROMPT = "Ты дружелюбный и умный помощник. Отвечай кратко, интересно и по делу."
TELEGRAM_LIMIT = 4000

bot = Bot(token=os.getenv("BOT_TOKEN", ""))
dp = Dispatcher()

_session: "aiohttp.ClientSession | None" = None


def get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90))
    return _session


async def ask_openrouter(user_text: str) -> str:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY не задан")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Title": "chatkeeeey",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.7,
        "max_tokens": 800,
    }

    async with get_session().post(OPENROUTER_URL, headers=headers, json=payload) as resp:
        try:
            data = await resp.json(content_type=None)
        except (json.JSONDecodeError, aiohttp.ContentTypeError):
            raise RuntimeError(f"OpenRouter вернул не JSON (HTTP {resp.status})")

        if resp.status != 200:
            error = data.get("error") if isinstance(data, dict) else None
            message = error.get("message") if isinstance(error, dict) else str(data)
            raise RuntimeError(f"OpenRouter HTTP {resp.status}: {message}")

        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(f"Пустой ответ OpenRouter: {data}")

        content = (choices[0].get("message") or {}).get("content") or ""
        return content.strip()


@dp.message(Command("start"))
async def cmd_start(message: types.Message) -> None:
    await message.answer(
        "👋 Привет! Я бот-собеседник.\n\n"
        "Пиши что угодно — отвечу через OpenRouter.\n"
        f"Текущая модель: {MODEL}"
    )


@dp.message()
async def handle_message(message: types.Message) -> None:
    text = (message.text or "").strip()

    if not text:
        await message.answer("Я понимаю только текст 🙂")
        return

    await bot.send_chat_action(message.chat.id, "typing")

    try:
        answer = await ask_openrouter(text)
    except Exception as error:
        print(f"Ошибка OpenRouter: {error}", flush=True)
        await message.answer("Не получилось ответить, попробуй чуть позже.")
        return

    await message.answer(answer[:TELEGRAM_LIMIT] or "Нечего добавить 🤔")


async def main() -> None:
    try:
        await dp.start_polling(bot)
    finally:
        if _session is not None and not _session.closed:
            await _session.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
