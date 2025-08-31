from flask import Flask, request, jsonify
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin

app = Flask(__name__)

# Логирование
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Кэш поиска (id -> ссылка на фильм)
search_cache = {}

def get_domain():
    today = datetime.today()
    date_str = today.strftime("%d%m%y")
    return f"https://kinovod{date_str}.pro"

# --- /input: поиск фильмов ---
@app.route("/input", methods=["GET", "POST"])
def input_handler():
    global search_cache
    search_cache.clear()

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

        for idx, item in enumerate(soup.select("ul.items.with_spacer li.item"), start=1):
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
            rating = rating_el.get_text(strip=True) if rating_el else "0"

            try:
                rating_val = float(rating.replace(",", "."))
            except:
                rating_val = 0.0

            footer_parts = [p for p in [year, quality, rating] if p]
            footer = ", ".join(footer_parts)

            search_cache[idx] = link

            films.append({
                "id": idx,
                "title": title,
                "image": poster,
                "titleFooter": footer,
                "rating_val": rating_val
            })
    except Exception as e:
        logger.error(f"Ошибка при поиске: {e}")

    # сортировка по убыванию рейтинга
    films_sorted = sorted(films, key=lambda x: x["rating_val"], reverse=True)

    # готовим JSON
    items = []
    for f in films_sorted:
        items.append({
            "title": f["title"],
            "image": f["image"],
            "titleFooter": f["titleFooter"],
            "action": f"panel:https://search-zlbh.onrender.com/search/{f['id']}.json"
        })

    response = {
        "type": "list",
        "headline": input_text,
        "template": {
            "type": "separate",
            "layout": "0,0,2,4",
            "color": "msx-glass",
            "iconSize": "medium",
            "title": input_text,
            "image": items[0]["image"] if items else "https://via.placeholder.com/160x240"
        },
        "items": items or [{
            "title": "Ничего не найдено",
            "image": "https://via.placeholder.com/160x240",
            "titleFooter": "",
            "action": "panel:https://search-zlbh.onrender.com/search/0.json"
        }]
    }
    return jsonify(response)

# --- /search/<id>.json: данные о фильме ---
@app.route("/search/<int:item_id>.json")
def search_film_details(item_id):
    link = search_cache.get(item_id)
    if not link:
        return jsonify({"error": "Фильм не найден"}), 404

    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(link, headers=headers, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"Ошибка загрузки {link}: {e}")
        return jsonify({"error": "Не удалось загрузить страницу"}), 500

    soup = BeautifulSoup(resp.text, "html.parser")

    # --- название ---
    title = soup.select_one("h1")
    title = title.get_text(strip=True) if title else "Без названия"

    # --- оригинальное название ---
    alt_title_el = soup.select_one('.info_item .value[itemprop="alternativeHeadline"]')
    alt_title = alt_title_el.get_text(strip=True) if alt_title_el else title

    # --- страна ---
    country = ""
    for info in soup.select("div.info_item"):
        key = info.select_one(".key")
        val = info.select_one(".value")
        if not key or not val:
            continue
        key_text = key.get_text(strip=True).lower()
        if key_text == "страна":
            country = val.get_text(strip=True)
        elif key_text == "год":
            year = val.get_text(strip=True)
        elif key_text == "жанр":
            genres = [g.get_text(strip=True) for g in val.select('[itemprop="genre"]')]

    # если год не найден в блоке, fallback
    year = locals().get("year", "")

    # --- постер ---
    poster = soup.select_one(".poster img")
    poster = urljoin(link, poster["src"]) if poster and poster.has_attr("src") else "https://via.placeholder.com/160x240"

    # --- рейтинг ---
    rating = soup.select_one(".rating")
    rating = rating.get_text(strip=True) if rating else "0"

    # --- описание ---
    description = soup.select_one('div.body[itemprop="description"]')
    description = description.get_text(strip=True) if description else "Описание отсутствует"

    # JSON в формате pages
    response = {
        "type": "pages",
        "headline": title,
        "pages": [
            {
                "headline": ", ".join([x for x in [alt_title, country, year] if x]),  # orig + страна + год
                "items": [
                    {
                        "type": "default",
                        "layout": "0,0,8,6",
                        "headline": title,
                        "text": description,
                        "titleHeader": f"Жанры: {', '.join(genres) if genres else 'не указаны'}",
                        "title": f"Рейтинг: {rating}",
                        "titleFooter": f"{year}",
                        "image": poster,
                        "imageFiller": "cover",
                        "imageWidth": 4
                        "action": "video:http://msx.benzac.de/media/video1.mp4"
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
