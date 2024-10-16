import time
import datetime
import logging

import schedule

from torgi.src.data_processing import data_processing


logging.basicConfig(
    filename='data/torgi.log',
    encoding='utf-8',
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] (%(filename)s) %(message)s"
)
logger = logging.getLogger(__name__)


def main(lot_subject: str = None, debug=False, center_only=True):
    try:
        start_time = datetime.datetime.now()
        print(f"Начало: {start_time.strftime('%H:%M:%S')}")
        logger.info(f'Скрипт запущен.')
        
        data_processing(lot_subject, debug, center_only)

        print(f"Конец: {datetime.datetime.now().strftime('%H:%M:%S')}\nВремя выполнения скрипта: {datetime.datetime.now() - start_time}")
        logger.info(f"Скрипт завершён. Время исполнения: {datetime.datetime.now() - start_time}\n")
        # time.sleep(6000)

    except Exception as e:
        logger.critical(e, exc_info=True)
        # time.sleep(6000)


if __name__ == '__main__':
    # Для запуска парсинга по опроедённым субъектам
    # main(lot_subject=['Липецкая область', 'Ненецкий автономный округ'])

    # Для запуска парсинга по всем субъектам РФ
    main()
    
    # schedule.every().day.at('09:30').do(main, lot_subject=['Калужская область', 'Тверская область'])
    # schedule.every().day.at('13:30').do(main, lot_subject=['Калужская область', 'Тверская область'])
    # schedule.every().day.at('18:30').do(main, lot_subject=['Калужская область', 'Тверская область'])
    # schedule.every().day.at('23:30').do(main, lot_subject=['Калужская область', 'Тверская область'])
    # schedule.every().day.at('05:00').do(main, lot_subject=['Калужская область', 'Тверская область'])
    
    # while True:
    #     schedule.run_pending()
    #     time.sleep(1)
    # main(lot_subject='Московская область')
