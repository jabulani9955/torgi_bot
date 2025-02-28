import json
from typing import Optional, Any, Dict
import redis.asyncio as redis
import structlog
from datetime import datetime, timedelta

logger = structlog.get_logger()

class FakeRedis:
    """Заглушка для Redis при локальной разработке"""
    def __init__(self):
        self.storage = {}
        self.logger = logger.bind(service="fake_redis")
    
    async def init(self):
        """Инициализация"""
        self.logger.info("FakeRedis initialized")
    
    async def close(self):
        """Закрытие"""
        self.storage.clear()
        self.logger.info("FakeRedis closed")
    
    async def get_progress(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получает прогресс"""
        key = f"progress:{user_id}"
        return self.storage.get(key)
    
    async def update_progress(
        self,
        user_id: int,
        current: int,
        total: int,
        force: bool = False
    ) -> bool:
        """Обновляет прогресс"""
        try:
            now = datetime.now()
            last_update_key = f"last_update:{user_id}"
            
            # Проверяем последнее обновление
            last_update = self.storage.get(last_update_key)
            if last_update and not force:
                last_update_time = datetime.fromisoformat(last_update)
                if now - last_update_time < timedelta(seconds=3):
                    return False
            
            # Обновляем прогресс
            progress_data = {
                "current": current,
                "total": total,
                "percentage": round(current / total * 100, 1),
                "updated_at": now.isoformat()
            }
            
            self.storage[f"progress:{user_id}"] = progress_data
            self.storage[last_update_key] = now.isoformat()
            return True
            
        except Exception as e:
            self.logger.error(
                "Failed to update progress",
                user_id=user_id,
                error=str(e)
            )
            return False
    
    async def clear_progress(self, user_id: int):
        """Очищает прогресс"""
        self.storage.pop(f"progress:{user_id}", None)
        self.storage.pop(f"last_update:{user_id}", None)
    
    async def cache_data(self, key: str, data: Any, ttl: int = 3600):
        """Кэширует данные"""
        self.storage[key] = data
    
    async def get_cached_data(self, key: str) -> Optional[Any]:
        """Получает кэшированные данные"""
        return self.storage.get(key)


class RedisService:
    def __init__(self, host: str = "redis", port: int = 6379, db: int = 0):
        self.redis = redis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=True
        )
        self.logger = logger.bind(service="redis")
    
    async def init(self):
        """Инициализация соединения"""
        try:
            await self.redis.ping()
            self.logger.info("Redis connection established")
        except Exception as e:
            self.logger.error("Redis connection failed", error=str(e))
            raise
    
    async def close(self):
        """Закрытие соединения"""
        await self.redis.close()
        self.logger.info("Redis connection closed")
    
    async def get_progress(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получает прогресс загрузки для пользователя"""
        try:
            data = await self.redis.get(f"progress:{user_id}")
            return json.loads(data) if data else None
        except Exception as e:
            self.logger.error("Failed to get progress", user_id=user_id, error=str(e))
            return None
    
    async def update_progress(
        self,
        user_id: int,
        current: int,
        total: int,
        force: bool = False
    ) -> bool:
        """Обновляет прогресс загрузки с защитой от флуда"""
        try:
            # Получаем текущее время
            now = datetime.now()
            
            # Проверяем, когда было последнее обновление
            last_update = await self.redis.get(f"last_update:{user_id}")
            if last_update and not force:
                last_update_time = datetime.fromisoformat(last_update)
                if now - last_update_time < timedelta(seconds=3):
                    return False
            
            # Обновляем прогресс
            progress_data = {
                "current": current,
                "total": total,
                "percentage": round(current / total * 100, 1),
                "updated_at": now.isoformat()
            }
            
            # Сохраняем данные
            await self.redis.set(
                f"progress:{user_id}",
                json.dumps(progress_data),
                ex=3600  # Храним 1 час
            )
            await self.redis.set(
                f"last_update:{user_id}",
                now.isoformat(),
                ex=3600
            )
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Failed to update progress",
                user_id=user_id,
                error=str(e)
            )
            return False
    
    async def clear_progress(self, user_id: int):
        """Очищает данные о прогрессе"""
        try:
            await self.redis.delete(f"progress:{user_id}", f"last_update:{user_id}")
        except Exception as e:
            self.logger.error(
                "Failed to clear progress",
                user_id=user_id,
                error=str(e)
            )
    
    async def cache_data(self, key: str, data: Any, ttl: int = 3600):
        """Кэширует данные"""
        try:
            await self.redis.set(key, json.dumps(data), ex=ttl)
        except Exception as e:
            self.logger.error("Failed to cache data", key=key, error=str(e))
    
    async def get_cached_data(self, key: str) -> Optional[Any]:
        """Получает кэшированные данные"""
        try:
            data = await self.redis.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            self.logger.error("Failed to get cached data", key=key, error=str(e))
            return None


# Глобальный экземпляр сервиса
redis_service: Optional[RedisService] = None

async def init_redis(config) -> Any:
    """Инициализация Redis или его заглушки"""
    if config.redis.enabled:
        service = RedisService(
            host=config.redis.host,
            port=config.redis.port
        )
    else:
        service = FakeRedis()
    
    await service.init()
    return service 