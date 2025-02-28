import asyncio
import logging
import structlog
from pathlib import Path
from logging.handlers import RotatingFileHandler

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from bot.config import Config, load_config
from bot.handlers import register_all_handlers
from bot.keyboards import register_all_keyboards
from bot.keyboards.menu import get_bot_commands
from bot.middlewares import register_all_middlewares
from bot.services import init_redis


async def main():
    # Создаем директорию для логов если её нет
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Настройка логирования в файл и консоль
    file_handler = RotatingFileHandler(
        log_dir / "bot.log",
        maxBytes=5_242_880,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    console_handler = logging.StreamHandler()
    
    # Формат логов
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[file_handler, console_handler]
    )
    
    # Настройка структурированного логирования
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            structlog.stdlib.add_log_level,
            structlog.processors.JSONRenderer()
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
    )
    logger = structlog.get_logger()

    # Загрузка конфигурации
    config: Config = load_config()
    
    # Инициализация Redis
    redis = await init_redis(config)

    # Инициализация бота и диспетчера с новыми параметрами
    default = DefaultBotProperties(parse_mode=ParseMode.HTML)
    bot = Bot(token=config.tg_bot.token, default=default)
    dp = Dispatcher()

    # Регистрация всех компонентов
    register_all_middlewares(dp, config)
    register_all_handlers(dp)
    register_all_keyboards()
    
    # Установка команд бота
    await bot.set_my_commands(get_bot_commands())

    # Запуск бота
    logger.info("Starting bot")
    try:
        await dp.start_polling(bot)
    finally:
        # Закрываем соединение с Redis при завершении
        if redis:
            await redis.close()
            logger.info("Redis connection closed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped!")
