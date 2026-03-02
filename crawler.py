import requests
from bs4 import BeautifulSoup
import json
import os
import re

BASE_URL = "https://goodsfu.10jqka.com.cn/qhpl_list/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://goodsfu.10jqka.com.cn/"
}

def safe_filename(title):
    return re.sub(r'[\\/:*?"<>|]', "_", title)

def load_history():
    if not os.path.exists("article.json"):
        return []
    with open("article.json", "r", encoding="utf-8") as f:
        return json.load(f)

def save_history(data):
    with open("article.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    print("开始抓取列表页...")
    resp = requests.get(BASE_URL, headers=HEADERS, timeout=20)
    resp.encoding = "utf-8"

    soup = BeautifulSoup(resp.text, "html.parser")
    items = soup.select("div.list-con ul li")

    history = load_history()
    history_times = {item["time"] for item in history}

    new_articles = []

    for li in items:
        title_tag = li.select_one("span.arc-title a.news-link")
        time_tag = li.select_one("span.arc-title span")

        if not title_tag or not time_tag:
            continue

        title = title_tag.get("title").strip()
        href = title_tag.get("href").strip()
        time_text = time_tag.text.strip()

        if time_text in history_times:
            print("已存在，跳过：", title)
            continue

        print("抓取新文章：", title)

        detail_resp = requests.get(href, headers=HEADERS, timeout=20)
        detail_resp.encoding = "utf-8"

        filename = safe_filename(title) + ".html"

        with open(filename, "w", encoding="utf-8") as f:
            f.write(detail_resp.text)

        new_articles.append({
            "title": title,
            "time": time_text
        })

    if new_articles:
        history = new_articles + history
        save_history(history)
        print("新增文章数量：", len(new_articles))
    else:
        print("没有新文章")

if __name__ == "__main__":
    main()
