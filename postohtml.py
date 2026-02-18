import requests
from jinja2 import Template
from tzlocal import get_localzone
import sqlite3
import re
from datetime import datetime, timezone
import os
from dotenv import load_dotenv

# Определение локальной временной зоны
local_timezone = get_localzone()
# Константы
load_dotenv()
  # ID группы ВКонтакте
HTML_TEMPLATE = """
<style>
    .post {
        margin: 20px;
        padding: 15px;
        border: 1px solid #ddd;
        border-radius: 10px;
    }
    .post img {
        margin: 5px;
        border-radius: 5px;
    }
    .collage {
        display: flex;
        flex-wrap: wrap;
        gap: 5px;
    }
    .collage img {
        width: calc(45% - 5px);
    }
    .collage-3 img {
        width: calc(33.33% - 5px);
    }
    .collage-4 img {
        width: calc(25% - 5px);
    }
</style>

<div class="post {{ post.collage_class }}">
    <p>{{ post.text.replace('\n', '<br>') | safe }}</p>
    {% for image in post.image %}
        <img src="{{ image.url }}" style="width: {{ image.width }}; height: {{ image.height }};">
    {% endfor %}
</div>
"""

def get_group_id():
    group_id = os.getenv("VK_GROUP_ID")
    return group_id

# Функция получения данных из VK API
def fetch_vk_posts(group_id, access_token, count=10):
    url = "https://api.vk.com/method/wall.get"
    params = {
        "owner_id": f"-{group_id}",
        "access_token": access_token,
        "v": "5.131",
        "count": count,
    }
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    if "error" in data:
        err = data["error"]
        msg = err.get("error_msg", str(err))
        raise Exception(f"VK API error: {msg}")
    if "response" in data:
        return data["response"]["items"]
    raise Exception(f"Error from VK API: {data}")


# Получение последнего API-ключа из базы данных
def get_api_key():
    api_key = os.getenv("VK_API_KEY")

    if not api_key:
        raise ValueError("VK_API_KEY не найден в .env")

    # Проверка актуальности ключа
    test_url = "https://api.vk.com/method/users.get"
    test_params = {
        "access_token": api_key,
        "v": "5.131"
    }
    response = requests.get(test_url, params=test_params, timeout=30)

    # Проверяем валидность
    if response.status_code == 200:
        data = response.json()
        if "error" in data:
            raise ValueError("VK_API_KEY в .env недействителен")
        if "response" in data:
            return api_key

    raise ValueError("VK_API_KEY в .env недействителен")

# Удаление эмодзи из текста
def remove_emojis(text):
    text = text.replace('#ГБУДОСОСШОРпофехтованию', '')
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # смайлики
        "\U0001F300-\U0001F5FF"  # символы и пиктограммы
        "\U0001F680-\U0001F6FF"  # транспорт и карты
        "\U0001F700-\U0001F77F"  # дополнительные пиктограммы
        "\U0001F780-\U0001F7FF"  # геометрические символы
        "\U0001F800-\U0001F8FF"  # супплементальные символы
        "\U0001F900-\U0001F9FF"  # руки, лица и прочее
        "\U0001FA00-\U0001FA6F"  # дополнительные смайлы
        "\U0001FA70-\U0001FAFF"  # больше символов
        "\u2600-\u26FF"          # символы (например, солнце)
        "\u2700-\u27BF"          # дополнения
        "]+",
        flags=re.UNICODE
    )
    return emoji_pattern.sub(r'', text)

# Парсинг постов для сохранения
def parse_posts(posts):
    parsed_posts = []

    # Вспомогательная функция для обработки отдельного поста (оригинального или репоста)
    def parse_single_post(post_item):
        # Очистка текста и форматирование времени
        clear_text = remove_emojis(post_item.get("text", ""))
        utc_time = datetime.fromtimestamp(post_item['date'], tz=timezone.utc)
        formatted_time = utc_time.astimezone(local_timezone).strftime('%Y-%m-%d %H:%M:%S')

        # Базовая структура поста
        parsed = {
            "title": post_item['id'],
            "text": clear_text,
            "date": formatted_time,
            "image": []
        }

        # Обработка изображений
        if "attachments" in post_item:
            for attachment in post_item["attachments"]:
                if attachment["type"] == "photo":
                    sizes = attachment.get("photo", {}).get("sizes", [])
                    if isinstance(sizes, list):
                        for size in sizes:
                            if size.get("type") == "x":
                                parsed["image"].append({
                                    "url": size["url"],
                                    "height": size["height"],
                                    "width": size["width"]
                                })
                                break

        return parsed

    # Основной цикл обработки постов
    for post in posts:
        # Парсим основной пост
        parsed_post = parse_single_post(post)

        # Если есть репосты, объединяем их с основным постом
        if "copy_history" in post:
            for repost in post["copy_history"]:
                parsed_repost = parse_single_post(repost)

                # Объединяем текст основного поста и репоста
                if parsed_repost["text"]:
                    parsed_post["text"] += "\n\n" + parsed_repost["text"]

                # Объединяем изображения
                parsed_post["image"].extend(parsed_repost["image"])


        parsed_posts.append(parsed_post)

    return parsed_posts

# Удаление дубликатов из базы данных
def remove_duplicates():
    with sqlite3.connect("posts.db") as connection:
        cursor = connection.cursor()

        cursor.execute("""
        DELETE FROM posts
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM posts
            GROUP BY text, date
        )
        """)

        cursor.execute("""
        DELETE FROM images
        WHERE post_id NOT IN (
            SELECT id FROM posts
        )
        """)
        # Удаление постов без текста
        cursor.execute("DELETE FROM posts WHERE text IS NULL OR TRIM(text) = ''")

# Сохранение постов в базу данных
def sql_insert(posts):
    with sqlite3.connect("posts.db") as connection:
        cursor = connection.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT,
            date TEXT,
            html TEXT,
            title TEXT
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            url TEXT,
            width INTEGER,
            height INTEGER,
            FOREIGN KEY (post_id) REFERENCES posts (id) ON DELETE CASCADE
        )
        """)

        post_template = Template(HTML_TEMPLATE)

        for post in posts:
            image_count = len(post["image"])
            if image_count == 1:
                post["image"][0]["width"] = "50%"
                post["image"][0]["height"] = "auto"
                post["collage_class"] = ""
            elif image_count > 1:
                post["collage_class"] = f"collage collage-{min(image_count, 4)}"
                for img in post["image"]:
                    img["width"] = ""
                    img["height"] = ""

            rendered_html = post_template.render(post=post)

            cursor.execute(
                "INSERT INTO posts (text, date, html, title) VALUES (?, ?, ?, ?)",
                (post['text'], post['date'], rendered_html, str(post.get('title', ''))))
            post_id = cursor.lastrowid

            for image in post['image']:
                cursor.execute(
                    "INSERT INTO images (post_id, url, width, height) VALUES (?, ?, ?, ?)",
                    (post_id, image['url'], image['width'], image['height']))

def main():
    try:
        api_key = get_api_key()
        group_id = get_group_id()
        vk_posts = fetch_vk_posts(group_id, api_key)
        parsed_posts = parse_posts(vk_posts)
        sql_insert(parsed_posts)
        remove_duplicates()

        print("Posts successfully saved to database.")

    except Exception as e:
        print(f"Error: {e}")



if __name__ == "__main__":
    main()


