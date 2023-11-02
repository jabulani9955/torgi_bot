import os
import json
import datetime
import logging

import requests

from torgi.src.data_processing import data_processing


def collect_data(search_text=None, category=None, subject=None):
    time_now = datetime.datetime.now().strftime(r"%Y%m%d_%H%M%S")
    BASE_URL = r"https://torgi.gov.ru/new/api/public/lotcards/search?" \
             + r"size=100&sort=firstVersionPublicationDate,desc&lotStatus=PUBLISHED,APPLICATIONS_SUBMISSION"

    if search_text:
        BASE_URL += f"&text={search_text}"

    if category:
        with open('data/const_filters/catCode.json', encoding='utf-8') as f:
            category_data = json.load(f)
            cat_code = [cat.get('code') for cat in category_data if cat.get('name') == category][0]
            BASE_URL += f"&catCode={cat_code}"

    if subject:
        with open('data/const_filters/dynSubjRF.json', encoding='utf-8') as f:
            subject_data = json.load(f)
            subject_code = [sub.get('code') for sub in subject_data if sub.get('name') == subject][0]
            BASE_URL += f"&dynSubjRF={subject_code}"

    full_json_data = []
    json_data = requests.get(BASE_URL).json()
    num_pages = json_data['totalPages']
    full_json_data.append(json_data)

    for page_num in range(1, num_pages):
        full_json_data.append(requests.get(BASE_URL+f"&page={page_num}").json())


    filepath = f'data/torgi_json_files'
    filename = f'TORGI_{subject}_{time_now}.json'

    if not os.path.exists(filepath):
        os.makedirs(filepath)

    with open(os.path.join(filepath, filename), 'w', encoding='utf-8') as f:
        json.dump(full_json_data, f, indent=4, ensure_ascii=False)

    return os.path.join(filepath, filename)


def main():
    torgi_file = collect_data(category="Земельные участки", subject="Московская область")
    data_processing(torgi_file)

if __name__ == '__main__':

    logging.basicConfig(filename='torgi/log.log', level=logging.INFO, format='%(asctime)s %(clientip)-15s %(user)-8s %(message)s')
    logger = logging.getLogger(__name__)

    try:
        logger.info('Старт...')
        main()
        logger.info('Конец.')
    except Exception as e:
        logger.critical(e, exc_info=True)
