import json
from typing import List, Dict, Any
from pathlib import Path


def load_subjects() -> List[Dict[str, Any]]:
    """Загружает список субъектов РФ"""
    with open(Path("const_filters/dynSubRF_new.json"), "r", encoding="utf-8") as f:
        data = json.load(f)
        
    # Преобразуем данные в формат, совместимый с остальным кодом
    subjects = []
    for item in data[0]['mappingTable']:
        subjects.append({
            "code": item["code"],
            "name": item["baseAttrValue"]["name"],
            "subjectRFCode": item["baseAttrValue"]["code"]
        })
    
    return subjects


def load_statuses() -> List[Dict[str, Any]]:
    """Загружает список статусов"""
    with open(Path("const_filters/lotStatus.json"), "r", encoding="utf-8") as f:
        return json.load(f)
