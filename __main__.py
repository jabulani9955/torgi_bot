import datetime

import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent


def collect_data():
    """ Collect railway stations. """
    current_time = datetime.datetime.now().strftime('%d.%m.%Y, %H:%M')
    print(current_time)
    ua = UserAgent()

    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "User-Agent": ua.random,
    }

    url = r"http://osm.sbin.ru/esr/region:mosobl:l"
    response = requests.get(url, headers=headers)

    with open('index.html', 'w', encoding="utf-8") as f:
        f.write(response.text)


def parse_data(parsing_file: str):
    with open(parsing_file, encoding="utf-8") as f:
        data = f.read()

    soup = BeautifulSoup()
    
    


def main():
    collect_data()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(e)
