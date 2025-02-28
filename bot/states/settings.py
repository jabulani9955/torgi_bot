from aiogram.fsm.state import State, StatesGroup


class SettingsState(StatesGroup):
    main_menu = State()
    selecting_subject = State()
    selecting_status = State()
    selecting_date_from = State()
    selecting_date_to = State()
    selecting_coordinates = State()
