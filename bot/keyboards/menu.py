from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_bot_commands() -> list[BotCommand]:
    """Возвращает список команд бота для меню"""
    return [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="settings", description="Настройки поиска")
    ]


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру главного меню"""
    builder = InlineKeyboardBuilder()
    
    builder.row(InlineKeyboardButton(
        text="⚙️ Настройки",
        callback_data="settings"
    ))
    
    return builder.as_markup()


def get_settings_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру настроек"""
    builder = InlineKeyboardBuilder()
    
    # Первая строка: Выбрать субъект РФ, Выбрать статус
    builder.row(
        InlineKeyboardButton(
            text="🏢 Выбрать субъект РФ",
            callback_data="select_subject"
        ),
        InlineKeyboardButton(
            text="📋 Выбрать статус",
            callback_data="select_status"
        )
    )
    
    # Вторая строка: Выбрать дату проведения торгов, Рассчитывать координаты
    builder.row(
        InlineKeyboardButton(
            text="📅 Выбрать дату",
            callback_data="select_date"
        ),
        InlineKeyboardButton(
            text="🌍 Координаты",
            callback_data="select_coordinates"
        )
    )
    
    # Третья строка: Начать поиск
    builder.row(InlineKeyboardButton(
        text="🔍 Начать поиск",
        callback_data="start_fetch"
    ))
    
    # Четвертая строка: Назад
    builder.row(InlineKeyboardButton(
        text="↩️ Назад",
        callback_data="back"
    ))
    
    return builder.as_markup()


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру с кнопкой отмены"""
    builder = InlineKeyboardBuilder()
    
    builder.row(InlineKeyboardButton(
        text="❌ Отменить",
        callback_data="cancel_fetch"
    ))
    
    return builder.as_markup()
