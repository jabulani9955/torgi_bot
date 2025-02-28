import os
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class TgBot:
    token: str


@dataclass
class RedisConfig:
    enabled: bool
    host: Optional[str] = None
    port: Optional[int] = None


@dataclass
class ProcessingConfig:
    calculate_coordinates: bool


@dataclass
class Config:
    tg_bot: TgBot
    redis: RedisConfig
    processing: ProcessingConfig


def load_config() -> Config:
    """Загружает конфигурацию из переменных окружения"""
    # Загружаем переменные окружения из .env файла
    env_path = Path('.') / '.env'
    if env_path.exists():
        load_dotenv(env_path)
    
    # Проверяем наличие Redis
    redis_enabled = os.getenv("USE_REDIS", "false").lower() == "true"
    redis_config = RedisConfig(
        enabled=redis_enabled,
        host=os.getenv("REDIS_HOST") if redis_enabled else None,
        port=int(os.getenv("REDIS_PORT", "6379")) if redis_enabled else None
    )
    
    # Настройки обработки данных
    processing_config = ProcessingConfig(
        calculate_coordinates=os.getenv("CALCULATE_COORDINATES", "false").lower() == "true"
    )
    
    # Проверяем наличие токена
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        raise ValueError("BOT_TOKEN не найден в переменных окружения")
    
    return Config(
        tg_bot=TgBot(token=bot_token),
        redis=redis_config,
        processing=processing_config
    ) 