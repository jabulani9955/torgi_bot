import os
import json
import logging
import re
import time
import ast
from random import randint
from datetime import datetime
import warnings

import folium
import pandas as pd
import numpy as np
import geopandas as gpd
import requests
import psycopg2
from folium.plugins import MarkerCluster, GroupedLayerControl
from rosreestr2coord import Area
from shapely import wkb
from shapely.geometry import Polygon, Point
from dotenv import load_dotenv
from bs4 import BeautifulSoup


warnings.filterwarnings('ignore')
load_dotenv()

logger = logging.getLogger(__name__)
MAPBOX_REQUESTS_NUM = 1


def load_constants(path_to_const_data: str = 'data/const_filters') -> tuple:
    """ Description. """

    # Subjects
    with open(os.path.join(path_to_const_data, 'dynSubjRF.json') , encoding='utf-8') as f_sub:
        subjects_data = json.load(f_sub)
    
    # Categories
    with open(os.path.join(path_to_const_data, 'catCode.json'), encoding='utf-8') as f_cat:
        categories_data = json.load(f_cat)

    # SubjectsRF
    with open(os.path.join(path_to_const_data, 'subject.json'), encoding='utf-8') as f_subrf:
        subjectsrf_data = json.load(f_subrf)

    return subjects_data, categories_data, subjectsrf_data


def collect_data(
    subject: str,
    subjects_data: list,
    categories_data: list,
    category: str = 'Земельные участки',
    status: list = ['APPLICATIONS_SUBMISSION', 'PUBLISHED'],
    search_text: str = None,
) -> str:
    """ Description. """

    time_now = datetime.now().strftime('%Y%m%d_%H%M%S')
    BASE_URL = 'https://torgi.gov.ru/new/api/public/lotcards/search'
    url_params = {
        'size': 100,
        'sort': 'firstVersionPublicationDate,desc',
        'page': 0
    }

    logger.info('Начинаю собирать данные...')
    logger.info(f'\t\tСубъект: "{subject}"')
    subject_code = [sub.get('code') for sub in subjects_data if sub.get('name') == subject][0]
    url_params['dynSubjRF'] = subject_code
    
    if search_text:
        url_params['text'] = search_text

    if status:
        url_params['lotStatus'] = status

    if category:
        logger.info(f'\t\tКатегория: "{category}"')

        cat_code = [cat.get('code') for cat in categories_data if cat.get('name') == category][0]
        url_params['catCode'] = cat_code
    
    
    full_json_data = []
    response = requests.get(BASE_URL, params=url_params)

    if response.status_code != 200:
        logger.error(f'Код {response.status_code}.')
        print(f'Код {response.status_code}.')
        return None
    
    try:
        json_data = response.json()    
    except Exception:
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'lxml')
        return [i.text.strip() for i in soup.find_all("div", {"class": "message-text"})]
    
    num_pages = json_data['totalPages']
    if num_pages == 0:
        return None
        
    logger.info(f"Получена страница 1/{num_pages} сайта torgi.gov.ru")

    full_json_data.append(json_data)
    for page_num in range(1, num_pages):
        url_params['page'] = page_num
        full_json_data.append(requests.get(BASE_URL, params=url_params).json())
        logger.info(f"Получена страница {page_num+1}/{num_pages} сайта torgi.gov.ru")

    filepath = f'data/torgi_json_files'
    filename = f"TORGI_{subject.replace(' ', '_')}_{time_now}.json"
    
    if not os.path.exists(filepath):
        os.makedirs(filepath)

    with open(os.path.join(filepath, filename), 'w', encoding='utf-8') as f:
        json.dump(full_json_data, f, indent=4, ensure_ascii=False)

    logger.info(f"JSON-файл с информацией о лотах сохранён по адресу: {os.path.join(filepath, filename)}")
    return os.path.join(filepath, filename)


def loading_railways(railway_source: str) -> pd.DataFrame:
    esr_df = pd.read_csv('data/const_filters/railways/esr.csv', sep=';')
    osm2esr_df = pd.read_csv('data/const_filters/railways/osm2esr.csv', sep=';')
    
    railway_stations = esr_df[esr_df['source'] == railway_source][['region', 'type', 'esr']].merge(
        osm2esr_df[osm2esr_df['status'] != 0].drop(columns=['status', 'type', 'railway', 'alt_name', 'old_name', 'official_name', 'user']),
        how='left',
        on='esr'
    ).drop(columns=['esr']).dropna(subset=['lat', 'lon']).sort_values(by=['name']).reset_index(drop=True)[[
        'name', 'region', 'type', 'osm_id', 'lat', 'lon'
    ]]
    railway_stations.osm_id = railway_stations.osm_id.apply(lambda x: str(x).split('.')[0])
    return railway_stations


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


