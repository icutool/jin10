import requests
from bs4 import BeautifulSoup
import json
import os
import re
import time
import traceback

BASE_URL = "https://goodsfu.10jqka.com.cn/qhpl_list/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://goodsfu.10jqka.com.cn/"
}

TIMEOUT = 60
RETRY_COUNT = 3


def log(msg):
    print(f"[LOG] {msg}", flush=True)


def safe_filename(title):
    return re.sub(r'[\\/:*?"<>|]', "_", title)


def load_history():
    if not os.path.exists("article.json"):
        log("article.json 不存在，初始化为空数组")
        return []

    try:
        with open("article.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log("读取 article.json 失败")
        traceback.print_exc()
        return []


def save_history(data):
    with open("article.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_with_retry(url):
    for i in range(RETRY_COUNT):
        try:
            log(f"请求: {url} (第{i+1}次)")
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)

            # 自动识别编码（关键！）
            resp.encoding = resp.apparent_encoding

            if resp.status_code == 200:
                return resp
            else:
                log(f"状态码异常: {resp.status_code}")

        except Exception as e:
            log(f"请求异常: {e}")
            if i == RETRY_COUNT - 1:
                raise
            time.sleep(3)

    return None


def main():
    log("开始抓取列表页")

    try:
        resp = fetch_with_retry(BASE_URL)
    except Exception:
        log("列表页抓取失败")
        traceback.print_exc()
        return

    soup = BeautifulSoup(resp.text, "html.parser")
    items = soup.select("div.list-con ul li")

    log(f"解析到 {len(items)} 条列表数据")

    history = load_history()
    history_times = {item["time"] for item in history}

    new_articles = []

    for index, li in enumerate(items):
        try:
            title_tag = li.select_one("span.arc-title a.news-link")
            time_tag = li.select_one("span.arc-title span")

            if not title_tag or not time_tag:
                log(f"第{index+1}条结构异常，跳过")
                continue

            title = title_tag.get("title").strip()
            href = title_tag.get("href").strip()
            time_text = time_tag.text.strip()

            log(f"发现文章: {title} | 时间: {time_text}")

            if time_text in history_times:
                log("已存在，跳过")
                continue

            # 请求详情页
            detail_resp = fetch_with_retry(href)
            if not detail_resp:
                log("详情页请求失败，跳过")
                continue

            filename = safe_filename(title) + ".html"

            with open(filename, "w", encoding="utf-8") as f:
                f.write(detail_resp.text)

            log(f"已保存文件: {filename}")

            new_articles.append({
                "title": title,
                "time": time_text
            })

            # 避免请求太快
            time.sleep(2)

        except Exception:
            log("处理单条文章时异常")
            traceback.print_exc()
            continue

    if new_articles:
        history = new_articles + history
        save_history(history)
        log(f"新增文章数量: {len(new_articles)}")
    else:
        log("没有新文章")


if __name__ == "__main__":
    main()
