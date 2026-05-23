# P2P Monitor Bot

Telegram-бот для мониторинга P2P-ордеров на Bybit с настраиваемыми фильтрами и live-обновлением.

## Стек

- Python 3.12, aiogram 3.x
- PostgreSQL 16, SQLAlchemy 2 (async) + Alembic
- Redis 7
- Poetry (управление зависимостями)
- Docker Compose

## Запуск

Полная инструкция по получению ключей Telegram/Bybit и запуску — в [Deploy.md](Deploy.md).

Кратко:

```bash
cp .env.example .env       # заполнить токены
docker compose up -d
docker compose exec bot alembic upgrade head
docker compose logs -f bot
```

## Структура проекта

```
p2p/
├── bot/                # Telegram bot (aiogram)
├── db/                 # Models, repositories, Alembic migrations
├── services/           # Business logic (Bybit client, tracking engine)
├── config.py           # Settings (pydantic-settings)
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml      # Poetry: зависимости проекта
└── poetry.lock
```

## Документация проекта

- [Deploy.md](Deploy.md) — установка и запуск
- [docs/bybit-p2p-links.md](docs/bybit-p2p-links.md) — Bybit P2P API, шаринг и ограничения ссылок в приложение
- [UserStories.md](UserStories.md) — пользовательские сценарии
