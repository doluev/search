# Базовый образ с Python
FROM python:3.12-slim

# Обновляем apt и ставим зависимости для Chromium
RUN apt-get update && apt-get install -y \
    libnss3 libatk1.0-0 libcups2 libxcomposite1 libxrandr2 libxdamage1 \
    libxkbcommon0 libgbm-dev wget curl unzip && \
    rm -rf /var/lib/apt/lists/*

# Рабочая папка
WORKDIR /app

# Копируем зависимости и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Устанавливаем Playwright и Chromium
RUN pip install --no-cache-dir playwright && playwright install --with-deps chromium

# Копируем весь код проекта
COPY . .

# Открываем порт для Render
EXPOSE 5000

# Запуск через gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:5000", "server:app"]