def get_coords_from_rosreestr(cad_num: str, center_only: bool = True):
    try:
        area = Area(
            code=cad_num,
            with_log=False,
            center_only=center_only,
            media_path='data'
        )

        if not area.get_center_xy():
            return np.nan
        
        coords_center = area.get_center_xy()[0][0][0]
        coords = list(map(tuple, area.get_coord()[0][0]))
        address = area.get_attrs().get('address')   

        if center_only:
            result = (coords_center, address)
        else:
            result = (coords, coords_center, address) 

        return result
    except Exception as e:
        logger.error(f"Error: {e}. Кадастровый номер: {cad_num}")
        return np.nan


def get_mapbox_isochrones(coords_center: list, minutes: int = 30, debug=False) -> Polygon: 
    global MAPBOX_REQUESTS_NUM

    if not coords_center:
        return np.nan
    
    if MAPBOX_REQUESTS_NUM == 300:
        print('Достигли 300 запросов в минуту. Ждём 1 минуту...')
        time.sleep(60 + randint(3, 7))
        
    geometry_coords_center = wkb.dumps(Point(coords_center), hex=True, srid=4326)

    pg_host = 'localhost' if debug else os.getenv('PG_HOST')
    pg_user = 'postgres' if debug else os.getenv('PG_USER')
    pg_password = 'admin' if debug else os.getenv('PG_PASSWORD')
    pg_db = 'postgres' if debug else os.getenv('PG_DB')
    pg_port = '5432' if debug else os.getenv('PG_PORT')

    try:
        with psycopg2.connect(
            host=pg_host,
            user=pg_user, 
            password=pg_password,
            dbname=pg_db, 
            port=pg_port
        ) as conn:
            with conn.cursor() as cur:
                select_query = "SELECT distance_polygon FROM isochrones_info WHERE address_point = %s"
                cur.execute(select_query, (geometry_coords_center,))
                result = cur.fetchone()
                if result:
                    return wkb.loads(result[0])
                else:
                    mapbox_token = os.getenv('MAPBOX_TOKEN')
                    profile = "mapbox/walking" # driving-traffic, driving, cycling
                    mapbox_iso_url = rf"https://api.mapbox.com/isochrone/v1/{profile}/{coords_center[0]},{coords_center[1]}"
                    response = requests.get(
                        mapbox_iso_url,
                        params={
                            'contours_minutes': minutes,
                            'polygons': 'true',
                            'access_token': mapbox_token
                        }
                    )

                    if response.status_code != 200:
                        return np.nan
                    
                    MAPBOX_REQUESTS_NUM += 1
                    
                    isochrone_data = response.json()                    
                    if 'features' in isochrone_data:
                        distance_polygon = Polygon(map(tuple, isochrone_data['features'][0]['geometry']['coordinates'][0]))
                        insert_query = '''
                            INSERT INTO isochrones_info (
                                address_point,
                                distance_polygon
                            ) VALUES(
                                %s,
                                %s
                            );
                        '''

                        cur.execute(
                            insert_query, 
                            (
                                geometry_coords_center,
                                wkb.dumps(distance_polygon, hex=True, srid=4326)
                            )
                        )
                        conn.commit()
                        return distance_polygon
                    else:
                        return np.nan 
    except Exception as e:
        print(f'Error: {str(e).capitalize()}')
        logger.critical("Координаты: {coords_center}\n")
        return np.nan


