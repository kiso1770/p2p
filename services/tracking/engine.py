"""TrackingEngine — per-user asyncio task that polls Bybit and updates UI."""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import TYPE_CHECKING

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.currencies import currency_flag
from bot.keyboards.tracking import header_kb, order_kb, stopped_header_kb
from db.models import Filter, User
from db.repositories import BlacklistRepo, FilterRepo
from services.hashing import hash_description
from services.bybit_client import (
    BybitApiError,
    BybitAuthError,
    BybitClient,
    BybitError,
    BybitRateLimitError,
    BybitServerError,
    BybitTimeoutError,
)
from services.bybit_models import BybitAd
from services.order_filter import apply_filter
from services.tracking.buffer import RedisOrderBuffer
from services.tracking.state import RedisTrackingStateRepo, TrackingState

if TYPE_CHECKING:
    from bot.views import ViewMessages
    from services.tracking.registry import EngineRegistry

logger = logging.getLogger(__name__)

DEFAULT_REFRESH_INTERVAL = 15.0  # fallback if filter is missing the column
MESSAGE_OP_DELAY = 0.3           # seconds between Telegram API calls per chat
BUFFER_SIZE = 15                 # total ads kept (5 displayed + 10 reserve)
DISPLAYED_LIMIT = 5              # ads shown at once (US-7)
API_PAGE_SIZE = 300              # Bybit max page size for /v5/p2p/item/online


def _format_header(
    flt: Filter, found: int | None, error: str | None = None
) -> str:
    title_status = (
        "🟢 Отслеживание активно"
        if error is None
        else "⚠️ Отслеживание активно (с ошибкой)"
    )
    flag = currency_flag(flt.currency_id)
    side_text = "📈 Покупка" if flt.side == 0 else "📉 Продажа"
    now = datetime.now().strftime("%H:%M:%S")
    lines = [
        f"<b>{title_status}</b>",
        f"{flag} {flt.token_id}/{flt.currency_id} • {side_text} • «{flt.name}»",
        f"🕐 {now}" + (f"  •  Найдено: {found}" if found is not None else ""),
    ]
    if error:
        lines.append("")
        lines.append(f"⚠️ {error}")
    elif found == 0:
        lines.append("")
        lines.append("😔 По вашему фильтру ордеров не найдено. Ожидание...")
    return "\n".join(lines)


def _format_order(ad: BybitAd) -> str:
    lines = [
        f"<b>{ad.price} {ad.currency_id}/USDT</b>",
        f"👤 {ad.nick_name} ⭐ {ad.recent_execute_rate}% ({ad.recent_order_num} сд.)",
        f"💰 {ad.min_amount} – {ad.max_amount} USDT",
    ]
    remark = (ad.remark or "").strip()
    if remark:
        if len(remark) > 200:
            remark = remark[:200] + "…"
        lines.append(f"📝 {remark}")
    return "\n".join(lines)


