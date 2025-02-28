import redis
import json
from typing import Any, Dict, Optional

def connect_to_redis() -> redis.Redis:
    """Подключение к Redis"""
    return redis.Redis(
        host='localhost',  # или из env
        port=6379,        # или из env
        db=0,            # или из env
        decode_responses=True  # автоматически декодировать ответы в строки
    )

def get_all_keys() -> list:
    """Получить все ключи"""
    r = connect_to_redis()
    return r.keys('*')

def get_key_value(key: str) -> Any:
    """Получить значение ключа с учетом его типа"""
    r = connect_to_redis()
    key_type = r.type(key)
    
    if key_type == 'string':
        return r.get(key)
    elif key_type == 'hash':
        return r.hgetall(key)
    elif key_type == 'list':
        return r.lrange(key, 0, -1)
    elif key_type == 'set':
        return list(r.smembers(key))
    elif key_type == 'zset':
        return r.zrange(key, 0, -1, withscores=True)
    else:
        return None

def print_database_content():
    """Вывести все содержимое базы в читаемом формате"""
    r = connect_to_redis()
    keys = get_all_keys()
    
    print("\n=== Redis Database Content ===\n")
    
    if not keys:
        print("База данных пуста")
        return
        
    for key in keys:
        value = get_key_value(key)
        key_type = r.type(key)
        
        print(f"\nKey: {key}")
        print(f"Type: {key_type}")
        print("Value:", end=" ")
        
        if isinstance(value, dict):
            print(json.dumps(value, ensure_ascii=False, indent=2))
        else:
            print(value)

if __name__ == '__main__':
    try:
        print_database_content()
    except redis.ConnectionError:
        print("Ошибка подключения к Redis. Проверьте, что Redis запущен и доступен.") 