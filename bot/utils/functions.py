import os
import json
import logging
import re
import warnings
from datetime import datetime

import pandas as pd
import numpy as np
import requests
from pyproj import Transformer
from shapely.geometry import Polygon, MultiPolygon, Point
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
import time


warnings.filterwarnings('ignore')
load_dotenv()

logger = logging.getLogger(__name__)

# Глобальная сессия для запросов
_global_session = None


def get_optimized_session():
    """Возвращает оптимизированную сессию для HTTP-запросов"""
    global _global_session
    if _global_session is None:
        _global_session = requests.Session()
        _global_session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://nspd.gov.ru/",
            "Connection": "keep-alive"
        })
        
        # Оптимизация пула соединений
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=20,
            pool_maxsize=50,
            max_retries=2,
            pool_block=False
        )
        _global_session.mount('https://', adapter)
        
        # Инициализация сессии - запрос к главной странице
        try:
            _global_session.get("https://nspd.gov.ru/", verify=False, timeout=10)
        except Exception as e:
            logger.warning(f"Ошибка при инициализации сессии: {e}")
    
    return _global_session


def load_constants(path_to_const_data: str = 'const_filters') -> tuple:
    """Загружает константы из JSON-файлов"""
    try:
        # Subjects - используем новый файл с измененной структурой
        with open(os.path.join(path_to_const_data, 'dynSubRF_new.json'), encoding='utf-8') as f_sub:
            subjects_data_raw = json.load(f_sub)
            
        # Преобразуем данные в формат, совместимый с остальным кодом
        subjects_data = []
        for item in subjects_data_raw[0]['mappingTable']:
            subjects_data.append({
                "code": item["code"],
                "name": item["baseAttrValue"]["name"],
                "subjectRFCode": item["baseAttrValue"]["code"],  # Добавляем код для сопоставления с ответом API
                "railway_source": ""  # Добавляем пустое значение для совместимости
            })
        
        # Categories
        with open(os.path.join(path_to_const_data, 'catCode.json'), encoding='utf-8') as f_cat:
            categories_data = json.load(f_cat)

        # Statuses
        with open(os.path.join(path_to_const_data, 'lotStatus.json'), encoding='utf-8') as f_status:
            statuses_data = json.load(f_status)

        return subjects_data, categories_data, statuses_data
    except Exception as e:
        logger.error(f"Ошибка при загрузке констант: {e}")
        return [], []


def fill_cadastr_num(character, desc):
    pattern = r"\b\d{2}:\d{2}:\d{6,7}(?::\d{1,4})?(?::\d)?(?::[А-Яа-я\d]*)?\b"

    for char in character:
        if char.get('code') == 'CadastralNumber':
            cad_num = char.get('characteristicValue')
            if cad_num:
                return cad_num.strip() if cad_num != '-' else np.nan
            else:
                matches = re.findall(pattern, desc)
                return matches[0].strip() if matches else np.nan
            

def fill_area(character):
    for char in character:
        if char.get('code') == 'SquareZU':
            return char.get('characteristicValue')


def get_coords_from_cadastral_number(cad_num: str) -> tuple:
    """Получает координаты по кадастровому номеру"""
    if not cad_num or pd.isna(cad_num):
        return np.nan
        
    url = f"https://nspd.gov.ru/api/geoportal/v2/search/geoportal?query={cad_num}"
    
    try:
        # Используем оптимизированную сессию
        session = get_optimized_session()
        
        # Запрос к API с таймаутом
        response = session.get(url, verify=False, timeout=5)
        if response.status_code != 200:
            logger.error(f"Ошибка запроса для {cad_num}: статус {response.status_code}")
            return np.nan
        
        data_coordinates = response.json()
        
        if 'data' not in data_coordinates.keys():
            return np.nan
        
        data_features = next(df for df in data_coordinates['data'].get('features') if 'readable_address' in df.get('properties').get('options'))

        polygon_type = data_features.get('geometry').get('type')
        coords = data_features.get('geometry').get('coordinates')
        address = data_features.get('properties').get('options').get('readable_address')
        epsg = data_features.get('geometry').get('crs').get('properties').get('name')

        transformer = Transformer.from_crs(epsg, "EPSG:4326", always_xy=True)

        if polygon_type == 'Polygon':
            converted_coords = [transformer.transform(x, y) for x, y in coords[0]]
            polygon = Polygon(converted_coords)
        elif polygon_type == 'MultiPolygon':
            polygon = MultiPolygon([Polygon([transformer.transform(x, y) for coord_part in coords for ring in coord_part for x, y in ring])])
        elif polygon_type == 'Point':
            polygon = Point(transformer.transform(*coords))
        else:
            logger.error(f'Ошибка! Неизвестный тип полигона "{polygon_type}" с кадастровым номером {cad_num}.')
            return np.nan
        return ([polygon.centroid.x, polygon.centroid.y], address)
    except Exception as e:
        logger.error(f"Ошибка при получении координат ({cad_num}): {e}")
        return np.nan


