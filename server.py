from flask import Flask, request, jsonify
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin, quote

app = Flask(__name__)

# Логирование
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def get_domain():
    today = datetime.today()
    date_str = today.strftime("%d%m%y")
    return f"https://kinovod{date_str}.pro"

# --- /input: поиск фильмов ---
@app.route("/input", methods=["GET", "POST"])
def input_handler():
    input_text = request.args.get("input", "") or request.form.get("input", "")
    logger.info(f"[INPUT] Получен ввод: {input_text}")

    if not input_text:
        return jsonify({"error": "Нет параметра input"}), 400

    domain = get_domain()
    search_url = f"{domain}/search?query={input_text}"
    headers = {"User-Agent": "Mozilla/5.0"}

    films = []
    try:
        resp = requests.get(search_url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for item in soup.select("ul.items.with_spacer li.item"):
            a_tag = item.select_one(".title a")
            poster_img = item.select_one(".poster img")
            year_el = item.select_one(".year")
            quality_el = item.select_one(".quality, .q")
            rating_el = item.select_one(".rating")

            if not a_tag:
                continue

            title = a_tag.get_text(strip=True)
            link = urljoin(domain, a_tag["href"])
            poster = urljoin(domain, poster_img["src"]) if poster_img and poster_img.has_attr("src") else "https://via.placeholder.com/160x240"
            year = year_el.get_text(strip=True) if year_el else ""
            quality = quality_el.get_text(strip=True) if quality_el else ""
            rating = rating_el.get_text(strip=True) if rating_el else ""

            footer_parts = [p for p in [year, quality, rating] if p]
            footer = ", ".join(footer_parts)

            films.append({
                "title": title,
                "image": poster,
                "titleFooter": footer,
                "action": f"panel:/film?link={quote(link)}"
            })
    except Exception as e:
        logger.error(f"Ошибка при поиске: {e}")

    response = {
        "type": "list",
        "headline": input_text,   # заголовок = ввод
        "template": {
            "type": "separate",
            "layout": "0,0,2,4",
            "color": "msx-glass",
            "icon": "msx-white-soft:movie",
            "iconSize": "medium",
            "title": input_text,
            "image": films[0]["image"] if films else "https://via.placeholder.com/160x240"
        },
        "items": films or [{
            "title": "Ничего не найдено",
            "image": "https://via.placeholder.com/160x240",
            "titleFooter": "",
            "action": "panel:/film?link="
        }]
    }
    return jsonify(response)

# --- /film: детали фильма ---
@app.route("/film")
def film_details():
    link = request.args.get("link", "")
    if not link:
        return jsonify({"error": "Нет ссылки"}), 400

    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(link, headers=headers, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"Ошибка загрузки страницы {link}: {e}")
        return jsonify({"error": "Не удалось получить страницу"}), 500

    soup = BeautifulSoup(resp.text, "html.parser")

    # --- данные со страницы ---
    title = soup.select_one("h1")
    title = title.get_text(strip=True) if title else "Без названия"

    poster = soup.select_one(".poster img")
    poster = urljoin(link, poster["src"]) if poster and poster.has_attr("src") else "https://via.placeholder.com/160x240"

    rating = soup.select_one(".rating")
    rating = rating.get_text(strip=True) if rating else "0"

    description = soup.select_one('div.body[itemprop="description"]')
    description = description.get_text(strip=True) if description else "Описание отсутствует"

    genres = soup.select(".genres a")
    genres = [g.get_text(strip=True) for g in genres] if genres else []

    year_el = soup.select_one(".year")
    year = year_el.get_text(strip=True) if year_el else ""

    # --- Формируем JSON в формате pages ---
    response = {
        "type": "pages",
        "headline": title,
        "pages": [
            {
                "headline": "Информация",
                "items": [
                    {
                        "type": "default",
                        "layout": "0,0,8,6",
                        "headline": title,                    # Название фильма
                        "text": description,                   # Описание
                        "icon": "msx-white-soft:apps",
                        "titleHeader": f"Жанры: {', '.join(genres) if genres else 'не указаны'}",
                        "title": f"Рейтинг: {rating}",
                        "titleFooter": f"{year}",              # Год выпуска
                        "image": poster,
                        "imageFiller": "cover",
                        "imageWidth": 2
                    }
                ]
            }
        ]
    }
    return jsonify(response)

@app.after_request
def after_request(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type")
    response.headers.add("Access-Control-Allow-Methods", "GET,POST")
    return response

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
