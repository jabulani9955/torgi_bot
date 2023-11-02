import json
import datetime

import pandas as pd
import requests


YANDEX_API = '65f602a2-d988-4a8a-bc23-32f3120ead18'
GEOCODE_URL = f'https://geocode-maps.yandex.ru/1.x/?apikey={YANDEX_API}&geocode={search_text}&format=json'


def collect_data(search_text=None, category=None, subject=None):
    time_now = datetime.datetime.now().strftime(r"%Y%m%d_%H%M%S")
    full_json_data = []
    BASE_URL = r"https://torgi.gov.ru/new/api/public/lotcards/search?size=100&sort=firstVersionPublicationDate,desc&lotStatus=PUBLISHED,APPLICATIONS_SUBMISSION"

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


def main():
    collect_data(category="Земельные участки", subject="Московская область")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(str(e).capitalize())
