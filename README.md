# Telegram Бот с OpenRouter

Приватный бот-собеседник: отвечает только пользователям из белого списка.

## Быстрый старт

### 1. Получите токен бота
Откройте [@BotFather](https://t.me/BotFather) в Telegram:
```
/newbot
```
Придумайте имя и юзернейм (должен заканчиваться на `bot`).
Сохраните полученный **BOT_TOKEN**.

### 2. Получите API ключ OpenRouter
Зарегистрируйтесь на [openrouter.ai](https://openrouter.ai) и получите API ключ
(workspace → Settings → API Keys).

### 3. Настройте Railway

1. Создайте репозиторий GitHub и загрузите файлы проекта.
2. В Railway: **Create → GitHub Repository** → выбрать репозиторий.
3. Добавьте переменные окружения:

| Переменная | Обязательна | Значение |
|---|---|---|
| `BOT_TOKEN` | да | токен от BotFather |
| `OPENROUTER_API_KEY` | да | ключ `sk-or-v1-...` |
| `MODEL` | нет | модель OpenRouter, по умолчанию `meta-llama/llama-3.1-8b-instruct` |
| `ALLOWED_USERNAMES` | нет | username через запятую без `@`, по умолчанию `sijin34` |
| `ALLOWED_USER_IDS` | нет | числовые Telegram ID через запятую, имеют приоритет |

4. Deploy — Railway соберёт образ по `Dockerfile`.

`PORT` не нужен: бот работает через long polling.

## Доступ

Все сообщения проходят через middleware `AccessMiddleware`:
- если `user.id` есть в `ALLOWED_USER_IDS` — доступ разрешён;
- иначе сравнивается `username` (без `@`, без учёта регистра) с `ALLOWED_USERNAMES`;
- всем остальным бот отвечает «Этот бот приватный.», а в логи пишется `id` и `username` отправителя.

Первый подходящий по ID или username пользователь допускается. Учтите, что username можно
сменить, поэтому для строгой защиты лучше добавить свой числовой ID в `ALLOWED_USER_IDS`
(команда `/id` в боте покажет ID).

## Структура проекта
```
bot/
├── main.py           # Код бота (aiogram + aiohttp → OpenRouter)
├── requirements.txt  # Зависимости
├── Dockerfile        # Контейнер для Railway
└── README.md         # Инструкция
```

## Возможности
- ✅ Отвечает на любые текстовые сообщения через выбранную модель OpenRouter
- ✅ Белый список пользователей (ID и/или username)
- ✅ Модель меняется переменной `MODEL`, без правки кода
- ✅ Индикатор «печатает…» пока модель думает

## Обновление
Пуш в GitHub → Railway автоматически пересобирает и перезапускает бота.