def convert_time(dt_col, time_offset):
    try:
        if not pd.isnull(dt_col) and not pd.isnull(time_offset):
            dt = pd.to_datetime(dt_col) + pd.to_timedelta(int(time_offset), 'm')
            # Удаляем информацию о часовом поясе (делаем timezone-naive)
            return dt.tz_localize(None) if hasattr(dt, 'tz_localize') else dt
        else:
            dt = pd.to_datetime(dt_col)
            # Удаляем информацию о часовом поясе (делаем timezone-naive)
            return dt.tz_localize(None) if hasattr(dt, 'tz_localize') else dt
    except ValueError as e:
        logger.error(f'Ошибка в преобразовании времени: {e}') 
        dt = pd.to_datetime(dt_col)
        # Удаляем информацию о часовом поясе (делаем timezone-naive)
        return dt.tz_localize(None) if hasattr(dt, 'tz_localize') else dt


def fill_rent_period(attributes):
    for at in attributes:
        if at.get('code') == 'DA_contractDate_EA(ZK)':
            return at.get('value')


def get_additional_data(id):
    """Получает дополнительные данные о лоте по его ID"""
    if not id:
        return [np.nan] * 7
    
    try:
        # Используем оптимизированную сессию
        session = get_optimized_session()
        url = f"https://torgi.gov.ru/new/api/public/lotcards/{id}"
        
        # Запрос с таймаутом
        response = session.get(url, verify=False, timeout=5)
        response.raise_for_status()  # Проверка статуса ответа
        
        json_data = response.json()

        auction_start_date = json_data.get('auctionStartDate')
        bidd_start_date = json_data.get('biddStartTime')
        auction_link = json_data.get('etpUrl')
        price_step = json_data.get('priceStep')
        deposit_price = json_data.get('deposit')

        # Получаем разрешенное использование
        permitted_use = ', '.join([
            ch_v.get('name')
            for ch in json_data.get('characteristics', [])
            if ch.get('code') == 'PermittedUse'
            for ch_v in ch.get('characteristicValue', [])
            if ch_v and ch_v.get('name')
        ])

        attachments = json_data.get('lotAttachments', [])
        files = [(x.get('fileName', 'Файл'), f"https://torgi.gov.ru/new/file-store/v1/{x.get('fileId', '')}") 
                for x in attachments if x.get('fileId')]
                
        return auction_start_date, bidd_start_date, auction_link, price_step, deposit_price, files, permitted_use
    except requests.exceptions.RequestException as e:
        logger.error(f'Ошибка сетевого запроса для лота {id}: {e}')
        return [np.nan] * 7 
    except ValueError as e:
        logger.error(f'Ошибка обработки JSON для лота {id}: {e}')
        return [np.nan] * 7
    except Exception as e:
        logger.error(f'Непредвиденная ошибка в additional data для лота {id}: {e}')
        return [np.nan] * 7


