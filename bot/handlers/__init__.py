from aiogram import Router

from bot.handlers import filters, start


def build_root_router() -> Router:
    root = Router(name="root")
    root.include_router(start.router)
    root.include_router(filters.router)
    return root


__all__ = ["build_root_router"]
