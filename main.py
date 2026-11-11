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


def _parse_ids(raw: str) -> set[int]:
    result = set()
    for item in (raw or "").split(","):
        item = item.strip()
        if item.lstrip("-").isdigit():
            result.add(int(item))
    return result


def _parse_usernames(raw: str) -> set[str]:
    return {item.strip().lstrip("@").lower() for item in (raw or "").split(",") if item.strip()}


ALLOWED_USER_IDS = _parse_ids(os.getenv("ALLOWED_USER_IDS", ""))
ALLOWED_USERNAMES = _parse_usernames(os.getenv("ALLOWED_USERNAMES", ""))
MAX_HISTORY = int(os.getenv("MAX_HISTORY", "20") or 20)

bot = Bot(token=os.getenv("BOT_TOKEN", ""))
dp = Dispatcher()

_session: "aiohttp.ClientSession | None" = None
_history: dict[int, list[dict]] = {}


def is_allowed(user: types.User | None) -> bool:
    if user is None:
        return False
    if user.id in ALLOWED_USER_IDS:
        return True
    username = (user.username or "").lower()
    return bool(username) and username in ALLOWED_USERNAMES


class AccessMiddleware(BaseMiddleware):
    """Пускает только ID (и username) из белого списка."""

    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user is not None and is_allowed(user):
            return await handler(event, data)

        user_id = getattr(user, "id", None)
        username = getattr(user, "username", None)
        print(f"Отказ в доступе: id={user_id} username=@{username}", flush=True)

        if isinstance(event, types.Message):
            try:
                await event.answer(
                    "Этот бот приватный.\n"
                    f"Твой ID: {user_id}\n"
                    "Передай его владельцу бота."
                )
            except Exception:
                pass
        return None


dp.message.outer_middleware(AccessMiddleware())


def get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90))
    return _session


async def ask_openrouter(history: list[dict]) -> str:
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
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, *history],
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
        "Пиши что угодно — отвечу через OpenRouter и буду помнить, о чём мы говорили.\n"
        f"Текущая модель: {MODEL}\n\n"
        "Команды:\n"
        "/reset — забыть историю диалога\n"
        "/id — показать твой Telegram ID"
    )


@dp.message(Command("reset"))
async def cmd_reset(message: types.Message) -> None:
    _history.pop(message.chat.id, None)
    await message.answer("Историю диалога очистил — начинаем с чистого листа.")


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

    history = _history.setdefault(message.chat.id, [])
    history.append({"role": "user", "content": text})

    await bot.send_chat_action(message.chat.id, "typing")

    try:
        answer = await ask_openrouter(history)
    except Exception as error:
        print(f"Ошибка OpenRouter: {error}", flush=True)
        history.pop()
        await message.answer("Не получилось ответить, попробуй чуть позже.")
        return

    answer = answer[:TELEGRAM_LIMIT] or "Нечего добавить 🤔"
    history.append({"role": "assistant", "content": answer})

    if len(history) > MAX_HISTORY:
        del history[: len(history) - MAX_HISTORY]

    await message.answer(answer)


async def main() -> None:
    print(
        f"Белый список: ids={sorted(ALLOWED_USER_IDS) or '—'} "
        f"usernames={sorted(ALLOWED_USERNAMES) or '—'}",
        flush=True,
    )
    if not ALLOWED_USER_IDS and not ALLOWED_USERNAMES:
        print(
            "ВНИМАНИЕ: белый список пуст, бот не ответит никому. "
            "Добавь ALLOWED_USER_IDS в переменные окружения.",
            flush=True,
        )

    try:
        await dp.start_polling(bot)
    finally:
        if _session is not None and not _session.closed:
            await _session.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
