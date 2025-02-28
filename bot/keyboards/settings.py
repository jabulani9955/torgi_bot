from typing import List
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.utils.data import load_subjects, load_statuses


SUBJECTS_PER_PAGE = 10


def get_subjects_keyboard(page: int, selected_subjects: List[str]) -> InlineKeyboardMarkup:
    """Создает клавиатуру выбора субъектов с пагинацией"""
    subjects = load_subjects()
    start_idx = page * SUBJECTS_PER_PAGE
    end_idx = min(start_idx + SUBJECTS_PER_PAGE, len(subjects))
    
    keyboard = []
    for subject in subjects[start_idx:end_idx]:
        is_selected = subject["code"] in selected_subjects
        mark = "✅ " if is_selected else ""
        keyboard.append([
            InlineKeyboardButton(
                text=f"{mark}{subject['name']}", 
                callback_data=f"subject_{subject['code']}"
            )
        ])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data="prev_page"))
    if end_idx < len(subjects):
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data="next_page"))
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton(text="✅ Готово", callback_data="done_subjects")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_status_keyboard(selected_statuses: List[str]) -> InlineKeyboardMarkup:
    """Создает клавиатуру выбора статусов"""
    statuses = load_statuses()
    keyboard = []
    for status in statuses:
        is_selected = status["code"] in selected_statuses
        mark = "✅ " if is_selected else ""
        keyboard.append([
            InlineKeyboardButton(
                text=f"{mark}{status['name']}", 
                callback_data=f"status_{status['code']}"
            )
        ])
    keyboard.append([InlineKeyboardButton(text="✅ Готово", callback_data="done_statuses")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
