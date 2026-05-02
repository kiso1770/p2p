from aiogram import Router

from bot.handlers import edit, filters, start, tracking, wizard


def build_root_router() -> Router:
    root = Router(name="root")
    root.include_router(start.router)
    root.include_router(wizard.router)
    root.include_router(edit.router)
    root.include_router(tracking.router)
    root.include_router(filters.router)
    return root


__all__ = ["build_root_router"]
