import os
import datetime
import logging
from typing import List, Dict, Any, Optional

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from bot.utils.functions import (
    fill_cadastr_num, 
    fill_area,
    get_coords_from_cadastral_number, 
    collect_data,
    load_constants,
    convert_time,
    fill_rent_period,
    get_additional_data
)


logger = logging.getLogger(__name__)


def format_excel(df: pd.DataFrame, filename: str) -> None:
    """Форматирует Excel файл для лучшей читаемости"""
    # Создаем Excel файл
    writer = pd.ExcelWriter(filename, engine='openpyxl')
    df.to_excel(writer, index=False, sheet_name='Данные')
    
    # Получаем рабочую книгу и лист
    workbook = writer.book
    worksheet = writer.sheets['Данные']
    
    # Определяем стили
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    centered_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    border = Border(
        left=Side(style='thin'), 
        right=Side(style='thin'), 
        top=Side(style='thin'), 
        bottom=Side(style='thin')
    )
    
    # Форматируем заголовки
    for col_num, column in enumerate(df.columns, 1):
        cell = worksheet.cell(row=1, column=col_num)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = centered_alignment
        cell.border = border
        
        # Устанавливаем ширину колонки
        column_width = max(len(str(column)), 15)  # Минимальная ширина 15
        worksheet.column_dimensions[get_column_letter(col_num)].width = column_width
    
    # Форматируем данные
    for row_num in range(2, len(df) + 2):
        for col_num in range(1, len(df.columns) + 1):
            cell = worksheet.cell(row=row_num, column=col_num)
            cell.alignment = Alignment(vertical='center', wrap_text=True)
            cell.border = border
    
    # Автоматическая настройка ширины колонок
    for col in worksheet.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            if cell.row == 1:  # Пропускаем заголовок
                continue
            try:
                if len(str(cell.value)) > max_length:
                    max_length = min(len(str(cell.value)), 50)  # Ограничиваем максимальную ширину
            except:
                pass
        adjusted_width = max(max_length + 2, 15)
        worksheet.column_dimensions[column].width = adjusted_width
    
    # Закрепляем заголовок
    worksheet.freeze_panes = 'A2'
    
    # Сохраняем файл
    writer.close()
    logger.info(f"Excel файл отформатирован и сохранен: {filename}")


def prepare_data_for_excel(df: pd.DataFrame) -> pd.DataFrame:
    """Подготавливает данные для Excel файла"""
    # Выбираем и переименовываем нужные колонки
    columns_mapping = {
        'lotName': 'Наименование',
        'lotDescription': 'Описание',
        'category': 'Категория',
        'biddType': 'Тип торгов',
        'biddForm': 'Форма торгов',
        'subject': 'Субъект РФ',
        'address': 'Адрес',
        'cadastral_number': 'Кадастровый номер',
        'area': 'Площадь (кв.м)',
        'priceMin': 'Начальная цена (руб)',
        'deposit': 'Задаток (руб)',
        'priceStep': 'Шаг аукциона (руб)',
        'rent_period': 'Срок аренды',
        'biddEndTime': 'Дата окончания приема заявок',
        'auction_start_date': 'Дата проведения аукциона',
        'lotStatus': 'Статус',
        'link': 'Ссылка на лот',
        'auction_link': 'Ссылка на аукцион',
        'lotImages': 'Изображения',
        'files': 'Документы'
    }
    
    # Создаем новый DataFrame с нужными колонками
    result_df = pd.DataFrame()
    
    for new_col, old_col in columns_mapping.items():
        if new_col in df.columns:
            result_df[old_col] = df[new_col]
    
    # Форматируем даты
    date_columns = ['Дата окончания приема заявок', 'Дата проведения аукциона']
    for col in date_columns:
        if col in result_df.columns:
            result_df[col] = pd.to_datetime(result_df[col]).dt.strftime('%d.%m.%Y %H:%M')
    
    # Форматируем числовые значения
    numeric_columns = ['Начальная цена (руб)', 'Задаток (руб)', 'Шаг аукциона (руб)']
    for col in numeric_columns:
        if col in result_df.columns:
            result_df[col] = result_df[col].apply(lambda x: f"{x:,.2f}".replace(',', ' ') if pd.notnull(x) else '')
    
    # Форматируем ссылки на документы
    if 'files' in df.columns:
        result_df['Документы'] = df['files'].apply(
            lambda x: '\n'.join([f"{name}: {url}" for name, url in x]) if isinstance(x, list) else ''
        )
    
    return result_df


