import json
import os
from datetime import datetime, timedelta
from typing import Dict, Optional
import asyncio

import aiohttp
import pandas as pd
from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
import structlog
from aiogram.exceptions import TelegramBadRequest

from bot.keyboards.menu import (
    get_main_menu_keyboard,
    get_settings_keyboard,
    get_cancel_keyboard
)
from bot.keyboards.settings import (
    get_subjects_keyboard,
    get_status_keyboard,
    get_date_keyboard,
    get_coordinates_keyboard,
    get_calendar_keyboard
)
from bot.services.data_fetcher import fetch_data
from bot.states.settings import SettingsState
from bot.utils.data import load_subjects, load_statuses
from bot.config import load_config


router = Router()
logger = structlog.get_logger()

# Словарь для хранения задач получения данных
fetch_tasks: Dict[int, asyncio.Task] = {}


def get_readable_filename(subjects: list[str], statuses: list[str]) -> str:
    """Создает читаемое имя файла с русскими названиями субъектов и статусов"""
    all_subjects = load_subjects()
    all_statuses = load_statuses()
    
    # Получаем русские названия
    subject_names = []
    for subject in subjects:
        for s in all_subjects:
            if s["code"] == subject:
                subject_names.append(s["name"].replace(" ", "_"))
                break
    
    status_names = []
    for status in statuses:
        for s in all_statuses:
            if s["code"] == status:
                status_names.append(s["name"].replace(" ", "_"))
                break
    
    # Формируем имя файла
    date_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    subjects_str = "-".join(subject_names) if len(subject_names) <= 2 else f"{len(subject_names)}_субъектов"
    statuses_str = "-".join(status_names) if len(status_names) <= 2 else f"{len(status_names)}_статусов"
    
    return f"Torgi_{subjects_str}_{statuses_str}_{date_str}.xlsx"


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Обработчик команды /start"""
    await state.clear()
    await message.answer(
        "👋 Привет! Я помогу вам получить данные с torgi.gov.ru\n"
        "Для начала работы перейдите в настройки и выберите параметры поиска.",
        reply_markup=get_main_menu_keyboard()
    )


@router.message(Command("settings"))
async def cmd_settings(message: Message, state: FSMContext) -> None:
    """Обработчик команды /settings"""
    await state.set_state(SettingsState.main_menu)
    await message.answer(
        "⚙️ Настройки поиска:",
        reply_markup=get_settings_keyboard()
    )


async def update_progress(
    message: Message,
    current: int,
    total: int,
    user_id: int
) -> None:
    """Обновляет сообщение с прогрессом"""
    if user_id not in fetch_tasks or fetch_tasks[user_id].cancelled():
        return
        
    try:
        await message.edit_text(
            f"⏳ Загрузка данных...\n"
            f"Обработано страниц: {current}/{total}\n"
            f"Пожалуйста, подождите.",
            reply_markup=get_cancel_keyboard()
        )
    except Exception as e:
        logger.error("Failed to update progress", error=str(e))


@router.callback_query(F.data == "cancel_fetch")
async def cancel_fetch(callback: CallbackQuery, state: FSMContext) -> None:
    """Отменяет текущий запрос данных"""
    # Сразу отвечаем на callback, чтобы избежать ошибки с устаревшим запросом
    await callback.answer()
    
    user_id = callback.from_user.id
    
    if user_id in fetch_tasks and not fetch_tasks[user_id].done():
        fetch_tasks[user_id].cancel()
        await callback.message.edit_text(
            "❌ Запрос отменен.",
            reply_markup=get_settings_keyboard()
        )
        logger.info("Fetch task cancelled by user", user_id=user_id)
    else:
        await callback.message.edit_text(
            "❓ Нет активных запросов для отмены.",
            reply_markup=get_settings_keyboard()
        )


@router.callback_query(F.data == "select_subject")
async def select_subject(callback: CallbackQuery, state: FSMContext) -> None:
    """Показывает меню выбора субъектов"""
    # Сразу отвечаем на callback, чтобы избежать ошибки с устаревшим запросом
    await callback.answer()
    
    data = await state.get_data()
    current_page = data.get("current_page", 0)
    selected_subjects = data.get("selected_subjects", [])
    
    await state.set_state(SettingsState.selecting_subject)
    await callback.message.edit_text(
        "Выберите субъекты РФ:",
        reply_markup=get_subjects_keyboard(current_page, selected_subjects)
    )


@router.callback_query(F.data == "select_status")
async def select_status(callback: CallbackQuery, state: FSMContext) -> None:
    """Показывает меню выбора статусов"""
    # Сразу отвечаем на callback, чтобы избежать ошибки с устаревшим запросом
    await callback.answer()
    
    data = await state.get_data()
    selected_statuses = data.get("selected_statuses", [])
    
    await state.set_state(SettingsState.selecting_status)
    await callback.message.edit_text(
        "Выберите статусы:",
        reply_markup=get_status_keyboard(selected_statuses)
    )


@router.callback_query(F.data == "select_date")
async def select_date(callback: CallbackQuery, state: FSMContext) -> None:
    """Показывает календарь для выбора даты проведения торгов"""
    # Отвечаем на callback сразу, чтобы предотвратить ошибку "query is too old"
    await callback.answer()
    
    await state.set_state(SettingsState.selecting_date_from)
    await callback.message.edit_text(
        "Выберите дату начала периода проведения торгов:",
        reply_markup=get_calendar_keyboard()
    )


@router.callback_query(F.data.startswith("calendar_month_"))
async def process_calendar_month(callback: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает выбор месяца в календаре"""
    # Отвечаем на callback сразу, чтобы предотвратить ошибку "query is too old"
    await callback.answer()
    
    # Извлекаем год и месяц из callback_data
    parts = callback.data.split("_")
    year = int(parts[2])
    month = int(parts[3])
    
    # Получаем текущее состояние
    current_state = await state.get_state()
    
    # Обновляем календарь
    if current_state == SettingsState.selecting_date_from:
        await callback.message.edit_text(
            "Выберите дату начала периода проведения торгов:",
            reply_markup=get_calendar_keyboard(year, month)
        )
    else:
        await callback.message.edit_text(
            "Выберите дату окончания периода проведения торгов:",
            reply_markup=get_calendar_keyboard(year, month)
        )


