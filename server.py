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

def get_domain():
    today = datetime.today()
    date_str = today.strftime("%d%m%y")
    return f"https://kinovod{date_str}.pro"

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
            quality_el = item.select_one(".quality, .q")  # иногда класс меняется

            if not a_tag:
                continue

            title = a_tag.get_text(strip=True)
            poster = urljoin(domain, poster_img["src"]) if poster_img and poster_img.has_attr("src") else "https://via.placeholder.com/160x240"
            year = year_el.get_text(strip=True) if year_el else ""
            quality = quality_el.get_text(strip=True) if quality_el else ""

            films.append({
                "title": title,
                "image": poster,
                "titleFooter": f"{year}, {quality}" if year or quality else ""
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
            "titleFooter": ""
        }]
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
