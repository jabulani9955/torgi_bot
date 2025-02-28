import json
from typing import List, Dict, Any
from pathlib import Path
import os
import structlog

logger = structlog.get_logger()

def load_subjects() -> List[Dict[str, Any]]:
    """Загружает список субъектов РФ из нового формата файла"""
    try:
        with open(Path("const_filters/dynSubRF_new.json"), "r", encoding="utf-8") as f:
            subjects_data_raw = json.load(f)
            
        # Преобразуем данные в формат, совместимый с остальным кодом
        subjects_data = []
        for item in subjects_data_raw[0]['mappingTable']:
            subjects_data.append({
                "code": item["code"],
                "name": item["baseAttrValue"]["name"],
                "subjectRFCode": item["baseAttrValue"]["code"],
                "railway_source": ""  # Добавляем пустое значение для совместимости
            })
        return subjects_data
    except Exception as e:
        logger.error(f"Ошибка при загрузке субъектов: {e}")
        return []


def load_statuses() -> List[Dict[str, Any]]:
    """Загружает список статусов"""
    with open(Path("const_filters/lotStatus.json"), "r", encoding="utf-8") as f:
        return json.load(f)
