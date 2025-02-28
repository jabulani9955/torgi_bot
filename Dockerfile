FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir --upgrade pip

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ ./bot/
COPY const_filters/ ./const_filters/

RUN mkdir -p logs

CMD ["python", "-m", "bot"] 