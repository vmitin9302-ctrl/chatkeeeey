import asyncio
import json
import os

import aiohttp
from aiogram import BaseMiddleware, Bot, Dispatcher, types
from aiogram.filters import Command

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = os.getenv("MODEL", "meta-llama/llama-3.1-8b-instruct")
SYSTEM_PROMPT = "Ты дружелюбный и умный помощник. Отвечай кратко, интересно и по делу."
TELEGRAM_LIMIT = 4000
DENY_TEXT = "Этот бот приватный."


def _parse_usernames(raw: str) -> set[str]:
    return {item.strip().lstrip("@").lower() for item in raw.split(",") if item.strip()}


def _parse_ids(raw: str) -> set[int]:
    result = set()
    for item in raw.split(","):
        item = item.strip()
        if item.lstrip("-").isdigit():
            result.add(int(item))
    return result


ALLOWED_USERNAMES = _parse_usernames(os.getenv("ALLOWED_USERNAMES") or "sijin34")
ALLOWED_USER_IDS = _parse_ids(os.getenv("ALLOWED_USER_IDS") or "")

bot = Bot(token=os.getenv("BOT_TOKEN", ""))
dp = Dispatcher()

_session: "aiohttp.ClientSession | None" = None


def is_allowed(user: types.User | None) -> bool:
    if user is None:
        return False
    if user.id in ALLOWED_USER_IDS:
        return True
    username = (user.username or "").lower()
    return bool(username) and username in ALLOWED_USERNAMES


class AccessMiddleware(BaseMiddleware):
    """Пускает только пользователей из белого списка."""

    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user is not None and is_allowed(user):
            return await handler(event, data)

        print(
            f"Отказ в доступе: id={getattr(user, 'id', None)} "
            f"username=@{getattr(user, 'username', None)}",
            flush=True,
        )
        if isinstance(event, types.Message):
            try:
                await event.answer(DENY_TEXT)
            except Exception:
                pass
        return None


dp.message.outer_middleware(AccessMiddleware())


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
        f"Текущая модель: {MODEL}\n\n"
        "Команда /id покажет твой Telegram ID."
    )


@dp.message(Command("id"))
async def cmd_id(message: types.Message) -> None:
    user = message.from_user
    username = f"@{user.username}" if user.username else "нет"
    await message.answer(f"Твой ID: {user.id}\nUsername: {username}")


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
