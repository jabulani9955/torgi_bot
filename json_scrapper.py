import json
import datetime

import pandas as pd
import requests



search_text = 'Астраханская область, г. Астрахань, р-н Трусовский, ул. Николая Ветошникова, д. 1б'
search_text_error = 'дунайкабобрайка10'
YANDEX_API = '65f602a2-d988-4a8a-bc23-32f3120ead18'

GEOCODE_URL = f'https://geocode-maps.yandex.ru/1.x/?apikey={YANDEX_API}&geocode={search_text}&format=json'

# RAILWAY_STATIONS_MOSCOW_URL = 'http://osm.sbin.ru/esr/region:mosobl:l'
# yandex_coords = requests.get(GEOCODE_URL).json()
# print(', '.join(yandex_coords['response']['GeoObjectCollection']['featureMember'][0]['GeoObject']['Point']['pos'].split()[::-1]))
# with open('yandex_coords.json', 'w', encoding='utf-8') as f:
#         json.dump(yandex_coords, f, indent=4, ensure_ascii=False)


def collect_data(search_text=None, category=None, subject=None):
    time_now = datetime.datetime.now().strftime(r"%d_%m_%Y_%H_%M_%S")
    full_json_data = []
    BASE_URL = "https://torgi.gov.ru/new/api/public/lotcards/search?size=100&sort=firstVersionPublicationDate,desc&lotStatus=PUBLISHED,APPLICATIONS_SUBMISSION"
    # print(BASE_URL)
    if search_text:
        BASE_URL += f"&text={search_text}"
    if category:
        with open(r"data\const_filters\catCode.json", encoding="utf-8") as f:
            category_data = json.load(f)
            cat_code = [cat.get('code') for cat in category_data if cat.get('name') == category][0]
            BASE_URL += f"&catCode={cat_code}"
    if subject:
        with open(r"data\const_filters\dynSubjRF.json", encoding="utf-8") as f:
            subject_data = json.load(f)
            subject_code = [sub.get('code') for sub in subject_data if sub.get('name') == subject][0]
            BASE_URL += f"&dynSubjRF={subject_code}"
    json_data = requests.get(BASE_URL).json()
    num_pages = json_data['totalPages']
    full_json_data.append(json_data)
    for page_num in range(1, num_pages):
        full_json_data.append(requests.get(BASE_URL+f"&page={page_num}").json())

    with open(f'TORGI_{subject}_{time_now}.json', 'w', encoding='utf-8') as f:
        json.dump(full_json_data, f, indent=4, ensure_ascii=False)


def parse_json():
    with open('json_file_full.json', encoding='utf-8') as f:
        data = pd.read_json(f)

    data_parts = []
    for json_part in data['content']:
        data_parts.extend(json_part)

    df = pd.DataFrame.from_records(data_parts)
    df.to_csv('test_excel.csv')
    

def get_coords(json_file_path: str):
    with open(json_file_path, encoding='utf-8') as f:
        data = json.load(f)
    
    responses = data['response']['GeoObjectCollection']['featureMember']
    
    if len(responses) >= 1:
        coords = tuple(map(float, responses[0]['GeoObject']['Point']['pos'].split()[::-1]))
    else:
        print('Response errror. No coords!')
        coords = None

    print(coords)


def plots_isochrone():
    ...


def main():
    collect_data(category="Земельные участки", subject="Московская область")
    # parse_json()
    # get_coords(json_file_path=r'json_file_test_geocode_error_request.json')


if __name__ == '__main__':
    
    main()
