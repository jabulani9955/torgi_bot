import os
import datetime
import logging

import pandas as pd
from torgi.src.functions import (
    fill_cadastr_num, 
    fill_area, 
    get_coords_from_rosreestr, 
    get_mapbox_isochrones, 
    is_railway_near, 
    loading_railways, 
    collect_data,
    load_constants,
    convert_time,
    fill_rent_period,
    generate_map,
    get_additional_data,
    get_pkk_link
)


logger = logging.getLogger(__name__)


def data_processing(lot_subject: str = None, debug=False, center_only=True):
    subjects_data, categories_data, subjectsrf_data = load_constants()
    
    if isinstance(lot_subject, list):
        subjects = lot_subject
    else:
        subjects = [lot_subject] if lot_subject else sorted([sub.get('name') for sub in subjects_data])

    full_df = pd.DataFrame()
    full_railway_stations = pd.DataFrame()

    for subject in subjects: 
        torgi_file = collect_data(subject, subjects_data, categories_data)
    
        if not torgi_file:
            logger.error(f'Нет информации по субъекту. Пропускаю и иду дальше...')
            continue
        elif isinstance(torgi_file, list):
            text_error = '\n'+'\n'.join(torgi_file)
            logger.critical(text_error)
            print(text_error)
            return None
                
        logger.info("Сбор данных завершён. Начинаю обработку данных...")

        data_parts = []
        time_now = datetime.datetime.now().strftime(r"%Y%m%d_%H%M%S")
        railway_source = [sub.get('railway_source') for sub in subjects_data if sub.get('name') == subject][0]
        
        if railway_source:
            railway_stations = loading_railways(railway_source)
            logger.info('Загружены Ж/Д станции.')

        if isinstance(torgi_file, str):
            data = pd.read_json(torgi_file)
        else:
            print('torgi_file НЕ str. Измени это!')
            return None

        for i in data['content']:
            data_parts.extend(i)

        df = pd.DataFrame.from_records(data_parts).reset_index(drop=True)
        df['subject'] = df['subjectRFCode'].apply(lambda x: [sub['name'] for sub in subjectsrf_data if sub['code'] == x][0])
        df['rent_period'] = df['attributes'].apply(fill_rent_period)
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

        logger.info('Начинаю собирать координаты из кадастрового номера...')
        df['rosreestr_info'] = df['cadastral_number'].apply(lambda x: get_coords_from_rosreestr(x, center_only=center_only))
        logger.info('Получены координаты из кадастрового номера.')

        df = df.dropna(subset=['rosreestr_info'])

        if not center_only:
            df['coords'] = df['rosreestr_info'].apply(lambda x: x[0])
            df['coords_center'] = df['rosreestr_info'].apply(lambda x: f"{x[1][0]}, {x[1][1]}")
            df['address'] = df['rosreestr_info'].apply(lambda x: x[2])
        else:
            df['coords_center'] = df['rosreestr_info'].apply(lambda x: x[0])
            df['address'] = df['rosreestr_info'].apply(lambda x: x[1])
        
        logger.info('Начинаю собирать дополнительные данные об объекте...')
        df['additional_info'] = df['id'].apply(get_additional_data)
        logger.info('Дополнительные данные собраны!')
        
        df['auction_start_date'] = df['additional_info'].apply(lambda x: x[0])
        df['bidd_start_date'] = df['additional_info'].apply(lambda x: x[1])
        df['auction_link'] = df['additional_info'].apply(lambda x: x[2])
        df['price_step'] = df['additional_info'].apply(lambda x: x[3])
        df['deposit_price'] = df['additional_info'].apply(lambda x: x[4])
        df['files'] = df['additional_info'].apply(lambda x: x[5])

        # Преобразование времени
        try:
            df['biddEndTime'] = df.apply(lambda x: convert_time(x['biddEndTime'], x['timezoneOffset']), axis=1)
            df['createDate'] = df.apply(lambda x: convert_time(x['createDate'], x['timezoneOffset']), axis=1)
            df['auction_start_date'] = df.apply(lambda x: convert_time(x['auction_start_date'], x['timezoneOffset']), axis=1)
            df['bidd_start_date'] = df.apply(lambda x: convert_time(x['bidd_start_date'], x['timezoneOffset']), axis=1)
        except Exception as e:
            logger.error(f'Ошибка в применении функции преобразования времени: {e}')
        # logger.info('Начинаю вычислять изохроны по координатам...')
        # df['isochrones'] = df.apply(lambda x: get_mapbox_isochrones(x['coords_center'], debug=debug), axis=1)
        # logger.info('Изохроны успешно получены.')
        
        # if railway_source:
        #     df['railway_in_30min'] = df['isochrones'].apply(lambda x: is_railway_near(x, railway_stations))
        # else:
        #     df['railway_in_30min'] = 'NO_RAILWAY'

        df = df.drop(columns=['characteristics', 'attributes', 'subjectRFCode', 'additional_info']).reset_index(drop=True)
        
        df = df.dropna(subset=['coords_center', 'cadastral_number'])

        try:
            df['cad_link'] = df.apply(lambda x: get_pkk_link(x['coords_center'], x['cadastral_number']), axis=1)
        except Exception as e:
            logger.error(f'Ошибка в получении ссылки на кадастровую карту!\n{e}')
            df['cad_link'] = np.nan

        if not debug:
            os.remove(torgi_file)
            logger.info('Временный JSON-файл удалён.')
                
        df = df[['id', 'noticeNumber', 'lotNumber', 'lotStatus', 'biddType', 'biddForm', 'lotName', 'lotDescription', 
                 'biddEndTime', 'lotImages', 'currencyCode', 'category', 'createDate', 'timeZoneName', 'timezoneOffset', 
                 'hasAppeals', 'isStopped', 'isAnnulled', 'priceMin', 'etpCode', 'subject', 'rent_period', 'area', 'cadastral_number', 
                 'link', 'rosreestr_info', 'coords_center', 'address', 'auction_start_date', 'bidd_start_date', 'auction_link', 
                 'price_step', 'deposit_price', 'files', 'cad_link']]
        
        full_df = pd.concat([full_df[full_df.notna()], df[df.notna()]]).reset_index(drop=True)
        
        if railway_source:
            full_railway_stations = pd.concat([full_railway_stations, railway_stations]).reset_index(drop=True)

    logger.info('Сохраняю файл...')
    if not os.path.exists('data'):
        os.makedirs('data')

    fullname_file = os.path.join('data', f'TORGI_{time_now}.csv')
    full_df.to_csv(fullname_file, index=False)
    
    try:
        generate_map(lots_df=full_df.copy(), raylway_df=full_railway_stations.copy())
        logger.info('Карта обновлена.')
    except Exception as e:
        logger.error(f'Ошибка в генерации карты: {e}')
