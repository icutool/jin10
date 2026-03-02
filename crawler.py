import hashlib
import html
import json
import re
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://goodsfu.10jqka.com.cn/qhpl_list/"
ARTICLE_SELECTOR = "div.news-content.article-content"
HISTORY_FILE = Path("article.json")
RAW_DIR = Path("raw")
SITE_DIR = Path("docs")
SITE_ARTICLE_DIR = SITE_DIR / "articles"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://goodsfu.10jqka.com.cn/",
}

TIMEOUT = 60
RETRY_COUNT = 3
RETRY_DELAY_SECONDS = 3
REQUEST_INTERVAL_SECONDS = 2

FALLBACK_CONTENT_HTML = (
    '<div class="news-content article-content">'
    "<p>未提取到正文容器，详情请查看 raw 中保存的原始页面。</p>"
    "</div>"
)

STYLES_CSS = """\
:root {
  color-scheme: light;
  --bg: #f4f7fb;
  --panel: #ffffff;
  --ink: #1f2937;
  --muted: #6b7280;
  --line: #dbe3ef;
  --brand: #005b9a;
  --brand-soft: #e6f2fb;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
  background: radial-gradient(circle at top, #fefefe 0, var(--bg) 45%);
  color: var(--ink);
}

.wrap {
  max-width: 980px;
  margin: 0 auto;
  padding: 24px 16px 40px;
}

.panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 14px;
  box-shadow: 0 8px 24px rgba(8, 36, 70, 0.08);
}

.header {
  padding: 20px 24px;
  border-bottom: 1px solid var(--line);
}

.title {
  margin: 0;
  font-size: 26px;
  line-height: 1.3;
}

.desc {
  margin: 10px 0 0;
  color: var(--muted);
}

.list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.item {
  padding: 16px 24px;
  border-bottom: 1px solid var(--line);
}

.item:last-child { border-bottom: none; }

.item a {
  color: var(--brand);
  text-decoration: none;
  font-weight: 600;
}

.item a:hover { text-decoration: underline; }

.meta {
  margin-top: 8px;
  color: var(--muted);
  font-size: 14px;
}

.article-wrap {
  padding: 18px 24px 30px;
}

.tag {
  display: inline-block;
  margin: 10px 0 16px;
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--brand-soft);
  color: var(--brand);
  font-size: 12px;
}

.back {
  display: inline-block;
  margin-top: 20px;
  color: var(--brand);
  text-decoration: none;
}

.back:hover { text-decoration: underline; }
"""


def log(message):
    print(f"[LOG] {message}", flush=True)


def ensure_dirs():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    SITE_ARTICLE_DIR.mkdir(parents=True, exist_ok=True)


def safe_filename(title):
    cleaned = re.sub(r'[\\/:*?"<>|]', "_", title).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:80] if cleaned else "article"


def make_slug(title, url):
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    return f"{safe_filename(title)}_{digest}"


def article_key(article):
    url = (article.get("url") or "").strip()
    if url:
        return f"url::{url}"

    title = (article.get("title") or "").strip()
    time_text = (article.get("time") or "").strip()
    return f"title_time::{title}::{time_text}"


def load_history():
    if not HISTORY_FILE.exists():
        log("article.json not found, start with empty history.")
        return []

    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        log("article.json is not a list, fallback to empty history.")
        return []
    except Exception:
        log("Failed to read article.json, fallback to empty history.")
        traceback.print_exc()
        return []


def save_history(data):
    HISTORY_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def fetch_with_retry(url):
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            log(f"Request: {url} ({attempt}/{RETRY_COUNT})")
            response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            response.encoding = response.apparent_encoding or response.encoding
            response.raise_for_status()
            return response
        except Exception as exc:
            log(f"Request failed: {exc}")
            if attempt == RETRY_COUNT:
                raise
            time.sleep(RETRY_DELAY_SECONDS)

    raise RuntimeError(f"Request failed after retries: {url}")


def extract_content_html(detail_html):
    soup = BeautifulSoup(detail_html, "html.parser")
    node = soup.select_one(ARTICLE_SELECTOR)
    if not node:
        return FALLBACK_CONTENT_HTML
    return str(node)


def build_article_page(article):
    title = html.escape(article.get("title", ""))
    time_text = html.escape(article.get("time", ""))
    source_url = html.escape(article.get("url", ""))
    content_html = article.get("content_html") or FALLBACK_CONTENT_HTML

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <link rel="stylesheet" href="../styles.css">
</head>
<body>
  <main class="wrap">
    <section class="panel">
      <header class="header">
        <h1 class="title">{title}</h1>
        <p class="desc">抓取时间标记：{time_text}</p>
        <span class="tag">正文容器：{ARTICLE_SELECTOR}</span>
        <p class="desc">原始来源：<a href="{source_url}" target="_blank" rel="noopener noreferrer">{source_url}</a></p>
      </header>
      <article class="article-wrap">
        {content_html}
        <a class="back" href="../index.html">返回文章列表</a>
      </article>
    </section>
  </main>
