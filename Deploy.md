# Deploy: запуск своего экземпляра бота

Эта инструкция позволяет любому пользователю развернуть собственную копию бота со своими ключами Telegram и Bybit.

## Требования

- Установленный Docker и Docker Compose
- Аккаунт в Telegram
- Аккаунт на Bybit со статусом **General Advertiser** (или выше) в P2P
- (для разработки) Python 3.12, Poetry

---

## 1. Получение Telegram BOT_TOKEN

1. Открой [@BotFather](https://t.me/BotFather) в Telegram.
2. Отправь команду `/newbot`.
3. Введи отображаемое имя (например `My P2P Monitor`).
4. Введи username бота (должен заканчиваться на `_bot`, например `my_p2p_monitor_bot`).
5. BotFather пришлёт токен вида `123456789:ABCdefGhIJklmnOPqrsTUvwxyz`.
6. Скопируй и сохрани токен — он понадобится в `.env`.

> **Важно:** никому не передавай токен. Если он скомпрометирован — `/revoke` в @BotFather.

---

## 2. Получение Bybit P2P API ключей

P2P API доступен **только пользователям со статусом General Advertiser** или выше. Это требование Bybit.

### 2.1. Регистрация и верификация
1. Зарегистрируйся на [bybit.com](https://www.bybit.com/).
2. Пройди KYC (Identity Verification) — обязательное условие для P2P.

### 2.2. Получение статуса P2P-рекламодателя
1. Изучи требования: [Introduction to P2P Open API](https://www.bybit.com/en/help-center/article/Introduction-to-P2P-Open-API).
2. Подай заявку на статус **General Advertiser** через раздел P2P в личном кабинете.
3. После одобрения заявки P2P API становится доступным для твоего аккаунта.

### 2.3. Создание API-ключа
1. Перейди в **Account & Security → API Management**.
2. Нажми **Create New Key → System-generated API Keys**.
3. Установи разрешения: включи группу **P2P**.
4. (Опционально) Ограничь доступ по IP для безопасности.
5. Сохрани `API Key` и `API Secret` — `Secret` показывается только один раз.

### Документация
- [P2P API Authentication](https://bybit-exchange.github.io/docs/p2p/guide)
- [Get Online Ads](https://bybit-exchange.github.io/docs/p2p/ad/online-ad-list)
- [Official Python SDK](https://github.com/bybit-exchange/bybit_p2p)

---

## 3. Настройка проекта

```bash
git clone <repo_url> p2p-monitor-bot
cd p2p-monitor-bot

cp .env.example .env
```

Отредактируй `.env`, заполнив:

| Переменная | Значение |
|---|---|
| `BOT_TOKEN` | токен от @BotFather |
| `BYBIT_API_KEY` | API Key от Bybit |
| `BYBIT_API_SECRET` | API Secret от Bybit |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Любые значения для локальной БД |

Остальные переменные можно оставить по умолчанию.

---

## 4. Запуск через Docker Compose

```bash
docker compose up -d
```

Проверь, что все сервисы стартанули:

```bash
docker compose ps
```

Все три сервиса (`postgres`, `redis`, `bot`) должны быть в статусе `running` / `healthy`.

### Применение миграций БД

```bash
docker compose exec bot alembic upgrade head
```

### Просмотр логов

```bash
docker compose logs -f bot
```

В логах должно появиться:
```
Bot connected: @<your_bot_username> (id=...)
```

---

## 5. Проверка работоспособности

1. Найди своего бота в Telegram по username.
2. Отправь `/start`.
3. На текущем этапе разработки (Фаза 1) бот не отвечает на сообщения — это нормально. Проверка на этом этапе сводится к отсутствию ошибок в логах.

---

## 6. Локальная разработка без Docker

```bash
poetry install                         # установка зависимостей
poetry shell                           # активация venv (опционально)
poetry run alembic upgrade head        # применение миграций (PG должен быть запущен)
poetry run python -m bot.main          # запуск бота
```

При локальном запуске убедись, что в `.env`:
- `POSTGRES_HOST=localhost`
- `REDIS_HOST=localhost`

---

## Управление

| Действие | Команда |
|---|---|
| Перезапустить бота | `docker compose restart bot` |
| Остановить всё | `docker compose down` |
| Остановить и удалить данные | `docker compose down -v` |
| Откатить миграции | `docker compose exec bot alembic downgrade base` |
| Создать новую миграцию | `docker compose exec bot alembic revision --autogenerate -m "..."` |

---

## Безопасность

- `.env` находится в `.gitignore` — **не коммить** реальные ключи.
- Bybit API Secret показывается только один раз — храни в надёжном месте.
- Если ключ скомпрометирован — отзови его в Bybit и создай новый.