def get_additional_data_batch(lot_ids, max_workers=10, retry_interval=1):
    """
    Получает дополнительные данные для нескольких лотов параллельно
    
    Args:
        lot_ids: Список ID лотов
        max_workers: Максимальное количество параллельных потоков
        retry_interval: Интервал в секундах между повторными попытками при ошибках
        
    Returns:
        dict: Словарь {id_лота: данные_лота}
    """
    logger.info(f"Получение дополнительных данных для {len(lot_ids)} лотов")
    start_time = time.time()
    
    results = {}
    failed_ids = []
    
    # Инициализируем сессию заранее
    get_optimized_session()
    
    # Функция для обработки в потоке
    def process_lot(lot_id):
        try:
            if not lot_id:
                return lot_id, [np.nan] * 7
                
            result = get_additional_data(lot_id)
            return lot_id, result
        except Exception as e:
            logger.error(f"Ошибка в потоке обработки лота {lot_id}: {e}")
            return lot_id, [np.nan] * 7
    
    # Запускаем параллельную обработку
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for lot_id, data in executor.map(process_lot, lot_ids):
            if all(pd.isna(x) if not isinstance(x, list) else False for x in data):
                failed_ids.append(lot_id)
            else:
                results[lot_id] = data
    
    # Повторяем для неудачных запросов с интервалом
    if failed_ids and retry_interval > 0:
        logger.info(f"Повторная попытка для {len(failed_ids)} неудачных запросов")
        time.sleep(retry_interval)
        
        with ThreadPoolExecutor(max_workers=max(3, max_workers//2)) as executor:
            for lot_id, data in executor.map(process_lot, failed_ids):
                results[lot_id] = data
    
    elapsed = time.time() - start_time
    success_rate = len(results) / len(lot_ids) * 100 if lot_ids else 0
    
    logger.info(f"Данные о лотах получены. Успешно: {len(results)}/{len(lot_ids)} ({success_rate:.1f}%). Время: {elapsed:.2f} сек.")
    
    return results


def get_coords_batch(cadastral_numbers, max_workers=5, retry_interval=2, rate_limit_delay=0.5):
    """
    Получает координаты для нескольких кадастровых номеров параллельно
    
    Args:
        cadastral_numbers: Список кадастровых номеров
        max_workers: Максимальное количество параллельных потоков
        retry_interval: Интервал в секундах между повторными попытками при ошибках
        rate_limit_delay: Задержка между запросами для предотвращения ошибки 429
        
    Returns:
        dict: Словарь {кадастровый_номер: координаты}
    """
    logger.info(f"Получение координат для {len(cadastral_numbers)} кадастровых номеров")
    start_time = time.time()
    
    results = {}
    failed_numbers = []
    
    # Инициализируем сессию заранее
    get_optimized_session()
    
    # Семафор для контроля одновременных запросов
    from threading import Semaphore
    request_semaphore = Semaphore(min(max_workers, 3))  # Ограничиваем до 3 одновременных запросов
    
    # Функция для обработки в потоке
    def process_cadastral(cad_num):
        try:
            if pd.isna(cad_num) or not cad_num:
                return cad_num, np.nan
            
            # Ограничиваем количество одновременных запросов
            with request_semaphore:
                # Добавляем задержку между запросами
                time.sleep(rate_limit_delay)
                
                url = f"https://nspd.gov.ru/api/geoportal/v2/search/geoportal?query={cad_num}"
                logger.debug(f"Запрашиваю координаты для: {cad_num}")
                
                # Используем оптимизированную сессию
                session = get_optimized_session()
                
                # Запрос к API с таймаутом
                response = session.get(url, verify=False, timeout=10)
                
                # Проверяем статус ответа
                if response.status_code == 429:
                    logger.warning(f"Ограничение запросов (429) для {cad_num}. Повторю позже.")
                    # Увеличиваем задержку при ограничении запросов
                    time.sleep(3)  # Более длительная пауза при ошибке 429
                    return cad_num, None  # Специальный маркер для повторной попытки
                
                if response.status_code != 200:
                    logger.error(f"Ошибка запроса для {cad_num}: статус {response.status_code}")
                    return cad_num, np.nan
                
                data_coordinates = response.json()
                
                if 'data' not in data_coordinates.keys():
                    return cad_num, np.nan
                
                if not data_coordinates['data'].get('features'):
                    logger.warning(f"Нет данных о координатах для {cad_num}")
                    return cad_num, np.nan
                
                data_features = next((df for df in data_coordinates['data'].get('features') 
                                    if 'readable_address' in df.get('properties', {}).get('options', {})), None)
                
                if not data_features:
                    logger.warning(f"Невозможно найти данные с адресом для {cad_num}")
                    return cad_num, np.nan

                polygon_type = data_features.get('geometry').get('type')
                coords = data_features.get('geometry').get('coordinates')
                address = data_features.get('properties').get('options').get('readable_address')
                epsg = data_features.get('geometry').get('crs').get('properties').get('name')

                transformer = Transformer.from_crs(epsg, "EPSG:4326", always_xy=True)

                if polygon_type == 'Polygon':
                    converted_coords = [transformer.transform(x, y) for x, y in coords[0]]
                    polygon = Polygon(converted_coords)
                elif polygon_type == 'MultiPolygon':
                    polygon = MultiPolygon([Polygon([transformer.transform(x, y) for coord_part in coords for ring in coord_part for x, y in ring])])
                elif polygon_type == 'Point':
                    polygon = Point(transformer.transform(*coords))
                else:
                    logger.error(f'Ошибка! Неизвестный тип полигона "{polygon_type}" с кадастровым номером {cad_num}.')
                    return cad_num, np.nan
                return cad_num, ([polygon.centroid.x, polygon.centroid.y], address)
                
        except Exception as e:
            logger.error(f"Ошибка в потоке обработки ({cad_num}): {e}")
            return cad_num, np.nan
    
    # Разбиваем запросы на группы для равномерной нагрузки
    batch_size = 20
    for i in range(0, len(cadastral_numbers), batch_size):
        batch = cadastral_numbers[i:i+batch_size]
        logger.info(f"Обработка группы {i//batch_size + 1} из {(len(cadastral_numbers) + batch_size - 1)//batch_size}")
        
        # Запускаем параллельную обработку для текущей группы
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for cad_num, coords in executor.map(process_cadastral, batch):
                if coords is None:  # Маркер для повторной попытки (429)
                    failed_numbers.append(cad_num)
                elif pd.isna(coords):
                    # Добавляем в список для повторной попытки только если не было явной 404 ошибки
                    failed_numbers.append(cad_num)
                else:
                    results[cad_num] = coords
        
        # Небольшая пауза между группами
        if i + batch_size < len(cadastral_numbers):
            time.sleep(2)
    
    # Повторяем для неудачных запросов с интервалом (с увеличенной задержкой)
    if failed_numbers:
        logger.info(f"Повторная попытка для {len(failed_numbers)} неудачных запросов")
        time.sleep(retry_interval * 2)  # Увеличиваем интервал для повторных попыток
        
        # Разбиваем неудачные запросы на еще меньшие группы
        retry_batch_size = 10
        for i in range(0, len(failed_numbers), retry_batch_size):
            retry_batch = failed_numbers[i:i+retry_batch_size]
            logger.info(f"Повторная обработка группы {i//retry_batch_size + 1} из {(len(failed_numbers) + retry_batch_size - 1)//retry_batch_size}")
            
            # Увеличиваем задержку для повторных попыток
            with ThreadPoolExecutor(max_workers=max(2, max_workers//2)) as executor:
                retry_processes = {}
                for cad_num in retry_batch:
                    # Добавляем дополнительную задержку между отправкой заданий
                    time.sleep(1)
                    retry_processes[executor.submit(process_cadastral, cad_num)] = cad_num
                
                for future in retry_processes:
                    cad_num = retry_processes[future]
                    try:
                        _, coords = future.result()
                        if coords is not None and not pd.isna(coords):
                            results[cad_num] = coords
                    except Exception as e:
                        logger.error(f"Ошибка при повторной попытке для {cad_num}: {e}")
            
            # Пауза между группами повторных попыток
            if i + retry_batch_size < len(failed_numbers):
                time.sleep(3)
    
    elapsed = time.time() - start_time
    success_rate = len(results) / len(cadastral_numbers) * 100 if cadastral_numbers else 0
    
    logger.info(f"Координаты получены. Успешно: {len(results)}/{len(cadastral_numbers)} ({success_rate:.1f}%). Время: {elapsed:.2f} сек.")
    
    return results