def is_railway_near(isochrone_coords, df):
    if pd.isnull(isochrone_coords):
        return np.nan
    
    polygon = Polygon(isochrone_coords)

    railway_df = df.copy()
    railway_df['point'] = railway_df.apply(lambda x: Point(x['lon'], x['lat']), axis=1)
    return any([polygon.contains(point) for point in railway_df['point'].to_list()])


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
        response = requests.get(url)
        json_data = response.json()

        auction_start_date = json_data.get('auctionStartDate')
        bidd_start_date = json_data.get('biddStartTime')
        auction_link = json_data.get('etpUrl')
        price_step = json_data.get('priceStep')
        deposit_price = json_data.get('deposit')

        attachmets = json_data.get('lotAttachments')
        files = [(x['fileName'], 'https://torgi.gov.ru/new/file-store/v1/'+x['fileId']) for x in attachmets]
        return auction_start_date, bidd_start_date, auction_link, price_step, deposit_price, files
    except Exception as e:
        logger.error(f'Error in additional data!\n{e}')
        return [np.nan] * 6


def get_pkk_link(coords_center: list, cad_num: str):
    try:
        if isinstance(coords_center, list):
            coords = ','.join(map(str, coords_center[::-1]))
            cad_num = ':'.join([str(int(x)) for x in cad_num.split(':')])
            return f"https://pkk.rosreestr.ru/#/search/{coords}/19/@5w3tqw5ca?text={cad_num}&opened={cad_num}"
        else:
            return np.nan
    except Exception as e:
        logger.error(f'Ошибка в получении кадастровой карты: {e}')
        return np.nan


