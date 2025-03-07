from typing import List, Dict, Any, Tuple, Callable, Optional, Awaitable, Union
from urllib.parse import urlencode
import aiohttp
import structlog
from math import ceil
import asyncio
import json
import os
import time


logger = structlog.get_logger()


async def fetch_page_data(
    subjects: List[str],
    statuses: Union[List[str], str],
    page: int,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Получает данные с одной страницы API
    
    Args:
        subjects: Список выбранных субъектов
        statuses: Статус(ы) лотов (строка или список строк)
        page: Номер страницы (начинается с 0)
        date_from: Начальная дата (опционально)
        date_to: Конечная дата (опционально)
        
    Returns:
        Dict[str, Any]: Данные с одной страницы
    """
    # Объединяем субъекты через запятую
    subjects_str = ",".join(subjects)
    
    # Преобразуем статусы в строку, если это список
    if isinstance(statuses, list):
        statuses_str = ",".join(statuses)
    else:
        statuses_str = statuses
    
    # Формируем параметры запроса
    params = {
        "dynSubjRF": subjects_str,
        "lotStatus": statuses_str,
        "catCode": "2",  # Код категории (2 - Земельные участки)
        "page": page,
        "size": 10,  # Размер страницы
        "sort": "firstVersionPublicationDate,desc"  # Сортировка по дате публикации
    }
    
    # Добавляем фильтры по датам, если они указаны
    if date_from:
        params["aucStartFrom"] = date_from
    if date_to:
        params["aucStartTo"] = date_to
    
    # Формируем URL
    url = f"https://torgi.gov.ru/new/api/public/lotcards/search?{urlencode(params, doseq=True)}"
    logger.info(f"Fetching data from URL: {url}")
    
    try:
        # Выполняем запрос
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=60) as response:
                if response.status != 200:
                    logger.error(f"Error fetching page {page}: {response.status}")
                    return None
                
                # Парсим JSON
                response_json = await response.json()
                return response_json
                
    except aiohttp.ClientError as e:
        logger.error(f"Network error while fetching page {page}: {e}")
        return None
    except asyncio.TimeoutError:
        logger.error(f"Timeout while fetching page {page}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error while fetching page {page}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unknown error while fetching page {page}: {e}")
        return None


async def fetch_data(
    selected_subjects: List[str],
    selected_statuses: List[str],
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    progress_callback: Optional[Callable[[int, int], Awaitable[None]]] = None
) -> Optional[List[Dict[str, Any]]]:
    """
    Получает данные с сервера по выбранным параметрам
    
    Args:
        selected_subjects: Список выбранных субъектов
        selected_statuses: Список выбранных статусов
        date_from: Начальная дата (опционально)
        date_to: Конечная дата (опционально)
        progress_callback: Коллбэк-функция для обновления прогресса
        
    Returns:
        List[Dict[str, Any]]: Список данных
    """
    # Проверяем входные данные
    if not selected_subjects or not selected_statuses:
        logger.error("No subjects or statuses provided")
        return None
    
    all_data = []
    
    try:
        # Словарь для хранения общего прогресса
        overall_progress = {"current": 0, "total": 0, "last_callback": 0}
        
        # Обрабатываем все статусы вместе для совместимости
        # Получаем первую страницу для определения общего количества страниц
        first_page = await fetch_page_data(selected_subjects, selected_statuses, 0, date_from, date_to)
        
        if not first_page or 'content' not in first_page:
            logger.warning(f"No data found for selected statuses")
            return None
            
        total_elements = first_page.get('totalElements', 0)
        
        if total_elements == 0:
            logger.warning(f"No elements found for selected statuses")
            return None
            
        # Добавляем данные с первой страницы
        all_data.extend(first_page['content'])
        
        # Вычисляем общее количество страниц
        page_size = 10
        total_pages = (total_elements + page_size - 1) // page_size
        
        # Обновляем счетчик общего прогресса
        overall_progress["total"] = total_pages
        overall_progress["current"] = 1
        
        # Обновляем прогресс для первой страницы
        current_time = time.time()
        if progress_callback:
            await progress_callback(overall_progress["current"], overall_progress["total"])
            overall_progress["last_callback"] = current_time
        
        # Загружаем остальные страницы
        tasks = []
        for page in range(1, total_pages):
            tasks.append(fetch_page_data(selected_subjects, selected_statuses, page, date_from, date_to))
            
            # Ограничиваем количество одновременных запросов
            if len(tasks) >= 5 or page == total_pages - 1:
                # Дожидаемся выполнения всех запросов
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Обрабатываем результаты
                for result in results:
                    if isinstance(result, Exception):
                        logger.error(f"Error while fetching page data: {result}")
                        continue
                        
                    if result and 'content' in result:
                        all_data.extend(result['content'])
                        
                    # Увеличиваем счетчик прогресса
                    overall_progress["current"] += 1
                
                # Обновляем прогресс только изредка (каждые 2 секунды или каждую 20-ю страницу)
                current_time = time.time()
                if progress_callback and (current_time - overall_progress["last_callback"] >= 2 or 
                                         overall_progress["current"] % 20 == 0 or
                                         overall_progress["current"] >= overall_progress["total"]):
                    await progress_callback(min(overall_progress["current"], overall_progress["total"]), 
                                          overall_progress["total"])
                    overall_progress["last_callback"] = current_time
                
                # Сбрасываем список задач
                tasks = []
        
        # Финальное обновление прогресса
        if progress_callback:
            await progress_callback(overall_progress["total"], overall_progress["total"])
            
        logger.info(f"Fetched {len(all_data)} items")
        return all_data
        
    except Exception as e:
        logger.error(f"Error while fetching data: {e}")
        return None
