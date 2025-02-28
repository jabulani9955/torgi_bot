"""Сервисы для работы с внешними API и хранилищами данных"""

# Импорт основных сервисов для удобства использования
from bot.services.redis_service import init_redis, RedisService, FakeRedis
from bot.services.data_fetcher import fetch_data, fetch_page_data