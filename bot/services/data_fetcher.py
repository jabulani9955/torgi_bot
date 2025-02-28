from typing import List, Dict, Any, Tuple, Callable, Optional
from urllib.parse import urlencode
import aiohttp
import structlog
from math import ceil
import asyncio
import json


logger = structlog.get_logger()


async def fetch_page_data(
    session: aiohttp.ClientSession,
    base_url: str,
    subjects: List[str],
    statuses: List[str],
    page: int,
    size: int = 10
) -> Tuple[List[Dict[str, Any]], int]:
    """Получает данные одной страницы"""
    params = {
        "dynSubjRF": ",".join(subjects),
        "lotStatus": ",".join(statuses),
        "catCode": "2",
        "byFirstVersion": "true",
        "withFacets": "true",
        "size": str(size),
        "page": str(page),
        "sort": "firstVersionPublicationDate,desc"
    }
    
    full_url = f"{base_url}?{urlencode(params)}"
    logger.info(
        "Sending request",
        url=full_url,
        subjects=subjects,
        statuses=statuses,
        page=page
    )
    
    try:
        async with session.get(base_url, params=params) as response:
            response_data = await response.json()
            logger.debug(
                "Raw response received",
                status_code=response.status,
                response_data=response_data
            )
            
            if response.status != 200:
                logger.error(
                    "Failed to fetch data - bad status code",
                    subjects=subjects,
                    statuses=statuses,
                    page=page,
                    response_status=response.status,
                    url=full_url
                )
                return [], 0
                
            if not isinstance(response_data, dict):
                logger.error(
                    "Failed to fetch data - invalid response format",
                    subjects=subjects,
                    statuses=statuses,
                    page=page,
                    response_type=type(response_data),
                    url=full_url
                )
                return [], 0
                
            if "content" not in response_data:
                logger.error(
                    "Failed to fetch data - no content in response",
                    subjects=subjects,
                    statuses=statuses,
                    page=page,
                    response_keys=list(response_data.keys()),
                    url=full_url
                )
                return [], 0
                
            total_pages = response_data.get("totalPages", 1)
            items = response_data["content"]
            
            logger.info(
                "Data received successfully",
                subjects=subjects,
                statuses=statuses,
                page=page,
                items_count=len(items),
                total_pages=total_pages
            )
            return items, total_pages
            
    except aiohttp.ClientError as e:
        logger.error(
            "Network error while fetching data",
            subjects=subjects,
            statuses=statuses,
            page=page,
            error_type=type(e).__name__,
            error=str(e),
            url=full_url
        )
    except json.JSONDecodeError as e:
        logger.error(
            "Failed to parse JSON response",
            subjects=subjects,
            statuses=statuses,
            page=page,
            error_type=type(e).__name__,
            error=str(e),
            url=full_url
        )
    except Exception as e:
        logger.error(
            "Unexpected error while fetching data",
            subjects=subjects,
            statuses=statuses,
            page=page,
            error_type=type(e).__name__,
            error=str(e),
            url=full_url
        )
    return [], 0


async def fetch_data(
    subjects: List[str],
    statuses: List[str],
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> List[Dict[str, Any]]:
    """Получает данные с API torgi.gov.ru со всех страниц"""
    base_url = "https://torgi.gov.ru/new/api/public/lotcards/search"
    all_data = []
    
    async with aiohttp.ClientSession() as session:
        # Получаем первую страницу для определения общего количества страниц
        first_page_data, total_pages = await fetch_page_data(
            session, base_url, subjects, statuses, 0
        )
        all_data.extend(first_page_data)
        
        if progress_callback:
            await progress_callback(1, total_pages)
        
        # Получаем остальные страницы
        if total_pages > 1:
            logger.info(
                "Multiple pages detected",
                subjects=subjects,
                statuses=statuses,
                total_pages=total_pages
            )
            
            for page in range(1, total_pages):
                page_data, _ = await fetch_page_data(
                    session, base_url, subjects, statuses, page
                )
                all_data.extend(page_data)
                
                if progress_callback:
                    await progress_callback(page + 1, total_pages)
                
                # Добавляем небольшую задержку между запросами
                await asyncio.sleep(0.5)
    
    logger.info(
        "Total items collected",
        count=len(all_data),
        subjects_count=len(subjects),
        statuses_count=len(statuses),
        total_pages=total_pages
    )
    return all_data
