# TODO — план разработки P2P Monitor Bot

Чек-лист всех фаз и задач, согласованных в начале проекта (см. [UserStories.md](UserStories.md)). Обновлять при завершении задачи.

---

## Фаза 1 — Инфраструктура проекта

- [x] Структура папок и `.gitignore`
- [x] `pyproject.toml` (Poetry) + `poetry.lock`
- [x] `.env.example` + `config.py` (pydantic-settings)
- [x] `db/session.py` + `db/models.py` (User, Filter, DescriptionBlacklist)
- [x] Alembic init + async `env.py` + миграция `0001_initial_schema` (с триггером `update_updated_at`)
- [x] `Dockerfile` (multi-stage Poetry export) + `docker-compose.yml` (postgres + redis + bot)
- [x] `bot/main.py` (заглушка)
- [x] `README.md` + `Deploy.md`

## Фаза 2 — Bybit API клиент

- [x] `services/bybit_models.py` (Pydantic v2)
- [x] `services/bybit_client.py` с HMAC-SHA256 подписью
- [x] Автосинхронизация серверного времени Bybit
- [x] Иерархия исключений (Auth/RateLimit/Server/Timeout/Api)
- [x] `services/order_filter.py` — клиентская фильтрация и сортировка
- [x] `services/hashing.py` — нормализованный SHA-256 для описаний
- [x] Unit-тесты подписи (golden test) и фильтра (~12 кейсов)
- [x] Integration smoke-test реального Bybit API

## Фаза 3 — Репозитории БД и Redis-обвязки

- [x] `UserRepo` (`get_or_create`, `update_last_active`)
- [x] `FilterRepo` (CRUD + `name_exists` + owner check)
- [x] `BlacklistRepo` через `INSERT ON CONFLICT DO NOTHING`
- [x] `RedisTrackingStateRepo` (Hash на `tracking:{chat_id}`)
- [x] `RedisOrderBuffer` (List на `tracking_buffer:{chat_id}` с pipeline)
- [x] Тестовая инфраструктура: проброс портов, изолированная `p2p_test_db`
- [x] Тесты на все репозитории

## Фаза 4 — Регистрация и главное меню

- [x] `DbSessionMiddleware` — транзакция на каждый update
- [x] `UserMiddleware` — `get_or_create` + флаг `is_new_user`
- [x] `main_menu_kb` + `/start` handler
- [x] `services/tracking/lifecycle.stop_tracking` (best-effort cleanup)
- [x] Тесты middleware + lifecycle + start

## Фаза 5a — Просмотр и удаление фильтров

- [x] `bot/views.py` — `ViewMessages` + `delete_current_view`
- [x] `bot/keyboards/filters.py` — клавиатуры списка/удаления + `format_filter`
- [x] `bot/handlers/filters.py` — `menu:filters`, `menu:back_to_main`, delete-flow
- [x] Owner-check на удаление
- [x] Inline-edit подтверждение удаления (без лишних сообщений)
- [x] `RedisStorage` для FSM в `bot/main.py`
- [x] Тесты handlers и views

## Фаза 5b — Wizard создания фильтра

- [x] `bot/states/wizard.py` — `CreateFilter` (3 состояния)
- [x] `bot/keyboards/wizard.py` — currency picker (с пагинацией), side picker, name input
- [x] `bot/currencies.py` — 80 фиатных валют + автогенерация флагов
- [x] `bot/handlers/wizard.py` — все шаги + Cancel + Back
- [x] Валидация имени (1–32, уникальность per user)
- [x] Edit wizard-сообщения с префиксом `⚠️` при ошибке
- [x] `/start` чистит FSM
- [x] Тесты wizard'а

## Фаза 5c — Редактор параметров

- [x] `EditFilter` StatesGroup (12 состояний)
- [x] Все клавиатуры редактора (`bot/keyboards/edit.py`)
- [x] Главный экран редактора
- [x] Группа: Диапазон суммы (2-step с проверкой `min ≤ max`)
- [x] Группа: Диапазон курса (то же)
- [x] Группа: Опыт и репутация (мин. сделок + Completion Rate)
- [x] Группа: Описание (toggle "Без описания" + Whitelist/Blacklist CSV)
- [x] Группа: Сортировка / количество / интервал
- [x] Skip / Back на каждом шаге (state-aware)
- [x] Eager-save модель
- [x] Wizard после успешного создания → редиректит в редактор
- [x] Тесты для всех групп

