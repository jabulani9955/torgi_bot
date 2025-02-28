from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BotCommand


def get_bot_commands() -> list[BotCommand]:
    """Возвращает список команд бота для меню"""
    return [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="settings", description="Настройки поиска")
    ]


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру главного меню"""
    keyboard = [
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_settings_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру настроек"""
    keyboard = [
        [InlineKeyboardButton(text="🏢 Субъект РФ", callback_data="select_subject")],
        [InlineKeyboardButton(text="📊 Статус", callback_data="select_status")],
        [InlineKeyboardButton(text="▶️ Старт", callback_data="start_fetch")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру с кнопкой отмены"""
    keyboard = [
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_fetch")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
