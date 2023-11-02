import logging
import re
import time
import ast
from random import randint

import pandas as pd
import numpy as np
import requests
import psycopg2
from rosreestr2coord import Area
from shapely import wkb
from shapely.geometry import Polygon, Point


MAPBOX_REQUESTS_NUM = 1


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


def get_values_from_rosreestr(cadastral_number: str) -> list:
    try:
        logging.basicConfig(filename='data/rosreestr.log', level=logging.DEBUG)
        logger = logging.getLogger(__name__)
        
        area = Area(
            code=cadastral_number,
            with_proxy=True,
            use_cache=True,
            with_log=False,
            media_path='data',
            logger=logger
        )
        coords = list(map(tuple, area.get_coord()[0][0]))
        coords_center = area.get_center_xy()[0][0][0]
        address = area.get_attrs()['address']
        return [coords, coords_center, address]
    except Exception as e:
        logger.critical(e, exc_info=True)


def get_mapbox_isochrones(coords_center: list, coords: list, minutes: int = 30) -> Polygon: 
    global MAPBOX_REQUESTS_NUM

    if not coords_center:
        return np.nan
    
    if MAPBOX_REQUESTS_NUM == 300:
        print('Достигли 300 запросов в минуту.\Ждём 1 минуту...')
        time.sleep(60 + randint(3, 7))

    try:
        coords_center = ast.literal_eval(coords_center) if isinstance(coords_center, str) else coords_center
        coords = ast.literal_eval(coords) if isinstance(coords, str) else coords
    
        with psycopg2.connect(host='localhost', dbname="postgres", user="postgres", password="admin") as conn:
            with conn.cursor() as cur:
                select_query = "SELECT distance_polygon FROM address_coords WHERE address_point = %s"
                cur.execute(select_query, (wkb.dumps(Point(coords_center), hex=True, srid=4326),))
                result = cur.fetchone()
                if result:
                    return wkb.loads(result[0])
                else:
                    # Убрать токен в переменные окружения!!
                    mapbox_token = "pk.eyJ1IjoiamFidWxhbmk5OTU1IiwiYSI6ImNrejJnaDV0ZTAwZDIyd3FmcmVoejR5bGUifQ.HtEP4kt_8ji1VbaumpXVZg"
                    profile = "mapbox/walking" # driving-traffic, driving, cycling
                    mapbox_iso_url = rf"https://api.mapbox.com/isochrone/v1/{profile}/{coords_center[0]},{coords_center[1]}?contours_minutes={minutes}&polygons=true&access_token={mapbox_token}"
                    response = requests.get(mapbox_iso_url)

                    if response.status_code != 200:
                        return np.nan
                    
                    MAPBOX_REQUESTS_NUM += 1
                    
                    isochrone_data = response.json()                    
                    if 'features' in isochrone_data:
                        distance_polygon = Polygon(map(tuple, isochrone_data['features'][0]['geometry']['coordinates'][0]))
                        insert_query = '''
                            INSERT INTO address_coords (
                                address_point, 
                                address_polygon, 
                                distance_polygon
                            ) VALUES(
                                %s,
                                %s,
                                %s
                            );
                        '''
                        cur.execute(
                            insert_query, 
                            (
                                wkb.dumps(Point(coords_center), hex=True, srid=4326),
                                wkb.dumps(Polygon(coords), hex=True, srid=4326),
                                wkb.dumps(distance_polygon, hex=True, srid=4326)
                            )
                        )
                        conn.commit()
                        return distance_polygon
                    else:
                        return np.nan 
    except Exception as e:
        print(f'Error: {str(e).capitalize()}')


def is_railway_near(isochrone_coords, df):
    if pd.isnull(isochrone_coords):
        return np.nan
    
    polygon = Polygon(isochrone_coords)

    railway_df = df.copy()
    railway_df['point'] = railway_df.apply(lambda x: Point(x['lon'], x['lat']), axis=1)
    return any([polygon.contains(point) for point in railway_df['point'].to_list()])
