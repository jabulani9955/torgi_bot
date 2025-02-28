import json
from typing import List, Dict, Any
from pathlib import Path


def load_subjects() -> List[Dict[str, Any]]:
    """Загружает список субъектов РФ"""
    with open(Path("const_filters/dynSubjRF.json"), "r", encoding="utf-8") as f:
        return json.load(f)


def load_statuses() -> List[Dict[str, Any]]:
    """Загружает список статусов"""
    with open(Path("const_filters/lotStatus.json"), "r", encoding="utf-8") as f:
        return json.load(f)
