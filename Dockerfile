# Используем официальный образ с поддержкой Playwright
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Рабочая папка
WORKDIR /app

# Копируем requirements.txt
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY . .

# Railway автоматически определяет порт через переменную $PORT
EXPOSE $PORT

# Запуск приложения
CMD gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 120 server:app
