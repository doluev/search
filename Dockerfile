# Базовый образ с Python
FROM python:3.12-slim

# Устанавливаем системные зависимости для Chromium
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libxss1 \
    libasound2 \
    libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

# Рабочая папка
WORKDIR /app

# Копируем зависимости и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Устанавливаем Playwright и браузеры
RUN pip install --no-cache-dir playwright
RUN playwright install chromium
RUN playwright install-deps chromium

# Копируем весь код проекта
COPY . .

# Устанавливаем переменные окружения для Playwright
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Открываем порт для Render
EXPOSE 5000

# Запуск через gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:5000", "server:app"]