def generate_map(lots_df, raylway_df):
    try:
        map_coords = list(np.mean(lots_df['coords_center'].to_list(), axis=0))[::-1]
    except Exception:
        map_coords = [94.15, 66.25]

    current_map = folium.Map(
        location=map_coords, 
        zoom_start=5, 
        control_scale=True
    )

    time_now = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
    html_title = """
        <title>Купить гектар земли в речной долине от государства СНТ ИЖС ЛПХ</title>
        <meta name="description" content="Поиск аукционных лотов земельных участков от ГИС Торги на карте. Земля и водный объект рядом с жд станциями">
    """
    html_yandex = '''
        <!-- Yandex.Metrika counter -->
        <script type="text/javascript" >
            (function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};
            m[i].l=1*new Date();
            for (var j = 0; j < document.scripts.length; j++) {if (document.scripts[j].src === r) { return; }}
            k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)})
            (window, document, "script", "https://mc.yandex.ru/metrika/tag.js", "ym");
        
            ym(95958976, "init", {
                clickmap:true,
                trackLinks:true,
                accurateTrackBounce:true
            });
        </script>
        <noscript><div><img src="https://mc.yandex.ru/watch/95958976" style="position:absolute; left:-9999px;" alt="" /></div></noscript>
        <!-- /Yandex.Metrika counter -->
    '''
    html_div = f"""
        <div style="position: fixed; bottom: 0px; right: 0px; background-color: white; border: 0px solid gray; z-index: 9999; padding-left: 3px; border-radius: 0px; height: 15px; width: 270px;">
            <p style="font-size:11px; vertical-align: center; text-align: center;"><b>Данные актуальны на дату:</b> {time_now}</p>
        </div>
    """
    current_map.get_root().header.add_child(folium.Element(html_title))
    current_map.get_root().header.add_child(folium.Element(html_yandex))
    current_map.get_root().html.add_child(folium.Element(html_div))

    if len(raylway_df) > 0:
        raylway_df['geometry'] = raylway_df.apply(lambda x: Point((x['lon'], x['lat'])), axis=1)

        railway_df_gjson = folium.GeoJson(
            gpd.GeoDataFrame(raylway_df[['name', 'geometry']], geometry='geometry', crs='EPSG:4326'), 
            name="railways",
            highlight_function=lambda x: {'fillOpacity': 0.8}
        )
    
    # category_layers = []
    
        railways_layer = MarkerCluster(
            name='Ж/Д Станции', 
            overlay=True,
            show=False
        )

        # Добавление на карту ЖД
        for feature in railway_df_gjson.data['features']:
            if feature['geometry']['type'] == 'Point':
                folium.Marker(
                    location=list(reversed(feature['geometry']['coordinates'])),
                    icon=folium.Icon(
                        color='lightgray',
                        icon_color='#ff033e',
                        icon='fa-solid fa-train',
                        prefix='fa'
                    ),
                    tooltip=f"<b>{feature['properties']['name']}</b>"
                ).add_to(railways_layer)

        railways_layer.add_to(current_map)
    
    categories = list(lots_df['category'].unique())

    for cat in categories:
        tmp_df = lots_df[lots_df['category'] == cat].reset_index(drop=True)
        cat_layer = MarkerCluster(name=cat)
        
        # lots_layer = MarkerCluster(
        #     name='Земельные участки', 
        #     overlay=True
        # )
        # isochrones_layer = folium.FeatureGroup(name='Шаговая доступность (30 мин.)', show=False)

        # category_layers.append(cat_layer)

        for _, r in tmp_df.iterrows():
            # folium.GeoJson(
            #     data=gpd.GeoSeries(r['isochrones']).simplify(tolerance=0.001).to_json(), 
            #     style_function=lambda _: {"fillColor": "#ff0000"},
            #     tooltip=f"<b>Шаговая доступность (30 мин)</b>"
            # ).add_to(isochrones_layer)

            rent_period = r['rent_period'] if not pd.isnull(r['rent_period']) else 'Не указано'
            price = f"{r['priceMin']} руб." if not pd.isnull(r['priceMin']) else 'Не указано'
            price_step = f"{r['price_step']} руб." if not pd.isnull(r['price_step']) else 'Не указано'
            deposit_price = f"{r['deposit_price']} руб." if not pd.isnull(r['deposit_price']) else 'Не указано'
            area = f"{r['area']} м²" if not pd.isnull(r['area']) else 'Не указано'
            bidd_start_date = f"{r['bidd_start_date'].strftime('%d.%m.%Y %H:%M')} ({r['timeZoneName']})" \
                if not pd.isnull(r['bidd_start_date']) else 'Не указано'
            bidd_end_time = f"{r['biddEndTime'].strftime('%d.%m.%Y %H:%M')} ({r['timeZoneName']})" \
                if not pd.isnull(r['biddEndTime']) else 'Не указано'
            auction_start_date = f"{r['auction_start_date'].strftime('%d.%m.%Y %H:%M')} ({r['timeZoneName']})" \
                if not pd.isnull(r['auction_start_date']) else 'Не указано'
            auction_link = f"<br><a href={r['auction_link']} target='_blank'>Аукцион</a><br>" \
                if not pd.isnull(r['auction_link']) else "<br>"
            if 'cad_link' in tmp_df.columns:
                cad_link = f"<a href={r['cad_link']} target='_blank'>Кадастровая карта</a><br><br>" \
                    if not pd.isnull(r['cad_link']) else "<br><br>"
            
            files = r['files']
            html_files = '\n'.join([f"<a href={lnk} target='_blank'>{name}</a><br>" for (name, lnk) in files])

            popup = folium.Popup(
                f"""
                    <b>Дата и время начала подачи заявок: </b>{bidd_start_date}<br>
                    <b>Дата и время окончания подачи заявок: </b>{bidd_end_time}<br>
                    <b>Дата проведения торгов: </b>{auction_start_date}<br>
                    <b>Начальная цена: </b>{price}<br>
                    <b>Размер задатка: </b>{deposit_price}<br>
                    <b>Шаг аукциона: </b>{price_step}<br>
                    <b>Площадь: </b>{area}<br>
                    <b>Срок аренды: </b>{rent_period}<br>
                    <a href={r['link']} target='_blank'>Лот</a>
                    {auction_link}
                    {cad_link}
                    <b>Файлы</b><br>
                """ + html_files,
                max_width=350
            )
            folium.Marker(
                location=r['coords_center'][::-1],
                popup=popup,
                icon=folium.Icon(
                    color="green", 
                    icon="glyphicon glyphicon-home"
                )
            ).add_to(cat_layer)

        cat_layer.add_to(current_map)

    folium.LayerControl().add_to(current_map)

    # time_now = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
    # html = f"""
    #     <div style="position: fixed; bottom: 0px; right: 0px; background-color: white; border: 0px solid gray; z-index: 9999; padding-left: 3px; border-radius: 0px; height: 15px; width: 250px;">
    #         <p style="font-size:11px; vertical-align: center;"><b>Данные актуальны на дату:</b> {time_now}</p>
    #     </div>
    # """

    # folium.Marker(
    #     location=map_center,
    #     icon=folium.DivIcon(html=folium.Element(html))
    # ).add_to(current_map)

    # GroupedLayerControl(
    #     groups={
    #         'Земельные участки': category_layers
    #     },
    #     exclusive_groups=False,
    #     collapsed=False
    # ).add_to(current_map)

    current_map.save('data/maps/map.html')