def data_processing(data: List[Dict[Any, Any]], selected_subjects: List[str], selected_statuses: List[str]) -> str:
    """Обрабатывает данные и создает Excel файл"""
    logger.info("Начинаю обработку данных...")
    
    # Загружаем константы
    subjects_data, _ = load_constants()
    
    # Создаем DataFrame из полученных данных
    df = pd.DataFrame(data)
    
    if df.empty:
        logger.error("Нет данных для обработки")
        return None
    
    # Добавляем информацию о субъекте
    df['subject'] = df['subjectRFCode'].apply(
        lambda x: next((sub['name'] for sub in subjects_data if sub['subjectRFCode'] == str(x)), "Неизвестный субъект")
    )
    
    # Обрабатываем данные
    logger.info("Обрабатываю данные...")
    
    # Преобразуем типы данных
    if 'biddType' in df.columns:
        df['biddType'] = df['biddType'].apply(lambda x: x['name'] if isinstance(x, dict) and 'name' in x else str(x))
    
    if 'biddForm' in df.columns:
        df['biddForm'] = df['biddForm'].apply(lambda x: x['name'] if isinstance(x, dict) and 'name' in x else str(x))
    
    if 'category' in df.columns:
        df['category'] = df['category'].apply(lambda x: x['name'] if isinstance(x, dict) and 'name' in x else str(x))
    
    if 'lotStatus' in df.columns:
        df['lotStatus'] = df['lotStatus'].apply(lambda x: x['name'] if isinstance(x, dict) and 'name' in x else str(x))
    
    # Добавляем дополнительные данные
    df['area'] = df['characteristics'].apply(fill_area)
    df['cadastral_number'] = df.apply(lambda x: fill_cadastr_num(x['characteristics'], x['lotDescription']), axis=1)
    df['rent_period'] = df['attributes'].apply(fill_rent_period)
    
    # Добавляем ссылки
    df['link'] = df['id'].apply(lambda x: f'https://torgi.gov.ru/new/public/lots/lot/{x}')
    
    if 'lotImages' in df.columns:
        df['lotImages'] = df['lotImages'].apply(
            lambda x: ', '.join([f'https://torgi.gov.ru/new/file-store/v1/{i}?disposition=inline' for i in x]) 
            if isinstance(x, list) else ''
        )
    
    logger.info('Получаю координаты из кадастровых номеров...')
    df['rosreestr_info'] = df['cadastral_number'].apply(lambda x: get_coords_from_cadastral_number(x) if pd.notnull(x) else np.nan)
    
    # Фильтруем записи с координатами
    df = df.dropna(subset=['rosreestr_info'])
    
    # Извлекаем координаты и адрес
    df['coords_center'] = df['rosreestr_info'].apply(lambda x: x[0] if isinstance(x, tuple) and len(x) > 0 else np.nan)
    df['address'] = df['rosreestr_info'].apply(lambda x: x[1] if isinstance(x, tuple) and len(x) > 1 else np.nan)
    
    logger.info('Получаю дополнительную информацию о лотах...')
    df['additional_info'] = df['id'].apply(get_additional_data)
    
    # Извлекаем дополнительную информацию
    df['auction_start_date'] = df['additional_info'].apply(lambda x: x[0] if isinstance(x, (list, tuple)) and len(x) > 0 else np.nan)
    df['bidd_start_date'] = df['additional_info'].apply(lambda x: x[1] if isinstance(x, (list, tuple)) and len(x) > 1 else np.nan)
    df['auction_link'] = df['additional_info'].apply(lambda x: x[2] if isinstance(x, (list, tuple)) and len(x) > 2 else np.nan)
    df['priceMin'] = df['additional_info'].apply(lambda x: x[3] if isinstance(x, (list, tuple)) and len(x) > 3 else np.nan)
    df['priceFin'] = df['additional_info'].apply(lambda x: x[4] if isinstance(x, (list, tuple)) and len(x) > 4 else np.nan)
    df['priceStep'] = df['additional_info'].apply(lambda x: x[5] if isinstance(x, (list, tuple)) and len(x) > 5 else np.nan)
    df['deposit'] = df['additional_info'].apply(lambda x: x[6] if isinstance(x, (list, tuple)) and len(x) > 6 else np.nan)
    df['files'] = df['additional_info'].apply(lambda x: x[7] if isinstance(x, (list, tuple)) and len(x) > 7 else [])
    
    # Преобразуем даты с учетом часового пояса
    try:
        df['biddEndTime'] = df.apply(lambda x: convert_time(x['biddEndTime'], x['timezoneOffset']), axis=1)
        df['createDate'] = df.apply(lambda x: convert_time(x['createDate'], x['timezoneOffset']), axis=1)
        df['auction_start_date'] = df.apply(lambda x: convert_time(x['auction_start_date'], x['timezoneOffset']), axis=1)
        df['bidd_start_date'] = df.apply(lambda x: convert_time(x['bidd_start_date'], x['timezoneOffset']), axis=1)
    except Exception as e:
        logger.error(f'Ошибка в преобразовании времени: {e}')
    
    # Удаляем ненужные колонки
    columns_to_drop = ['characteristics', 'attributes', 'subjectRFCode', 'additional_info', 'rosreestr_info']
    df = df.drop(columns=[col for col in columns_to_drop if col in df.columns]).reset_index(drop=True)
    
    # Подготавливаем данные для Excel
    excel_df = prepare_data_for_excel(df)
    
    # Создаем директорию для результатов, если она не существует
    results_path = os.path.join('data', 'results')
    os.makedirs(results_path, exist_ok=True)
    
    # Формируем имя файла
    time_now = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Получаем названия субъектов
    subject_names = []
    for subject_code in selected_subjects:
        subject_name = next((sub['name'] for sub in subjects_data if sub['code'] == subject_code), None)
        if subject_name:
            subject_names.append(subject_name.replace(" ", "_"))
    
    # Формируем имя файла
    subjects_str = "-".join(subject_names) if len(subject_names) <= 2 else f"{len(subject_names)}_субъектов"
    statuses_str = "-".join(selected_statuses) if len(selected_statuses) <= 2 else f"{len(selected_statuses)}_статусов"
    filename = f"TORGI_{subjects_str}_{statuses_str}_{time_now}.xlsx"
    fullpath = os.path.join(results_path, filename)
    
    # Сохраняем и форматируем Excel файл
    format_excel(excel_df, fullpath)
    
    logger.info(f"Данные успешно обработаны и сохранены в файл: {fullpath}")
    return fullpath
