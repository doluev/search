# Базовый образ с Python
FROM python:3.12-slim

# Обновляем систему и устанавливаем необходимые пакеты
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libdrm2 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    libxss1 \
    libgbm1 \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Рабочая папка
WORKDIR /app

# Копируем зависимости и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Устанавливаем Playwright
RUN pip install --no-cache-dir playwright

# Устанавливаем браузеры с полными зависимостями
RUN playwright install --with-deps chromium

# Проверяем что браузер установлен
RUN playwright install-deps

# Копируем весь код проекта
COPY . .

# Открываем порт для Render
EXPOSE 5000

# Запуск через gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:5000", "-w", "1", "--timeout", "120", "server:app"]
