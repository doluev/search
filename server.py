from flask import Flask, request, jsonify
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin
import threading
import time
from playwright.sync_api import sync_playwright
import re
import os

app = Flask(__name__)

# Логирование
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Кэш поиска (id -> ссылка на фильм)
search_cache = {}

# Кэш парсинга (id -> статус и данные)
parsing_cache = {}


def get_domain():
    today = datetime.today()
    date_str = today.strftime("%d%m%y")
    return f"https://kinovod{date_str}.pro"


def clean_title(title):
    if not title:
        return ""
    title = re.sub(r'\s+', ' ', title.strip())
    title = re.sub(r'[^\w\s\-\.а-яёА-ЯЁ]', '', title)
    return title.strip()


def scrape_movie_async(url, movie_id):
    """Асинхронный парсинг фильма"""
    logger.info(f"[ASYNC-PARSING] Начат парсинг фильма {movie_id}: {url}")
    parsing_cache[movie_id] = {"status": "parsing", "data": None}

    m3u8_requests = []
    title = "Фильм"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu'
                ]
            )
            page = browser.new_page()

            def handle_request(request_obj):
                if ".m3u8" in request_obj.url:
                    logger.info(f"[MOVIE-ANY] {request_obj.url}")
                    if re.search(r'(master.*\.m3u8$|index.*\.m3u8$)', request_obj.url):
                        logger.info(f"[MOVIE] Найдено по сети: {request_obj.url}")
                        m3u8_requests.append(request_obj.url)

            page.on("request", handle_request)

            page.goto(url, timeout=60000)
            page.wait_for_load_state("networkidle")

            video_tags = page.query_selector_all("video[src]")
            for tag in video_tags:
                src = tag.get_attribute("src")
                if src and ".m3u8" in src:
                    logger.info(f"[MOVIE-DOM] Найден src в <video>: {src}")
                    m3u8_requests.append(src)

            time.sleep(1)
            title = clean_title(page.title() or "Фильм")
            browser.close()

        unique_links = list(dict.fromkeys(m3u8_requests))

        if unique_links:
            parsing_cache[movie_id] = {
                "status": "completed",
                "data": {"title": title, "links": unique_links}
            }
            logger.info(f"[ASYNC-PARSING] Парсинг {movie_id} завершен: {len(unique_links)} ссылок")
        else:
            parsing_cache[movie_id] = {"status": "failed", "data": None}
            logger.warning(f"[ASYNC-PARSING] Парсинг {movie_id} завершен, но ссылки не найдены")

    except Exception as e:
        logger.error(f"[ASYNC-PARSING] Ошибка парсинга {movie_id}: {e}")
        parsing_cache[movie_id] = {"status": "failed", "data": None}


def start_async_parsing(url, movie_id):
    thread = threading.Thread(target=scrape_movie_async, args=(url, movie_id))
    thread.daemon = True
    thread.start()


@app.route("/")
def root():
    return jsonify({
        "service": "Movie Search API",
        "status": "running",
        "endpoints": ["/input", "/search/<id>.json", "/video.json", "/health"]
    }), 200


@app.route("/health")
def health_check():
    return jsonify({"status": "ok"}), 200


@app.route("/input", methods=["GET", "POST"])
def input_handler():
    global search_cache, parsing_cache
    search_cache.clear()
    parsing_cache.clear()

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

    films_sorted = sorted(films, key=lambda x: x["rating_val"], reverse=True)

    base_url = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "localhost:5000")
    if not base_url.startswith("http"):
        base_url = f"https://{base_url}"

    items = []
    for f in films_sorted:
        items.append({
            "title": f["title"],
            "image": f["image"],
            "titleFooter": f["titleFooter"],
            "action": f"panel:{base_url}/search/{f['id']}.json"
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
            "action": f"panel:{base_url}/search/0.json"
        }]
    }
    return jsonify(response)


@app.route("/search/<int:item_id>.json")
def search_film_details(item_id):
    link = search_cache.get(item_id)
    if not link:
        return jsonify({"error": "Фильм не найден"}), 404

    if item_id not in parsing_cache:
        logger.info(f"[ASYNC] Запуск парсинга для фильма {item_id}")
        start_async_parsing(link, item_id)

    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(link, headers=headers, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"Ошибка загрузки {link}: {e}")
        return jsonify({"error": "Не удалось загрузить страницу"}), 500

    soup = BeautifulSoup(resp.text, "html.parser")

    title = soup.select_one("h1")
    title = title.get_text(strip=True) if title else "Без названия"

    alt_title_el = soup.select_one('.info_item .value[itemprop="alternativeHeadline"]')
    alt_title = alt_title_el.get_text(strip=True) if alt_title_el else title

    country = ""
    year = ""
    genres = []
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

    poster = soup.select_one(".poster img")
    poster = urljoin(link, poster["src"]) if poster and poster.has_attr("src") else "https://via.placeholder.com/160x240"

    rating = soup.select_one(".rating")
    rating = rating.get_text(strip=True) if rating else "0"

    description = soup.select_one('div.body[itemprop="description"]')
    description = description.get_text(strip=True) if description else "Описание отсутствует"

    base_url = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "localhost:5000")
    if not base_url.startswith("http"):
        base_url = f"https://{base_url}"

    response = {
        "type": "pages",
        "headline": title,
        "pages": [
            {
                "headline": ", ".join([x for x in [alt_title, country, year] if x]),
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
                        "imageWidth": 4,
                        "action": f"panel:{base_url}/video.json?id={item_id}"
                    }
                ]
            }
        ]
    }
    return jsonify(response)


@app.route("/video.json")
def video_handler():
    item_id = request.args.get("id", type=int)
    if not item_id:
        return jsonify({"error": "Не указан параметр id"}), 400

    parse_status = parsing_cache.get(item_id)
    if not parse_status:
        return jsonify({"error": "Парсинг не найден"}), 404

    if parse_status["status"] == "parsing":
        return jsonify({"error": "Парсинг в процессе"}), 202

    if parse_status["status"] == "failed":
        return jsonify({"error": "Парсинг завершился с ошибкой"}), 500

    if parse_status["status"] == "completed":
        data = parse_status["data"]
        if not data or not data.get("links"):
            return jsonify({"error": "Видео не найдено"}), 404

        items = []
        for i, video_url in enumerate(data["links"], 1):
            items.append({
                "title": f"Качество {i}",
                "playerLabel": f"{data['title']} - Качество {i}",
                "action": f"video:{video_url}"
            })

        response = {
            "type": "pages",
            "headline": "Videos",
            "template": {
                "tag": "Web",
                "type": "separate",
                "layout": "0,0,2,4",
                "icon": "msx-white-soft:movie",
                "color": "msx-glass"
            },
            "items": items
        }
        return jsonify(response)

    return jsonify({"error": "Неизвестный статус парсинга"}), 500


@app.after_request
def after_request(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type")
    response.headers.add("Access-Control-Allow-Methods", "GET,POST")
    return response


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
