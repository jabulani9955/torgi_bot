from aiogram import Dispatcher
from bot.handlers.base import router as base_router
from bot.handlers.settings import router as settings_router


def register_all_handlers(dp: Dispatcher) -> None:
    """Регистрирует все обработчики"""
    dp.include_router(base_router)
    dp.include_router(settings_router)