### Доработки фазы 5

- [x] Поле `refresh_interval_seconds` в фильтре (5–600с, default 15)
- [x] Миграция `0002_refresh_interval`
- [x] Отображение интервала в `format_filter` и редакторе
- [x] Engine использует интервал из фильтра

## Фаза 6a — Базовый движок отслеживания

- [x] `services/tracking/engine.py` — `TrackingEngine` (asyncio task)
- [x] `services/tracking/registry.py` — `EngineRegistry`
- [x] `services/tracking/url.py` — URL builder для кнопки "Купить"
- [x] `bot/keyboards/tracking.py` — header + order keyboards
- [x] `bot/handlers/tracking.py` — `filter:start`, `tracking:stop`
- [x] Header edit каждый цикл (время + счётчик найденных)
- [x] Замена order messages с задержкой 0.3с между ops (rate-limit)
- [x] Обработка всех ошибок Bybit (header показывает ошибку, ордера сохраняются)
- [x] `stop_tracking` интеграция с registry
- [x] Graceful shutdown всех engines в `main.py`
- [x] `/start` отменяет активный engine через registry
- [x] Тесты engine

## Фаза 6b — Действия по ордерам

- [ ] `❌ Не подходит` — добавление в blacklist + удаление сообщения + pop из buffer + send нового
- [ ] Управление displayed-mapping (`message_id ↔ ad`)
- [ ] Toast-уведомление через `answerCallbackQuery`
- [ ] Тесты reject-flow

## Фаза 6c — Автостоп и пауза

- [ ] Таймер автостопа (5 минут) — `asyncio.Task`
- [ ] Reset таймера на каждом callback ("Не подходит")
- [ ] `▶️ Возобновить` — кнопка после остановки
- [ ] State `STOPPED_BY_TIMEOUT` vs `STOPPED_MANUALLY`
- [ ] Тесты автостопа

## Фаза 8 — Настройки / чёрный список

- [ ] Раздел `⚙️ Настройки`
- [ ] Просмотр черного списка описаний (одно сообщение на запись)
- [ ] Удаление одной записи
- [ ] `🗑 Очистить всё` с подтверждением
- [ ] Тесты handlers

## Фаза 9 — Устойчивость и обработка ошибок

- [ ] Глобальный exception handler aiogram
- [ ] Обработка Telegram flood limit (`RetryAfter`) в очереди сообщений
- [ ] Структурированное логирование (уровни DEBUG/INFO/ERROR)
- [ ] Retry с backoff для критичных Bybit-вызовов

## Фаза 10 — Деплой

- [x] `Dockerfile` + `docker-compose.yml` (готово в Фазе 1)
- [x] `Deploy.md` с инструкцией по получению ключей
- [ ] (опционально) GitHub Actions для линтера
- [ ] (опционально) production-конфигурация (sentry, structured logging)

---

## Открытые задачи (вне основного плана)

### Поведение ссылки "💚 Купить →"

**Текущее состояние**: URL ведёт на `https://www.bybit.com/en-US/p2p/{buy|sell}/{token}/{currency}?adNo={ad_id}` — открывается список ордеров в приложении Bybit / браузере, но **не на конкретный ордер**.

**Причина**: Bybit deep-link на конкретный ордер требует `share_id` (32-char hex), который генерируется только при шаринге ордера из приложения и не возвращается публичным API.

**Дополнительные ограничения**:
- Telegram in-app WebView не триггерит Universal Links / App Links — нужен external browser
- На некоторых устройствах требуется long-tap → "Открыть во внешнем браузере"

**TODO**: Проработать поведение работы ссылок:
- [ ] Изучить, есть ли в Bybit P2P API метод получения share_id для ad_id (или эквивалент)
- [ ] Альтернатива: открывать профиль продавца (`/p2p/profile/{userId}`) — там обычно 1–5 ордеров этого пользователя, нужный легко найти
- [ ] Альтернатива: фильтровать листинг по точной цене или диапазону (если URL поддерживает)
- [ ] Документировать в README/Deploy.md требования к настройкам Telegram (внешний браузер) и Bybit-приложения (универсальные ссылки)
- [ ] (опционально) Отправлять seller nickname текстом рядом с кнопкой, чтобы легко найти в листинге