@router.callback_query(F.data.startswith("calendar_year_"))
async def process_calendar_year(callback: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает выбор года в календаре"""
    # Отвечаем на callback сразу, чтобы предотвратить ошибку "query is too old"
    await callback.answer()
    
    # Извлекаем год и месяц из callback_data
    parts = callback.data.split("_")
    year = int(parts[2])
    month = int(parts[3])
    
    # Получаем текущее состояние
    current_state = await state.get_state()
    
    # Обновляем календарь
    if current_state == SettingsState.selecting_date_from:
        await callback.message.edit_text(
            "Выберите дату начала периода проведения торгов:",
            reply_markup=get_calendar_keyboard(year, month)
        )
    else:
        await callback.message.edit_text(
            "Выберите дату окончания периода проведения торгов:",
            reply_markup=get_calendar_keyboard(year, month)
        )


@router.callback_query(F.data.startswith("date_"))
async def process_date_selection(callback: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает выбор даты в календаре"""
    # Отвечаем на callback сразу, чтобы предотвратить ошибку "query is too old"
    await callback.answer()
    
    # Извлекаем дату из callback_data
    date_str = callback.data.split("_")[1]
    
    # Получаем текущее состояние
    current_state = await state.get_state()
    
    if current_state == SettingsState.selecting_date_from:
        # Сохраняем дату начала
        await state.update_data(date_from=date_str)
        
        # Переходим к выбору даты окончания
        await state.set_state(SettingsState.selecting_date_to)
        
        # Показываем календарь для выбора даты окончания
        await callback.message.edit_text(
            "Выберите дату окончания периода проведения торгов:",
            reply_markup=get_calendar_keyboard()
        )
    else:
        # Получаем дату начала
        data = await state.get_data()
        date_from_str = data.get("date_from")
        
        # Проверяем, что дата окончания не раньше даты начала
        if date_str < date_from_str:
            await callback.message.edit_text(
                "❌ Дата окончания не может быть раньше даты начала. Пожалуйста, выберите корректную дату:",
                reply_markup=get_calendar_keyboard()
            )
            return
        
        # Сохраняем дату окончания
        await state.update_data(date_to=date_str)
        
        # Возвращаемся в меню настроек
        await state.set_state(SettingsState.main_menu)
        await callback.message.edit_text(
            f"✅ Период проведения торгов установлен: с {date_from_str} по {date_str}",
            reply_markup=get_settings_keyboard()
        )


@router.callback_query(F.data == "ignore")
async def ignore_callback(callback: CallbackQuery) -> None:
    """Игнорирует callback от неактивных кнопок календаря"""
    await callback.answer()


@router.callback_query(F.data == "select_coordinates")
async def select_coordinates(callback: CallbackQuery, state: FSMContext) -> None:
    """Показывает меню выбора опции расчета координат"""
    # Отвечаем на callback сразу, чтобы предотвратить ошибку "query is too old"
    await callback.answer()
    
    data = await state.get_data()
    calculate_coordinates = data.get("calculate_coordinates", False)
    
    await state.set_state(SettingsState.selecting_coordinates)
    await callback.message.edit_text(
        "Рассчитывать координаты по кадастровым номерам?\n"
        "⚠️ Внимание: расчет координат может значительно увеличить время обработки данных.",
        reply_markup=get_coordinates_keyboard(calculate_coordinates)
    )


@router.callback_query(F.data.in_(["coordinates_yes", "coordinates_no"]))
async def process_coordinates_selection(callback: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает выбор опции расчета координат"""
    calculate_coordinates = callback.data == "coordinates_yes"
    
    # Отвечаем на callback сразу, чтобы предотвратить ошибку "query is too old"
    await callback.answer(
        "✅ Расчет координат включен" if calculate_coordinates else "✅ Расчет координат отключен"
    )
    
    await state.update_data(calculate_coordinates=calculate_coordinates)
    
    await callback.message.edit_text(
        "Рассчитывать координаты по кадастровым номерам?\n"
        "⚠️ Внимание: расчет координат может значительно увеличить время обработки данных.",
        reply_markup=get_coordinates_keyboard(calculate_coordinates)
    )


@router.callback_query(F.data == "cancel_date")
async def cancel_date_selection(callback: CallbackQuery, state: FSMContext) -> None:
    """Отменяет выбор даты"""
    # Отвечаем на callback сразу, чтобы предотвратить ошибку "query is too old"
    await callback.answer()
    
    await state.set_state(SettingsState.main_menu)
    await callback.message.edit_text(
        "⚙️ Настройки поиска:",
        reply_markup=get_settings_keyboard()
    )


@router.callback_query(F.data.startswith("subject_"))
async def process_subject_selection(callback: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает выбор субъекта"""
    data = await state.get_data()
    selected_subjects = data.get("selected_subjects", [])
    current_page = data.get("current_page", 0)
    
    subject_code = callback.data.split("_")[1]
    was_selected = subject_code in selected_subjects
    
    # Отвечаем на callback сразу, чтобы предотвратить ошибку "query is too old"
    await callback.answer(
        "✅ Субъект убран" if was_selected else "✅ Субъект добавлен"
    )
    
    if was_selected:
        selected_subjects.remove(subject_code)
    else:
        selected_subjects.append(subject_code)
    
    await state.update_data(selected_subjects=selected_subjects)
    
    # Создаем новую клавиатуру
    new_keyboard = get_subjects_keyboard(current_page, selected_subjects)
    
    try:
        await callback.message.edit_text(
            "Выберите субъекты РФ:",
            reply_markup=new_keyboard
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            # Если ошибка не связана с отсутствием изменений, пробрасываем её дальше
            raise


@router.callback_query(F.data.startswith("status_"))
async def process_status_selection(callback: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает выбор статуса"""
    data = await state.get_data()
    selected_statuses = data.get("selected_statuses", [])
    
    # Извлекаем полный код статуса после префикса "status_"
    status_code = "_".join(callback.data.split("_")[1:])  # Изменено здесь
    was_selected = status_code in selected_statuses
    
    # Перемещаем вызов callback.answer() в начало функции
    await callback.answer(
        "✅ Статус убран" if was_selected else "✅ Статус добавлен"
    )
    
    if was_selected:
        selected_statuses.remove(status_code)
    else:
        selected_statuses.append(status_code)
    
    await state.update_data(selected_statuses=selected_statuses)
    
    # Создаем новую клавиатуру
    new_keyboard = get_status_keyboard(selected_statuses)
    
    try:
        await callback.message.edit_text(
            "Выберите статусы:",
            reply_markup=new_keyboard
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            # Если ошибка не связана с отсутствием изменений, пробрасываем её дальше
            raise


@router.callback_query(F.data.in_(["prev_page", "next_page"]))
async def process_pagination(callback: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает пагинацию"""
    # Отвечаем на callback сразу, чтобы предотвратить ошибку "query is too old"
    await callback.answer()
    
    data = await state.get_data()
    current_page = data.get("current_page", 0)
    selected_subjects = data.get("selected_subjects", [])
    
    if callback.data == "prev_page":
        current_page = max(0, current_page - 1)
    else:
        subjects = load_subjects()
        max_page = (len(subjects) - 1) // 10
        current_page = min(max_page, current_page + 1)
    
    await state.update_data(current_page=current_page)
    await callback.message.edit_text(
        "Выберите субъекты РФ:",
        reply_markup=get_subjects_keyboard(current_page, selected_subjects)
    )


@router.callback_query(F.data.in_(["done_subjects", "done_statuses", "done_coordinates"]))
async def return_to_settings(callback: CallbackQuery, state: FSMContext) -> None:
    """Возвращает в меню настроек"""
    # Отвечаем на callback сразу, чтобы предотвратить ошибку "query is too old"
    await callback.answer()
    
    await state.set_state(SettingsState.main_menu)
    await callback.message.edit_text(
        "⚙️ Настройки поиска:",
        reply_markup=get_settings_keyboard()
    )


@router.callback_query(F.data == "back")
async def go_back(callback: CallbackQuery, state: FSMContext) -> None:
    """Возвращает в главное меню"""
    # Отвечаем на callback сразу, чтобы предотвратить ошибку "query is too old"
    await callback.answer()
    
    await state.clear()
    await callback.message.edit_text(
        "Главное меню",
        reply_markup=get_main_menu_keyboard()
    )


@router.callback_query(F.data == "start_fetch")
async def start_data_fetch(callback: CallbackQuery, state: FSMContext) -> None:
    """Запускает процесс получения данных"""
    # Сразу отвечаем на callback, чтобы избежать таймаута
    await callback.answer()
    
    user_id = callback.from_user.id
    if user_id in fetch_tasks and not fetch_tasks[user_id].done():
        await callback.message.edit_text(
            "⚠️ У вас уже есть активный запрос. Дождитесь его завершения или отмените.",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    data = await state.get_data()
    selected_subjects = data.get("selected_subjects", [])
    selected_statuses = data.get("selected_statuses", [])
    date_from = data.get("date_from")
    date_to = data.get("date_to")
    calculate_coordinates = data.get("calculate_coordinates", False)
    
    if not selected_subjects or not selected_statuses:
        await callback.message.edit_text(
            "❌ Необходимо выбрать хотя бы один субъект и один статус!",
            reply_markup=get_settings_keyboard()
        )
        return
    
    status_message = await callback.message.edit_text(
        "⏳ Бот начал работать, ожидайте...\n"
        "Это может занять некоторое время в зависимости от количества выбранных параметров.",
        reply_markup=get_cancel_keyboard()
    )
    
    try:
        logger.info(
            "Starting data fetch",
            subjects=selected_subjects,
            statuses=selected_statuses,
            date_from=date_from,
            date_to=date_to,
            calculate_coordinates=calculate_coordinates,
            user_id=user_id
        )
        
        # Создаем и сохраняем задачу
        fetch_tasks[user_id] = asyncio.create_task(fetch_data(
            selected_subjects,
            selected_statuses,
            date_from=date_from,
            date_to=date_to,
            progress_callback=lambda current, total: update_progress(
                status_message, current, total, user_id
            )
        ))
        
        # Ждем завершения задачи
        try:
            data = await fetch_tasks[user_id]
        except asyncio.CancelledError:
            logger.info("Fetch task was cancelled", user_id=user_id)
            return
        finally:
            # Удаляем задачу из словаря
            fetch_tasks.pop(user_id, None)
        
        if not data:
            await status_message.edit_text(
                "❌ Не найдено данных по выбранным параметрам",
                reply_markup=get_settings_keyboard()
            )
            return
            
        await status_message.edit_text(
            f"📊 Обработка {len(data)} записей...\n"
            "Создание Excel файла..."
        )
        
        try:
            # Используем новую функцию обработки данных
            from bot.utils.data_processing import data_processing
            # Загружаем конфигурацию
            config = load_config()
            # Устанавливаем опцию расчета координат
            config.processing.calculate_coordinates = calculate_coordinates
            filename = data_processing(data, selected_subjects, selected_statuses, config)
            
            if not filename:
                await status_message.edit_text(
                    "❌ Ошибка при обработке данных",
                    reply_markup=get_settings_keyboard()
                )
                return
            
            # Создаем FSInputFile для корректной отправки файла
            file = FSInputFile(filename)
            
            # Формируем текст сообщения
            date_info = ""
            if date_from and date_to:
                date_info = f"\n📅 Период: с {date_from} по {date_to}"
            
            coords_info = "\n🌍 Расчет координат: включен" if calculate_coordinates else ""
            
            await callback.message.answer_document(
                document=file,
                caption=(
                    f"✅ Данные успешно загружены!\n"
                    f"📊 Количество записей: {len(data)}\n"
                    f"🏢 Выбрано субъектов: {len(selected_subjects)}{date_info}{coords_info}"
                )
            )
            
            await status_message.edit_text(
                "⚙️ Настройки поиска:",
                reply_markup=get_settings_keyboard()
            )
            
        except Exception as e:
            logger.error(
                "Error during data processing",
                error=str(e),
                user_id=user_id
            )
            await status_message.edit_text(
                f"❌ Произошла ошибка при обработке данных: {str(e)}",
                reply_markup=get_settings_keyboard()
            )
        
    except Exception as e:
        logger.error(
            "Error during data fetch",
            error=str(e),
            user_id=user_id
        )
        await status_message.edit_text(
            "❌ Произошла ошибка при загрузке данных. Попробуйте позже.",
            reply_markup=get_settings_keyboard()
        )