</body>
</html>
"""


def build_index_page(history):
    cards = []
    for article in history:
        title = html.escape(article.get("title", ""))
        time_text = html.escape(article.get("time", ""))
        article_link = html.escape(article.get("site_file", "index.html"))
        source_url = html.escape(article.get("url", ""))

        cards.append(
            f"""<li class="item">
  <a href="{article_link}">{title}</a>
  <p class="meta">时间：{time_text}</p>
  <p class="meta">来源：<a href="{source_url}" target="_blank" rel="noopener noreferrer">{source_url}</a></p>
</li>"""
        )

    cards_html = "\n".join(cards) if cards else '<li class="item">暂无文章数据</li>'

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>期货观点文章汇总</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <main class="wrap">
    <section class="panel">
      <header class="header">
        <h1 class="title">期货观点文章汇总</h1>
        <p class="desc">自动抓取 + 自动更新静态站点</p>
      </header>
      <ul class="list">
        {cards_html}
      </ul>
    </section>
  </main>
</body>
</html>
"""


def ensure_history_shape(history):
    normalized = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for item in history:
        title = (item.get("title") or "").strip()
        time_text = (item.get("time") or "").strip()
        url = (item.get("url") or "").strip()
        slug = item.get("slug")
        if not slug:
            slug_seed = url or f"{title}-{time_text}-{len(normalized)}"
            slug = make_slug(title or "article", slug_seed)

        site_file = item.get("site_file") or f"articles/{slug}.html"
        raw_file = item.get("raw_file") or ""
        content_html = item.get("content_html") or FALLBACK_CONTENT_HTML

        normalized.append(
            {
                "title": title,
                "time": time_text,
                "url": url,
                "slug": slug,
                "raw_file": raw_file,
                "site_file": site_file,
                "content_html": content_html,
                "updated_at": item.get("updated_at") or now_iso,
            }
        )

    return normalized


def render_site(history):
    (SITE_DIR / "styles.css").write_text(STYLES_CSS, encoding="utf-8")
    (SITE_DIR / "index.html").write_text(build_index_page(history), encoding="utf-8")

    for article in history:
        page_path = SITE_DIR / article["site_file"]
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_text(build_article_page(article), encoding="utf-8")


def parse_list_items(list_html):
    soup = BeautifulSoup(list_html, "html.parser")
    items = soup.select("div.list-con ul li")
    log(f"List items found: {len(items)}")
    parsed = []

    for index, li in enumerate(items, start=1):
        title_tag = li.select_one("span.arc-title a.news-link")
        time_tag = li.select_one("span.arc-title span")

        if not title_tag or not time_tag:
            log(f"Skip malformed list item #{index}")
            continue

        title = (title_tag.get("title") or title_tag.get_text(strip=True) or "").strip()
        href = (title_tag.get("href") or "").strip()
        time_text = time_tag.get_text(strip=True)

        if not title or not href:
            log(f"Skip empty list item #{index}")
            continue

        url = urljoin(BASE_URL, href)
        parsed.append({"title": title, "time": time_text, "url": url})

    return parsed


def crawl_new_articles(history):
    list_resp = fetch_with_retry(BASE_URL)
    list_items = parse_list_items(list_resp.text)

    existing_keys = {article_key(item) for item in history}
    new_articles = []

    for item in list_items:
        key = article_key(item)
        if key in existing_keys:
            continue

        title = item["title"]
        url = item["url"]
        time_text = item["time"]

        try:
            detail_resp = fetch_with_retry(url)
            slug = make_slug(title, url)
            raw_path = RAW_DIR / f"{slug}.html"
            raw_path.write_text(detail_resp.text, encoding="utf-8")
            content_html = extract_content_html(detail_resp.text)

            article = {
                "title": title,
                "time": time_text,
                "url": url,
                "slug": slug,
                "raw_file": raw_path.as_posix(),
                "site_file": f"articles/{slug}.html",
                "content_html": content_html,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            new_articles.append(article)
            existing_keys.add(key)

            log(f"Saved raw and extracted content: {title}")
            time.sleep(REQUEST_INTERVAL_SECONDS)

        except Exception:
            log(f"Failed to process article: {title}")
            traceback.print_exc()
            continue

    return new_articles


def main():
    ensure_dirs()

    history = ensure_history_shape(load_history())
    new_articles = crawl_new_articles(history)

    if new_articles:
        history = new_articles + history
        log(f"New articles: {len(new_articles)}")
    else:
        log("No new articles.")

    save_history(history)
    render_site(history)
    log("Static site generated in docs/.")


if __name__ == "__main__":
    main()
