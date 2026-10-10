#!/usr/bin/env python3
"""HOTEL SMART 公式オンラインマニュアルの記事一覧を、サイト内検索用の索引に取り込む。

使い方（どのディレクトリからでも可）:
    python case-study/araki-smart-manual/scripts/import_official_index.py 記事一覧.html
    python case-study/araki-smart-manual/scripts/import_official_index.py 記事一覧.txt

- 入力は、公式サイトの記事一覧ページをブラウザで「名前を付けて保存」した HTML か、
  一覧をコピーして貼り付けたテキスト。
  - HTML：公式サイト（pms-manual.xxxaz.jp）へのリンクを記事として拾い、直前の見出しをカテゴリにする。
    /category/… へのリンク（メニューのカテゴリ）は「カテゴリ一覧」として取り込む（親カテゴリがあればそれをカテゴリ名にする）。
    トップページ（/）を保存したものではカテゴリだけ、マニュアル一覧（/manual）を保存したものでは記事も取り込める。
  - JSON：公式サイトの WordPress REST API をブラウザで開いて保存したもの。
      https://pms-manual.xxxaz.jp/wp-json/wp/v2/categories?per_page=100
      https://pms-manual.xxxaz.jp/wp-json/wp/v2/posts?per_page=100&page=1 （page=2 も）
    posts の各記事を、categories の名前（親カテゴリがあれば「親 › 子」）付きで取り込む。
  - 複数のファイルを渡すと、まとめて1つの索引にする（categories の JSON を先に渡す）。
  - テキスト：URL を含む行を「記事名 URL」、URL を含まない行をカテゴリ名として読む。
- assets/official-manual-index.json に {category, title, url} の一覧を書き出す。
  記事の本文は取り込まない（タイトルとリンクだけ。本文の転載は許諾が無いため）。

Python 3 の標準ライブラリだけで動く。
"""
from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "assets" / "official-manual-index.json"
HOST = "pms-manual.xxxaz.jp"
BASE = f"https://{HOST}/"
URL_RE = re.compile(r"https?://[^\s<>\"'）)]+")


def squash(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


SKIP_PATHS = ("/wp-", "/feed", "/comments", "/tag/", "/author/", "/xmlrpc", "/news")


def is_article(url: str) -> bool:
    u = urlparse(url)
    return u.netloc == HOST and u.path not in ("", "/") and not u.path.startswith(SKIP_PATHS)


def category_of(url: str) -> str | None:
    """/category/親/子 → 親、/category/親 → 「カテゴリ一覧」。カテゴリページでなければ None。"""
    parts = [unquote(x) for x in urlparse(url).path.strip("/").split("/")]
    if len(parts) < 2 or parts[0] != "category":
        return None
    return parts[1] if len(parts) >= 3 else "カテゴリ一覧"


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items: list[dict] = []
        self.category = ""
        self.heading: str | None = None
        self.link: dict | None = None
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style", "footer"):
            self.skip += 1
        elif tag in ("h1", "h2", "h3", "h4") and not self.skip:
            self.heading = ""
        elif tag == "a" and not self.skip:
            href = urljoin(BASE, a.get("href") or "")
            if is_article(href):
                self.link = {"url": href.split("#")[0], "text": ""}

    def handle_endtag(self, tag):
        if tag in ("script", "style", "footer") and self.skip:
            self.skip -= 1
        elif tag in ("h1", "h2", "h3", "h4") and self.heading is not None:
            text = squash(self.heading)
            if text and not self.link:
                self.category = text
            self.heading = None
        elif tag == "a" and self.link:
            title = squash(self.link["text"])
            cat = category_of(self.link["url"])
            if title:
                self.items.append({"category": cat or self.category, "title": title, "url": self.link["url"]})
            self.link = None

    def handle_data(self, data):
        if self.link is not None:
            self.link["text"] += data
        elif self.heading is not None:
            self.heading += data


def from_html(text: str) -> list[dict]:
    p = LinkParser()
    p.feed(text)
    p.close()
    return p.items


def from_text(text: str) -> list[dict]:
    items, category = [], ""
    for line in text.splitlines():
        line = squash(line)
        if not line:
            continue
        m = URL_RE.search(line)
        if not m:
            category = line.strip("#【】[]■●・ ")
            continue
        title = squash(line.replace(m.group(0), "")).strip("-–:：|｜ ")
        if title and is_article(m.group(0)):
            items.append({"category": category, "title": title, "url": m.group(0)})
    return items


def strip_tags(s: str) -> str:
    import html as _html
    return squash(_html.unescape(re.sub(r"<[^>]+>", " ", s)))


WP_CATEGORIES: dict[int, dict] = {}


def wp_category_name(cid: int) -> str:
    c = WP_CATEGORIES.get(cid)
    if not c:
        return ""
    parent = WP_CATEGORIES.get(c.get("parent") or 0)
    return f"{parent['name']} › {c['name']}" if parent else c["name"]


def from_json(data) -> list[dict]:
    """WordPress REST API の categories / posts の JSON。"""
    items: list[dict] = []
    if not isinstance(data, list):
        return items
    for o in data:
        if not isinstance(o, dict) or "link" not in o:
            continue
        if "parent" in o and "count" in o and "title" not in o:  # categories
            WP_CATEGORIES[o["id"]] = {"name": strip_tags(o.get("name", "")), "parent": o.get("parent", 0)}
            continue
        title = o.get("title")
        title = strip_tags(title.get("rendered", "")) if isinstance(title, dict) else strip_tags(str(title or ""))
        if not title or not is_article(o["link"]):
            continue
        cats = [wp_category_name(c) for c in (o.get("categories") or [])]
        cats = [c for c in cats if c]
        items.append({"category": " / ".join(cats), "title": title, "url": o["link"]})
    return items


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    seen, out = set(), []
    for arg in sys.argv[1:]:
        src = Path(arg)
        text = src.read_text(encoding="utf-8", errors="replace")
        if text.lstrip().startswith("["):
            items = from_json(json.loads(text))
            if not items:  # categories だけのファイルは、記事を出さない
                continue
        elif "<a " in text.lower():
            items = from_html(text)
        else:
            items = from_text(text)
        n = 0
        for it in items:
            if it["url"] in seen:
                continue
            seen.add(it["url"])
            out.append(it)
            n += 1
        if not n:
            sys.exit(f"{src}: {HOST} の記事へのリンクが見つかりませんでした")
    # 子カテゴリの親は URL の slug（例：settings）なので、親カテゴリページの表示名に置き換える
    by_path = {urlparse(e["url"]).path.strip("/"): e["title"] for e in out}
    for e in out:
        parts = [unquote(x) for x in urlparse(e["url"]).path.strip("/").split("/")]
        if len(parts) >= 3 and parts[0] == "category":
            e["category"] = by_path.get("/".join(urlparse(e["url"]).path.strip("/").split("/")[:2]), e["category"])
        elif not e["category"] and category_of(e["url"]) is None and urlparse(e["url"]).path.count("/") <= 1:
            e["category"] = "ガイド"
    # 記事を先、カテゴリページを後ろに（同点の検索結果で記事が上に来るように）
    out.sort(key=lambda e: category_of(e["url"]) is not None)
    body = ",\n".join(json.dumps(e, ensure_ascii=False) for e in out)
    OUTPUT.write_text("[\n" + body + "\n]\n", encoding="utf-8", newline="\n")
    cats = len({e["category"] for e in out})
    print(f"{OUTPUT.relative_to(ROOT)}: {len(out)} 記事（{cats} カテゴリ）")


if __name__ == "__main__":
    main()
