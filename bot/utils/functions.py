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


warnings.filterwarnings('ignore')
load_dotenv()

logger = logging.getLogger(__name__)


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

        return subjects_data, categories_data
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
    url = f"https://nspd.gov.ru/api/geoportal/v2/search/geoportal?query={cad_num}"
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://nspd.gov.ru/",
            "Connection": "keep-alive"
        }
        session = requests.Session()
        session.headers.update(headers)
        
        # Предварительный запрос к главной странице для получения cookies
        homepage_response = session.get("https://nspd.gov.ru/", verify=False)
        logger.info(f"Главная страница: статус {homepage_response.status_code}")
        
        # Теперь запрос к API
        response = session.get(url, verify=False)
        if response.status_code != 200:
            logger.error(f"Ошибка запроса: статус {response.status_code}. Текст ответа: {response.text}")
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
            return pd.to_datetime(dt_col) + pd.to_timedelta(int(time_offset), 'm')
        else:
            return pd.to_datetime(dt_col)
    except ValueError as e:
        logger.error(f'Ошибка в преобразовании времени: {e}') 
        return pd.to_datetime(dt_col)


def fill_rent_period(attributes):
    for at in attributes:
        if at.get('code') == 'DA_contractDate_EA(ZK)':
            return at.get('value')


def get_additional_data(id):
    try:
        url = f"https://torgi.gov.ru/new/api/public/lotcards/{id}"
        response = requests.get(url, verify=False)
        json_data = response.json()

        auction_start_date = json_data.get('auctionStartDate')
        bidd_start_date = json_data.get('biddStartTime')
        auction_link = json_data.get('etpUrl')
        price_min = json_data.get('priceMin')
        price_fin = json_data.get('priceFin')
        price_step = json_data.get('priceStep')
        deposit_price = json_data.get('deposit')

        attachmets = json_data.get('lotAttachments')
        files = [(x['fileName'], 'https://torgi.gov.ru/new/file-store/v1/'+x['fileId']) for x in attachmets]
        return auction_start_date, bidd_start_date, auction_link, price_min, price_fin, price_step, deposit_price, files
    except Exception as e:
        logger.error(f'Error in additional data!\n{e}')
        return [np.nan] * 8
