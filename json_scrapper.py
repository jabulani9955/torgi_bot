import json

import pandas as pd
import requests



search_text = 'Астраханская область, г. Астрахань, р-н Трусовский, ул. Николая Ветошникова, д. 1б'
search_text_error = 'дунайкабобрайка10'
YANDEX_API = '65f602a2-d988-4a8a-bc23-32f3120ead18'

GEOCODE_URL = f'https://geocode-maps.yandex.ru/1.x/?apikey={YANDEX_API}&geocode={search_text}&format=json'

# RAILWAY_STATIONS_MOSCOW_URL = 'http://osm.sbin.ru/esr/region:mosobl:l'
yandex_coords = requests.get(GEOCODE_URL).json()
print(', '.join(yandex_coords['response']['GeoObjectCollection']['featureMember'][0]['GeoObject']['Point']['pos'].split()[::-1]))
# with open('yandex_coords.json', 'w', encoding='utf-8') as f:
#         json.dump(yandex_coords, f, indent=4, ensure_ascii=False)


def collect_data(search_text: str, cat_code: int):
    full_json_data = []
    
    TORGI_URL_FIRST = f'https://torgi.gov.ru/new/api/public/lotcards/search?text={search_text}&catCode={cat_code}&size=100'
    json_data = requests.get(TORGI_URL_FIRST).json()
    num_pages = json_data['totalPages']
    full_json_data.append(json_data)
    
    for page_num in range(1, num_pages):
        TORGI_URL = f'https://torgi.gov.ru/new/api/public/lotcards/search?text={search_text}&catCode={cat_code}&size=100&page={page_num}'
        full_json_data.append(requests.get(TORGI_URL).json())

    with open('json_file_full.json', 'w', encoding='utf-8') as f:
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


def main():
    # collect_data(search_text='Астрахань', cat_code=7)
    # parse_json()
    # get_coords(json_file_path=r'json_file_test_geocode_error_request.json')
    ...


if __name__ == '__main__':
    
    main()