class TrackingEngine:
    def __init__(
        self,
        *,
        bot: Bot,
        chat_id: int,
        user: User,
        flt: Filter,
        bybit_client: BybitClient,
        session_factory: async_sessionmaker,
        state_repo: RedisTrackingStateRepo,
        buffer: RedisOrderBuffer,
        view_messages: "ViewMessages",
        registry: "EngineRegistry",
    ) -> None:
        self._bot = bot
        self._chat_id = chat_id
        self._user_id = user.id
        self._user_telegram_id = user.telegram_id
        self._filter_id = flt.id
        self._bybit = bybit_client
        self._session_factory = session_factory
        self._state_repo = state_repo
        self._buffer = buffer
        self._view_messages = view_messages
        self._registry = registry

        self._task: asyncio.Task | None = None
        self._stopping = False
        # Cache of the filter for header rendering, refreshed every cycle
        self._cached_filter: Filter = flt
        # IDs of order messages currently displayed (kept in memory, mirrored in Redis)
        self._order_message_ids: list[int] = []
        # Maps message_id → BybitAd for currently displayed orders. Used by
        # reject_order to look up the description to blacklist.
        self._displayed: dict[int, BybitAd] = {}
        self._header_message_id: int | None = None
        # Serialise concurrent mutations of the displayed list (refresh cycle vs reject).
        self._lock = asyncio.Lock()

    # ─── lifecycle ──────────────────────────────────────────────────

    async def start(self) -> None:
        await self._send_initial_messages()
        self._task = asyncio.create_task(self._loop(), name=f"tracking:{self._chat_id}")

    async def stop(self) -> None:
        if self._stopping:
            return
        self._stopping = True

        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass

        # Delete order messages
        for msg_id in list(self._order_message_ids):
            await self._delete_message(msg_id)
            await asyncio.sleep(MESSAGE_OP_DELAY)
        self._order_message_ids.clear()
        self._displayed.clear()

        # Edit header into "stopped" state
        if self._header_message_id is not None:
            try:
                await self._bot.edit_message_text(
                    "⏹ <b>Отслеживание остановлено</b>",
                    chat_id=self._chat_id,
                    message_id=self._header_message_id,
                    reply_markup=stopped_header_kb(),
                )
            except TelegramBadRequest as exc:
                logger.debug("stop: cannot edit header: %s", exc)

        # Cleanup Redis state and buffer; keep the header message id in view
        # so /start (or back navigation) deletes it correctly.
        await self._state_repo.delete(self._chat_id)
        await self._buffer.clear(self._chat_id)
        if self._header_message_id is not None:
            await self._view_messages.set(self._chat_id, [self._header_message_id])
        self._registry.unregister(self._chat_id)

    # ─── user actions ───────────────────────────────────────────────

    async def reject_order(self, message_id: int) -> bool:
        """Hide an order: blacklist its description, delete its message,
        send the next ad from the buffer in its place.

        Returns True if reject was processed, False if there's no such
        message in the displayed set (already removed or never existed).
        """
        async with self._lock:
            ad = self._displayed.get(message_id)
            if ad is None:
                return False

            # 1) Blacklist the description (idempotent at the DB level)
            remark = (ad.remark or "").strip()
            if remark:
                try:
                    async with self._session_factory() as session:
                        await BlacklistRepo(session).add(self._user_id, remark)
                        await session.commit()
                    logger.info(
                        "Blacklisted description hash=%s for user %s",
                        hash_description(remark)[:12], self._user_telegram_id,
                    )
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to add description to blacklist")

            # 2) Delete the message and remove from in-memory state
            await self._delete_message(message_id)
            self._displayed.pop(message_id, None)
            try:
                idx = self._order_message_ids.index(message_id)
            except ValueError:
                idx = -1
            else:
                self._order_message_ids.pop(idx)

            # 3) Pop next ad from buffer and send it (if any)
            next_ad = await self._buffer.pop_next(self._chat_id)
            if next_ad is not None:
                await asyncio.sleep(MESSAGE_OP_DELAY)
                new_id = await self._send_order(next_ad)
                if new_id is not None:
                    self._order_message_ids.append(new_id)
                    self._displayed[new_id] = next_ad

            # 4) Mirror the new state to Redis
            if self._header_message_id is not None:
                await self._state_repo.update_message_ids(
                    self._chat_id,
                    self._header_message_id,
                    self._order_message_ids,
                )
                await self._view_messages.set(
                    self._chat_id,
                    [self._header_message_id, *self._order_message_ids],
                )

            return True

    # ─── loop ───────────────────────────────────────────────────────

    async def _loop(self) -> None:
        try:
            while True:
                interval = float(
                    getattr(
                        self._cached_filter, "refresh_interval_seconds",
                        DEFAULT_REFRESH_INTERVAL,
                    )
                )
                await asyncio.sleep(interval)
                if self._stopping:
                    return
                try:
                    await self._refresh_once()
                except asyncio.CancelledError:
                    raise
                except Exception:  # noqa: BLE001
                    logger.exception("Refresh cycle failed for chat %s", self._chat_id)
        except asyncio.CancelledError:
            return

    # ─── one cycle ──────────────────────────────────────────────────

    async def _send_initial_messages(self) -> None:
        ads, error_text = await self._fetch_filtered()
        flt = await self._reload_filter()
        if flt is None:
            return
        self._cached_filter = flt

        displayed = ads[:DISPLAYED_LIMIT]
        pending = ads[DISPLAYED_LIMIT:]

        header_text = _format_header(
            flt, found=None if error_text else len(ads), error=error_text
        )
        sent = await self._bot.send_message(
            self._chat_id, header_text, reply_markup=header_kb()
        )
        self._header_message_id = sent.message_id
        await asyncio.sleep(MESSAGE_OP_DELAY)

        new_ids: list[int] = []
        new_displayed: dict[int, BybitAd] = {}
        for ad in displayed:
            mid = await self._send_order(ad)
            if mid is not None:
                new_ids.append(mid)
                new_displayed[mid] = ad
            await asyncio.sleep(MESSAGE_OP_DELAY)
        self._order_message_ids = new_ids
        self._displayed = new_displayed

        await self._buffer.set(self._chat_id, pending)
        await self._state_repo.set(
            self._chat_id,
            TrackingState(
                filter_id=self._filter_id,
                header_message_id=self._header_message_id,
                order_message_ids=new_ids,
                last_activity_at=time.time(),
                status="ACTIVE",
            ),
        )
        await self._view_messages.set(
            self._chat_id, [self._header_message_id, *new_ids]
        )

    async def _refresh_once(self) -> None:
        ads, error_text = await self._fetch_filtered()
        flt = await self._reload_filter()
        if flt is None:
            return
        self._cached_filter = flt

        # 1) Edit header
        header_text = _format_header(
            flt, found=None if error_text else len(ads), error=error_text
        )
        if self._header_message_id is not None:
            try:
                await self._bot.edit_message_text(
                    header_text,
                    chat_id=self._chat_id,
                    message_id=self._header_message_id,
                    reply_markup=header_kb(),
                )
            except TelegramBadRequest as exc:
                logger.debug("refresh: cannot edit header: %s", exc)

        # 2) On API error keep the previous orders untouched.
        if error_text is not None:
            return

        # 3) Replace orders
        await self._replace_orders(ads)

    async def _replace_orders(self, ads: list[BybitAd]) -> None:
        async with self._lock:
            # Delete old orders sequentially with rate-limit-friendly delay
            for msg_id in self._order_message_ids:
                await self._delete_message(msg_id)
                await asyncio.sleep(MESSAGE_OP_DELAY)
            self._order_message_ids.clear()
            self._displayed.clear()

            displayed = ads[:DISPLAYED_LIMIT]
            pending = ads[DISPLAYED_LIMIT:]

            new_ids: list[int] = []
            new_displayed: dict[int, BybitAd] = {}
            for ad in displayed:
                mid = await self._send_order(ad)
                if mid is not None:
                    new_ids.append(mid)
                    new_displayed[mid] = ad
                await asyncio.sleep(MESSAGE_OP_DELAY)
            self._order_message_ids = new_ids
            self._displayed = new_displayed

            await self._buffer.set(self._chat_id, pending)
            if self._header_message_id is not None:
                await self._state_repo.update_message_ids(
                    self._chat_id, self._header_message_id, new_ids
                )
                await self._view_messages.set(
                    self._chat_id, [self._header_message_id, *new_ids]
                )

    # ─── helpers ────────────────────────────────────────────────────

    async def _fetch_filtered(self) -> tuple[list[BybitAd], str | None]:
        """Returns (filtered_ads, error_text). On API error: ([], "...")."""
        try:
            async with self._session_factory() as session:
                flt = await FilterRepo(session).get_by_id(self._filter_id, self._user_id)
                if flt is None:
                    return [], "Фильтр не найден"
                blacklist = await BlacklistRepo(session).get_hashes_by_user(self._user_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("DB error during fetch: %s", exc)
            return [], "Ошибка базы данных"

        try:
            result = await self._bybit.get_online_ads(
                token_id=flt.token_id,
                currency_id=flt.currency_id,
                side=flt.side,
                size=API_PAGE_SIZE,
            )
        except BybitAuthError:
            return [], "Bybit: ошибка авторизации (проверь API-ключи)"
        except BybitRateLimitError:
            return [], "Bybit: лимит запросов превышен. Повтор через 5 сек..."
        except BybitTimeoutError:
            return [], "Bybit: таймаут. Повтор через 5 сек..."
        except BybitServerError:
            return [], "Bybit: сервер недоступен. Повтор через 5 сек..."
        except BybitApiError as exc:
            return [], f"Bybit API: {exc.ret_msg}"
        except BybitError as exc:
            return [], f"Bybit: {exc}"

        filtered = apply_filter(result.items, flt, blacklist, limit=BUFFER_SIZE)
        return filtered, None

    async def _reload_filter(self) -> Filter | None:
        try:
            async with self._session_factory() as session:
                return await FilterRepo(session).get_by_id(self._filter_id, self._user_id)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to reload filter")
            return None

    async def _send_order(self, ad: BybitAd) -> int | None:
        try:
            sent = await self._bot.send_message(
                self._chat_id,
                _format_order(ad),
                reply_markup=order_kb(
                    ad.id, ad.token_id, ad.currency_id, ad.side
                ),
            )
            return sent.message_id
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to send order: %s", exc)
            return None

    async def _delete_message(self, message_id: int) -> None:
        try:
            await self._bot.delete_message(self._chat_id, message_id)
        except TelegramBadRequest as exc:
            logger.debug("delete failed for %s: %s", message_id, exc)
