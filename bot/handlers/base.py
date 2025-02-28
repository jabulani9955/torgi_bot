from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.keyboards.menu import get_main_menu_keyboard, get_settings_keyboard
from bot.states.settings import SettingsState


router = Router()


@router.message(CommandStart())
async def command_start(message: Message, state: FSMContext) -> None:
    """Обработчик команды /start"""
    await state.clear()
    await message.answer(
        "Привет!\nЯ помогу получить нужную информацию из сайта torgi.gov.ru\n"
        "Нажми на кнопку ⚙️ Настройки для настройки поиска",
        reply_markup=get_main_menu_keyboard()
    )


@router.callback_query(F.data == "settings")
async def show_settings(callback: CallbackQuery, state: FSMContext) -> None:
    """Показывает меню настроек"""
    await state.set_state(SettingsState.main_menu)
    await callback.message.edit_text(
        "⚙️ Настройки поиска:",
        reply_markup=get_settings_keyboard()
    )
    await callback.answer()
