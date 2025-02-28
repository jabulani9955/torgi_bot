from typing import List, Dict, Any, Tuple, Callable, Optional
from urllib.parse import urlencode
import aiohttp
import structlog
from math import ceil
import asyncio
import json
import os


logger = structlog.get_logger()


async def fetch_page_data(
    session: aiohttp.ClientSession,
    subjects: List[str],
    statuses: List[str],
    page: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> Dict[str, Any]:
    """Получает данные с одной страницы API"""
    url = "https://torgi.gov.ru/new/api/public/lotcards/search"
    
    # Формируем параметры запроса
    # Объединяем субъекты и статусы через запятую
    subjects_str = ",".join(subjects)
    statuses_str = ",".join(statuses)
    
    params = {
        "dynSubjRF": subjects_str,
        "lotStatus": statuses_str,
        "catCode": 2,
        "page": page,
        "size": 10,
        "sort": "firstVersionPublicationDate,desc"
    }
    
    # Добавляем параметры даты, если они указаны
    if date_from:
        params["aucStartFrom"] = date_from
    if date_to:
        params["aucStartTo"] = date_to
    
    # Формируем полный URL с параметрами для логирования
    full_url = f"{url}?{urlencode(params, doseq=True)}"
    logger.info(f"Fetching data from URL: {full_url}")
    
    try:
        # Используем GET запрос вместо POST и передаем параметры через params
        async with session.get(url, params=params) as response:
            if response.status != 200:
                logger.error(
                    "API request failed",
                    status=response.status,
                    url=full_url,
                    page=page
                )
                return {}
            
            data = await response.json()
            return data
    except Exception as e:
        logger.error(
            "Error fetching data",
            error=str(e),
            url=full_url,
            page=page
        )
        return {}


async def fetch_data(
    subjects: List[str],
    statuses: List[str],
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> List[Dict[str, Any]]:
    """Получает данные со всех страниц API"""
    all_data = []
    
    # Логируем информацию о запросе
    logger.info(
        "Starting data fetch",
        subjects=subjects,
        statuses=statuses,
        date_from=date_from,
        date_to=date_to
    )
    
    # Формируем базовый URL для логирования
    base_url = "https://torgi.gov.ru/new/api/public/lotcards/search"
    
    # Объединяем субъекты и статусы через запятую
    subjects_str = ",".join(subjects)
    statuses_str = ",".join(statuses)
    
    base_params = {
        "dynSubjRF": subjects_str,
        "lotStatus": statuses_str,
        "size": 20,
        "sort": "firstVersionPublicationDate,desc"
    }
    
    if date_from:
        base_params["aucStartFrom"] = date_from
    if date_to:
        base_params["aucStartTo"] = date_to
    
    base_url_with_params = f"{base_url}?{urlencode(base_params, doseq=True)}"
    logger.info(f"Base URL for all requests: {base_url_with_params}")
    
    async with aiohttp.ClientSession() as session:
        # Получаем первую страницу для определения общего количества
        first_page = await fetch_page_data(session, subjects, statuses, 0, date_from, date_to)
        
        if not first_page:
            logger.error("Failed to fetch first page")
            return []
        
        total_pages = first_page.get("totalPages", 0)
        logger.info(f"Total pages: {total_pages}")
        
        if total_pages == 0:
            logger.info("No data found")
            return []
        
        # Добавляем данные с первой страницы
        all_data.extend(first_page.get("content", []))
        
        # Если есть callback для прогресса, вызываем его
        if progress_callback:
            await progress_callback(1, total_pages)
        
        # Получаем остальные страницы
        tasks = []
        for page in range(1, total_pages):
            tasks.append(fetch_page_data(session, subjects, statuses, page, date_from, date_to))
            
            # Ограничиваем количество одновременных запросов
            if len(tasks) >= 5 or page == total_pages - 1:
                results = await asyncio.gather(*tasks)
                for i, result in enumerate(results):
                    if result:
                        all_data.extend(result.get("content", []))
                    
                    # Обновляем прогресс
                    if progress_callback:
                        current_page = 1 + page - len(tasks) + i + 1
                        await progress_callback(current_page, total_pages)
                
                tasks = []
                # Небольшая пауза, чтобы не перегружать сервер
                await asyncio.sleep(0.5)
    
    logger.info(f"Fetched {len(all_data)} items")
    return all_data
