# Torgi Bot

Telegram бот для получения данных с torgi.gov.ru

## Локальная разработка

1. Создайте виртуальное окружение:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Создайте файл `.env` из примера:
```bash
cp .env.example .env
```

4. Отредактируйте `.env`, добавив токен бота:
```
BOT_TOKEN=your_bot_token_here
USE_REDIS=false
```

5. Запустите бота:
```bash
python -m bot
```

## Деплой на сервер

1. Клонируйте репозиторий на сервер:
```bash
git clone https://github.com/your_username/torgi_bot.git
cd torgi_bot
```

2. Создайте файл `.env` с продакшен настройками:
```
BOT_TOKEN=your_bot_token_here
USE_REDIS=true
REDIS_HOST=redis
REDIS_PORT=6379
```

3. Запустите с помощью Docker Compose:
```bash
docker-compose up -d
```

4. Просмотр логов:
```bash
docker-compose logs -f
```

## Обновление бота на сервере

1. Получите последние изменения:
```bash
git pull origin main
```

2. Пересоберите и перезапустите контейнеры:
```bash
docker-compose up -d --build
```

## Структура проекта

```
bot/
├── __init__.py
├── __main__.py          # Точка входа
├── config.py            # Конфигурация
├── handlers/            # Обработчики команд
├── keyboards/           # Клавиатуры
├── services/           # Сервисы (Redis, API)
├── states/             # Состояния FSM
└── utils/              # Утилиты
```

## Разработка

1. Создайте новую ветку для фичи:
```bash
git checkout -b feature/new-feature
```

2. Внесите изменения и закоммитьте:
```bash
git add .
git commit -m "Add new feature"
```

3. Отправьте изменения в репозиторий:
```bash
git push origin feature/new-feature
```

4. Создайте Pull Request на GitHub

## Функционал

- Выбор субъектов РФ
- Выбор статусов лотов
- Получение данных в формате Excel
- Поддержка множественного выбора параметров
- Пагинация для удобного выбора субъектов

## Установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/yourusername/torgi_bot.git
cd torgi_bot
```

2. Создайте виртуальное окружение и активируйте его:
```bash
python -m venv venv
source venv/bin/activate  # для Linux/Mac
venv\Scripts\activate     # для Windows
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Создайте файл `.env` и добавьте в него токен вашего бота:
```
BOT_TOKEN=your_bot_token_here
```

## Запуск

```bash
python bot.py
```

## Использование

1. Отправьте команду `/start` боту
2. Нажмите на кнопку "⚙️ Настройки"
3. Выберите необходимые субъекты РФ и статусы
4. Нажмите "💾 Сохранить" для получения данных в формате Excel

## Требования

- Python 3.7+
- Токен Telegram бота (получить можно у @BotFather) 