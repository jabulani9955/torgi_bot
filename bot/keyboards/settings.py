from typing import List, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import math
from datetime import datetime, timedelta
import calendar

from bot.utils.data import load_subjects, load_statuses


SUBJECTS_PER_PAGE = 10


def get_subjects_keyboard(page: int = 0, selected_subjects: List[str] = None) -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора субъектов РФ"""
    if selected_subjects is None:
        selected_subjects = []
    
    subjects = load_subjects()
    
    # Разбиваем на страницы по 10 субъектов
    items_per_page = 10
    total_pages = math.ceil(len(subjects) / items_per_page)
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, len(subjects))
    
    builder = InlineKeyboardBuilder()
    
    # Добавляем кнопки субъектов по одной в строку
    for subject in subjects[start_idx:end_idx]:
        code = subject["code"]
        name = subject["name"]
        prefix = "✅ " if code in selected_subjects else ""
        builder.row(InlineKeyboardButton(
            text=f"{prefix}{name}",
            callback_data=f"subject_{code}"
        ))
    
    # Добавляем кнопки навигации
    row = []
    if page > 0:
        row.append(InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="prev_page"
        ))
    
    if page < total_pages - 1:
        row.append(InlineKeyboardButton(
            text="Вперед ▶️",
            callback_data="next_page"
        ))
    
    if row:
        builder.row(*row)
    
    # Добавляем кнопку "Готово"
    builder.row(InlineKeyboardButton(
        text="✅ Готово",
        callback_data="done_subjects"
    ))
    
    return builder.as_markup()


def get_status_keyboard(selected_statuses: List[str] = None) -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора статусов"""
    if selected_statuses is None:
        selected_statuses = []
    
    statuses = load_statuses()
    
    builder = InlineKeyboardBuilder()
    
    # Добавляем кнопки статусов по одной в строку
    for status in statuses:
        code = status["code"]
        name = status["name"]
        prefix = "✅ " if code in selected_statuses else ""
        builder.row(InlineKeyboardButton(
            text=f"{prefix}{name}",
            callback_data=f"status_{code}"
        ))
    
    # Добавляем кнопку "Готово"
    builder.row(InlineKeyboardButton(
        text="✅ Готово",
        callback_data="done_statuses"
    ))
    
    return builder.as_markup()


def get_date_keyboard(is_from: bool = True) -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора даты"""
    builder = InlineKeyboardBuilder()
    
    # Добавляем кнопку отмены
    builder.row(InlineKeyboardButton(
        text="❌ Отмена",
        callback_data="cancel_date"
    ))
    
    return builder.as_markup()


def get_coordinates_keyboard(calculate_coordinates: bool) -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора опции расчета координат"""
    builder = InlineKeyboardBuilder()
    
    # Добавляем кнопки выбора
    builder.row(
        InlineKeyboardButton(
            text="✅ Да" if calculate_coordinates else "Да",
            callback_data="coordinates_yes"
        ),
        InlineKeyboardButton(
            text="✅ Нет" if not calculate_coordinates else "Нет",
            callback_data="coordinates_no"
        )
    )
    
    # Добавляем кнопку "Готово"
    builder.row(InlineKeyboardButton(
        text="✅ Готово",
        callback_data="done_coordinates"
    ))
    
    return builder.as_markup()


def get_calendar_keyboard(year: int = None, month: int = None) -> InlineKeyboardMarkup:
    """Создает клавиатуру календаря для выбора даты"""
    if year is None or month is None:
        now = datetime.now()
        year = now.year
        month = now.month
    
    builder = InlineKeyboardBuilder()
    
    # Добавляем заголовок с месяцем и годом
    month_names = [
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
    ]
    
    # Кнопки для навигации по месяцам и годам
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    
    # Добавляем кнопки навигации по месяцам и годам
    builder.row(
        InlineKeyboardButton(
            text="◀️ Год",
            callback_data=f"calendar_year_{year-1}_{month}"
        ),
        InlineKeyboardButton(
            text=f"{month_names[month-1]} {year}",
            callback_data=f"ignore"
        ),
        InlineKeyboardButton(
            text="Год ▶️",
            callback_data=f"calendar_year_{year+1}_{month}"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="◀️ Месяц",
            callback_data=f"calendar_month_{prev_year}_{prev_month}"
        ),
        InlineKeyboardButton(
            text="Месяц ▶️",
            callback_data=f"calendar_month_{next_year}_{next_month}"
        )
    )
    
    # Добавляем дни недели
    days_of_week = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    builder.row(*[InlineKeyboardButton(text=day, callback_data="ignore") for day in days_of_week])
    
    # Получаем календарь на текущий месяц
    cal = calendar.monthcalendar(year, month)
    
    # Добавляем дни месяца
    for week in cal:
        week_buttons = []
        for day in week:
            if day == 0:
                # Пустая ячейка
                week_buttons.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
            else:
                # Форматируем дату в строку YYYY-MM-DD
                date_str = f"{year}-{month:02d}-{day:02d}"
                week_buttons.append(InlineKeyboardButton(
                    text=str(day),
                    callback_data=f"date_{date_str}"
                ))
        builder.row(*week_buttons)
    
    # Добавляем кнопку отмены
    builder.row(InlineKeyboardButton(
        text="❌ Отмена",
        callback_data="cancel_date"
    ))
    
    return builder.as_markup()
