# Используем официальный образ Python для ARM64
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем зависимости для сборки
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Копируем файлы зависимостей
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY bot/ ./bot/
COPY const_filters/ ./const_filters/

# Создаем директорию для логов
RUN mkdir -p logs

# Запускаем бота
CMD ["python", "-m", "bot"] 