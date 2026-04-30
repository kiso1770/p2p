# P2P Monitor Bot

Telegram-бот для мониторинга P2P-ордеров на Bybit с настраиваемыми фильтрами и live-обновлением.

## Стек

- Python 3.12, aiogram 3.x
- PostgreSQL 16, SQLAlchemy 2 (async) + Alembic
- Redis 7
- Docker Compose

## Запуск

### 1. Подготовка окружения

```bash
cp .env.example .env
# Заполнить значения: BOT_TOKEN, BYBIT_API_KEY, BYBIT_API_SECRET и др.
```

### 2. Старт контейнеров

```bash
docker compose up -d
```

Будут запущены три сервиса: `postgres`, `redis`, `bot`. Бот стартует только после прохождения healthcheck-ов БД и Redis.

### 3. Применение миграций

```bash
docker compose exec bot alembic upgrade head
```

### 4. Просмотр логов

```bash
docker compose logs -f bot
```

## Управление миграциями

| Команда | Назначение |
|---|---|
| `alembic upgrade head` | Применить все миграции |
| `alembic downgrade base` | Откатить все миграции |
| `alembic revision --autogenerate -m "..."` | Сгенерировать новую миграцию по изменениям моделей |

Все команды выполняются внутри контейнера: `docker compose exec bot <команда>`.

## Структура проекта

```
p2p/
├── bot/                # Telegram bot (aiogram)
├── db/                 # Models, repositories, Alembic migrations
├── services/           # Business logic (Bybit client, tracking engine)
├── config.py           # Settings (pydantic-settings)
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## Документация проекта

- [UserStories.md](UserStories.md) — пользовательские сценарии
