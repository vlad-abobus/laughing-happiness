 НАчт смотри 
## Требования

- Python **3.10+**
- Аккаунт [OpenRouter](https://openrouter.ai/) и API-ключ
- Токен бота от [@BotFather](https://t.me/BotFather)

## Быстрый старт

```bash
cd laughing-happiness-main
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # или cp на Unix
```


Запуск:

```bash
python run_bot.py
```

Альтернатива (тот же entrypoint):

```bash
python serverbot.py
```

## Переменные окружения

См. полный список в [`.env.example`](.env.example). Кратко:

| Переменная | Описание |
|------------|----------|
| `BOT_TOKEN` | Токен Telegram-бота |
| `OPENROUTER_API_KEY` | Ключ OpenRouter |
| `OPENROUTER_MODEL` | Алиас: `deepseek-chat`, `gemini`, `mistral`, `claude`, `gpt` или полный id (`vendor/model`) |
| `OPENROUTER_VISION_MODEL` | Модель с vision для проверки фото (полный id на OpenRouter) |
| `ADMIN_IDS` | ID админов через запятую |
| `DATABASE_PATH` | Путь к SQLite (по умолчанию `bot.db`) |
| `RULES_JSON_PATH` | Путь к `rules.json` |
| `ADMIN_LOG_PATH` | Файл лога действий админов |
| `PING_HOST`, `PING_PORT` | HTTP-сервер для `GET /ping` (watchdog) |
| `RATE_LIMIT_WINDOW_SEC`, `RATE_LIMIT_MAX_MESSAGES` | Ограничение частоты сообщений на пользователя |
| `AI_SYSTEM_PROMPT` | Опционально: системный промпт для `/ai` |

## Правила и тексты (`rules.json`)

В корне лежит [`rules.json`](rules.json). Если файл отсутствует или в нём ошибка JSON, подставляются значения из [`bot/config/default_rules.json`](bot/config/default_rules.json) с **merge** по ключам.

Основные блоки:

- `community_rules_text` — текст для `/rules` и блок `{rules}` в welcome
- `welcome` — `enabled`, `parse_mode`, `template` (плейсхолдеры: `{mention}`, `{rules}`, `{name}`)
- `warning_templates` — тексты предупреждений по типу нарушения
- `escalation` — пороги предупреждений до mute/ban и длительность mute
- `moderation` — флуд, спам-эвристики, списки слов/доменов, включение AI для текста и картинок

**Ссылки:** пустой `blocked_link_domains` — нарушение при любой ссылке в сообщении (для не-админов). Непустой список — блокируются только URL, содержащие указанные подстроки доменов.

## Команды в чате

**Для всех (в группе):** `/rules`, `/admins`, `/ai …`

**Только админы (`ADMIN_IDS`):**

- `/ban` — ответ на сообщение или `/ban <user_id>`
- `/mute` — ответ + длительность (`30m`, `2h`, `1d`, или секунды) или `/mute <user_id> 30m`
- `/warn`, `/unwarn` — ответ или указание `user_id`
- `/block <user_id>`, `/unblock <user_id>` — запрет/разрешение использования AI-функций бота глобально

Боту в группе нужны права на **удаление сообщений**, **ограничение участников** и **бан**, иначе часть функций не сработает.

## Модели OpenRouter

Алиасы в `OPENROUTER_MODEL` разрешаются в полные id в [`bot/config/settings.py`](bot/config/settings.py) (`resolve_chat_model_id`). Примеры:

- `deepseek-chat` → `deepseek/deepseek-chat`
- `gemini` → `google/gemini-2.0-flash-001`
- `mistral` → `mistralai/mistral-small-3.1-24b-instruct`
- `claude` → `anthropic/claude-3.5-sonnet`
- `gpt` → `openai/gpt-4o-mini`

Для картинок любую поддерживаемую на OpenRouter vision-модель в `OPENROUTER_VISION_MODEL`.

## Дополнительные скрипты

- **`watchdog.py`** — раз в 30 с запрашивает `http://127.0.0.1:8080/ping` и при смене статуса шлёт сообщение в чат. Нужны в окружении `BOT_TOKEN` и `WATCHDOG_CHAT_ID`.
- **`web.py`** — простая панель и `GET /api/overview` по SQLite (`DATABASE_PATH`, порт `FLASK_PORT`).

## Структура проекта

```
bot/
  main.py              # точка входа: polling, /ping, heartbeat
  context.py           # контекст приложения
  ai/openrouter.py     # клиент OpenRouter
  config/              # настройки и rules loader
  database/            # SQLite-схема и репозиторий
  handlers/            # admin, group, ai_cmd + middleware
  moderation/          # флуд, эвристики, сервис модерации
  utils/               # rate limit, лог, парсинг длительностей
run_bot.py
serverbot.py           # алиас запуска
rules.json
requirements.txt
```

Най все Пробуй
