from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from db.repositories import UserRepo


class UserMiddleware(BaseMiddleware):
    """Loads/creates the User for the current update.

    Adds two keys to the handler data:
      * `user` — the User row.
      * `is_new_user` — True when this is the very first update from the user.

    Requires DbSessionMiddleware to run first (provides `session`).
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        from_user = None
        if isinstance(event, (Message, CallbackQuery)):
            from_user = event.from_user

        if from_user is None:
            return await handler(event, data)

        session = data["session"]
        repo = UserRepo(session)

        existing = await repo.get_by_telegram_id(from_user.id)
        if existing is None:
            user = await repo.create(from_user.id, from_user.username)
            is_new = True
        else:
            user = existing
            is_new = False

        await repo.update_last_active(user.id)

        data["user"] = user
        data["is_new_user"] = is_new
        return await handler(event, data)
