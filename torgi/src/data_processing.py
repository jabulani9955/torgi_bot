import os
import datetime

import pandas as pd
from .functions import fill_cadastr_num, fill_area, get_values_from_rosreestr, get_mapbox_isochrones, is_railway_near


def loading_railways() -> pd.DataFrame:
    esr_df = pd.read_csv('data/const_filters/railways/esr.csv', sep=';')
    osm2esr_df = pd.read_csv('data/const_filters/railways/osm2esr.csv', sep=';')

    railway_stations = esr_df[esr_df['source'] == 'mosobl'][['division', 'railway', 'type', 'esr']].merge(
        osm2esr_df[osm2esr_df['status'] != 0].drop(columns=['status', 'type', 'railway', 'alt_name', 'old_name', 'official_name', 'user']),
        how='left',
        on='esr'
    ).drop(columns=['esr']).dropna(subset=['lat', 'lon']).sort_values(by=['name']).reset_index(drop=True)[[
        'name', 'division', 'railway', 'type', 'osm_id', 'lat', 'lon'
    ]]
    railway_stations.osm_id = railway_stations.osm_id.apply(lambda x: str(x).split('.')[0])
    return railway_stations


def data_processing(torgi_file: str):
    data_parts = []
    mapbox_requests_num = 1
    time_now = datetime.datetime.now().strftime(r"%Y%m%d_%H%M%S")
    date_today = datetime.datetime.now().date().isoformat()

    moscow_railway_stations = loading_railways()
    
    if isinstance(torgi_file, str):
        data = pd.read_json(torgi_file)

    for i in data['content']:
        data_parts.extend(i)

    df = pd.DataFrame.from_records(data_parts).reset_index(drop=True)
    
    df_columns = [
        'id',
        'lotStatus',
        'biddType',
        'biddForm',
        'lotName',
        'lotDescription',
        'priceMin',
        'createDate',
        'biddEndTime',
        'lotImages',
        'category',
        'characteristics',
    ]
    df = df[df_columns].reset_index(drop=True)
    df['biddEndTime'] = pd.to_datetime(df['biddEndTime']).dt.tz_localize(None)
    df['createDate'] = pd.to_datetime(df['createDate']).dt.tz_localize(None)
    df['biddType'] = df['biddType'].apply(lambda x: x['name'])
    df['biddForm'] = df['biddForm'].apply(lambda x: x['name'])
    df['category'] = df['category'].apply(lambda x: x['name'])
    df['area'] = df['characteristics'].apply(fill_area)
    df['cadastral_number'] = df.apply(lambda x: fill_cadastr_num(x['characteristics'], x['lotDescription']), axis=1)
    
    # Получаем уникальный кадастровый номер для каждого лота (группируем и берём самый свежий).
    df = df.groupby('cadastral_number')\
        .apply(lambda x: x.loc[x['createDate'].idxmax()])\
        .sort_values(by='createDate', ascending=False)\
        .reset_index(drop=True)

    df['lotImages'] = df['lotImages'].apply(lambda x: ', '.join(['https://torgi.gov.ru/new/file-store/v1/'+i+'?disposition=inline' for i in x]))
    df['link'] = df['id'].apply(lambda x: 'https://torgi.gov.ru/new/public/lots/lot/' + x) 
    df['rosreestr_info'] = df['cadastral_number'].apply(get_values_from_rosreestr)
    df = df.dropna(subset=['rosreestr_info'])
    df['coords'] = df['rosreestr_info'].apply(lambda x: x[0])
    df['coords_center'] = df['rosreestr_info'].apply(lambda x: f"{x[1][0]}, {x[1][1]}")
    df['address'] = df['rosreestr_info'].apply(lambda x: x[2])

    df.drop(columns=['characteristics', 'rosreestr_info'])
    df['isochrones'] = df.apply(lambda x: get_mapbox_isochrones(x['coords_center'], x['coords']), axis=1)
    df['railway_in_30min'] = df['isochrones'].apply(lambda x: is_railway_near(x, moscow_railway_stations))

    df = df.reset_index(drop=True)
    
    final_df = df.rename(columns={
        'id': 'ID',
        'lotStatus': 'Статус',
        'biddType': 'Тип',
        'biddForm': 'Форма',
        'lotName': 'Название',
        'lotDescription': 'Описание',
        'priceMin': 'Начальная цена',
        'createDate': 'Дата создания',
        'biddEndTime': 'Дата окончания',
        'lotImages': 'Фото',
        'category': 'Категория',
        'area': 'Площадь',
        'cadastral_number': 'Кадастровый номер',
        'link': 'Ссылка',
        'coords_center': 'Координаты',
        'address': 'Адрес',
        'railway_in_30min': 'Ж/Д станция в 30 минутах'
    }).copy()
    
    final_df = final_df[[
        'ID',
        'Статус',
        'Тип',
        'Форма',
        'Название',
        'Описание',
        'Начальная цена',
        'Дата создания',
        'Дата окончания',
        'Категория',
        'Площадь',
        'Кадастровый номер',
        'Координаты',
        'Адрес',
        'Ж/Д станция в 30 минутах',
        'Фото',
        'Ссылка'
    ]]

    dev_path_to_save = f'data/results/{date_today}/dev'
    if not os.path.exists(dev_path_to_save):
        os.makedirs(dev_path_to_save)

    path_to_save = f'data/results/{date_today}/final'
    if not os.path.exists(path_to_save):
        os.makedirs(path_to_save)

    df.to_csv(os.path.join(dev_path_to_save, f'DEV_TORGI_MSK_{time_now}.csv'), index=False)
    final_df.to_excel(os.path.join(path_to_save, f'TORGI_MSK_{time_now}.xlsx'), index=False, engine='xlsxwriter')
