import datetime

import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent


def collect_data():
    current_time = datetime.datetime.now().strftime('%d.%m.%Y, %H:%M')
    print(current_time)
    ua = UserAgent()

    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "User-Agent": ua.random,
    }
    cookies = {
        'SESSION': 'OTRhNWM2YzQtZWZkMi00N2Y0LTlkODgtNjNjN2FlNzgxODc2',
        '_ym_uid': '1691681502844862233',
        '_ym_d': '1691681502',
        '_ym_visorc': 'w',
        '_ym_isad': '1'
    }

    # response = requests.get('https://torgi.gov.ru/new/public/lots/reg', headers=headers, cookies=cookies)
    # with open('index.html', 'w', encoding="utf-8") as f:
    #     f.write(response.text)

def main():
    collect_data()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(e)
