#!/usr/bin/env python3
"""かんたんフロントマニュアルのサイト内検索インデックスを作る。

使い方（どのディレクトリからでも可）:
    python case-study/araki-smart-manual/scripts/build_search_index.py

- 各ページを h2 / h3 ごとの節に分け、assets/search-index.json に書き出す。
- 本文テキストには figcaption（画像のキャプション）も含む。1節6,000字で打ち切る。
- すべての h2 / h3 に id が必要（検索結果はその id へ直接リンクする）。id の無い見出しがあるとエラーで止まる。
- 翻訳版（en/*.html など。TRANSLATIONS 参照）も同じように assets/search-index-<言語>.json に書き出す。
  翻訳版のページの検索はこちらを使う。

- 最後に、全ページの assets/*.css・search.js への参照に ?v=内容のハッシュ を付け直す（ブラウザに古い
  CSS・JS・検索データが残って、公開直後に古い検索結果が出るのを防ぐ。search.js は自分の ?v= を検索データの取得にも付ける）。

運用ルール: ページを更新したら必ずこのスクリプトを再実行し、
assets/search-index.json も同じ commit に含めること。
Python 3 の標準ライブラリだけで動く。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "assets" / "search-index.json"
MAX_TEXT = 6000

# 検索結果の並び（同点のとき）はこの順。index.html は他ページへのリンク集なので対象外。
PAGES = [
    ("daily-operations.html", "1日の業務"),
    ("reservation-guide.html", "予約・会計"),
    ("room-assignment.html", "部屋割り"),
    ("service-operations.html", "客室・清掃"),
    ("troubleshooting.html", "困ったとき"),
    ("front-operations.html", "フロント運用"),
    ("startup.html", "初期設定"),
    ("quick-reference.html", "早見表"),
    ("glossary.html", "用語集"),
    ("HOTEL-SMART-front-manual-reference.html", "公式資料との対応"),
]

# 翻訳版：言語コード → ページ一覧（<言語>/ の同じファイル名。見出しの id も日本語版と同じ）
PAGES_EN = [
    ("daily-operations.html", "Daily tasks"),
    ("reservation-guide.html", "Reservations & billing"),
    ("room-assignment.html", "Room assignment"),
    ("service-operations.html", "Rooms & cleaning"),
    ("troubleshooting.html", "Troubleshooting"),
    ("front-operations.html", "Front desk operations"),
    ("startup.html", "Initial setup"),
    ("quick-reference.html", "Quick reference"),
    ("glossary.html", "Glossary"),
    ("HOTEL-SMART-front-manual-reference.html", "Official documents map"),
]
TRANSLATIONS = {"en": PAGES_EN}

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
BLOCK = {"p", "div", "li", "ul", "ol", "td", "th", "tr", "table", "figcaption", "figure", "section",
         "dt", "dd", "dl", "br", "h1", "h2", "h3", "h4", "aside", "blockquote", "header", "main"}


def classes(attrs: dict) -> set[str]:
    return set((attrs.get("class") or "").split())


def should_skip(tag: str, attrs: dict) -> bool:
    """検索対象にしない要素（ナビ、ヘッダー、フッター、検索フォーム、拡大の案内など）。"""
    c = classes(attrs)
    if tag in ("script", "style", "nav", "footer", "form", "template", "noscript"):
        return True
    if tag == "header" and "site-header" in c:
        return True
    if "manual-topbar" in c or "zoom-hint" in c or "skip-link" in c:
        return True
    return False


class SectionParser(HTMLParser):
    def __init__(self, page: str):
        super().__init__(convert_charrefs=True)
        self.page = page
        self.sections: list[dict] = []
        self.current: dict | None = None
        self.skip_depth = 0
        self.heading: dict | None = None  # 見出しの読み取り中
        self.in_scene_num = 0
        self.span_stack: list[bool] = []
        self.errors: list[str] = []

    # --- helpers ---
    def _text(self, s: str) -> None:
        if self.heading is not None:
            if self.in_scene_num:
                self.heading["num"] += s
            else:
                self.heading["text"] += s
        elif self.current is not None:
            self.current["parts"].append(s)

    def handle_starttag(self, tag, attrs_list):
        attrs = dict(attrs_list)
        if self.skip_depth:
            if tag not in VOID:
                self.skip_depth += 1
            return
        if should_skip(tag, attrs):
            if tag not in VOID:
                self.skip_depth = 1
            return
        if tag in ("h2", "h3"):
            anchor = attrs.get("id")
            if not anchor:
                self.errors.append(f"{self.page}: id の無い <{tag}> があります")
            self.heading = {"tag": tag, "anchor": anchor or "", "text": "", "num": ""}
            return
        if self.heading is not None and tag == "span" and "scene-num" in classes(attrs):
            self.in_scene_num = 1
            return
        if self.in_scene_num and tag not in VOID:
            self.in_scene_num += 1
        if tag == "span":
            # 囲みのラベル（<span class="label">注意</span>本文…）は本文とくっつかないよう区切る
            is_label = "label" in classes(attrs)
            self.span_stack.append(is_label)
            if is_label:
                self._text(" ")
        if tag in BLOCK:
            self._text(" ")

    def handle_startendtag(self, tag, attrs_list):
        if not self.skip_depth and tag in BLOCK:
            self._text(" ")

    def handle_endtag(self, tag):
        if self.skip_depth:
            self.skip_depth -= 1
            return
        if self.heading is not None and tag == self.heading["tag"]:
            h = self.heading
            self.heading = None
            text = squash(h["text"])
            num = squash(h["num"])
            heading = f"{num}. {text}" if num else text
            self.current = {"anchor": h["anchor"], "heading": heading, "parts": []}
            self.sections.append(self.current)
            return
        if self.in_scene_num:
            self.in_scene_num -= 1
            return
        if tag == "span" and self.span_stack and self.span_stack.pop():
            self._text(" ")
        if tag in BLOCK:
            self._text(" ")

    def handle_data(self, data):
        if not self.skip_depth:
            self._text(data)


def squash(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def build(pages=PAGES, base: Path = ROOT) -> list[dict]:
    entries: list[dict] = []
    errors: list[str] = []
    for page, title in pages:
        parser = SectionParser(page)
        parser.feed((base / page).read_text(encoding="utf-8"))
        parser.close()
        errors += parser.errors
        seen = set()
        for s in parser.sections:
            if s["anchor"] in seen:
                errors.append(f"{page}: id が重複しています: {s['anchor']}")
            seen.add(s["anchor"])
            text = squash("".join(s["parts"]))[:MAX_TEXT]
            entries.append({"page": page, "pageTitle": title, "anchor": s["anchor"],
                            "heading": s["heading"], "text": text})
    if errors:
        sys.exit("\n".join(errors))
    return entries


def write(entries: list[dict], output: Path, n_pages: int) -> None:
    body = ",\n".join(json.dumps(e, ensure_ascii=False) for e in entries)
    output.write_text("[\n" + body + "\n]\n", encoding="utf-8", newline="\n")
    print(f"{output.relative_to(ROOT)}: {len(entries)} sections from {n_pages} pages")


def file_hash(*paths: Path) -> str:
    h = hashlib.sha256()
    for p in paths:
        if p.exists():
            h.update(p.read_bytes())
    return h.hexdigest()[:10]


def stamp_versions() -> None:
    """ページから assets の CSS・JS への参照に ?v=ハッシュ を付ける（内容が変わったときだけ URL が変わる）。"""
    assets = ROOT / "assets"
    versions = {
        "manual.css": file_hash(assets / "manual.css"),
        "search.css": file_hash(assets / "search.css"),
        # 検索データ（JSON）が変わったときも search.js の URL を変え、search.js がその v を JSON の取得に付ける
        "search.js": file_hash(assets / "search.js", *sorted(assets.glob("*.json"))),
    }
    ref = re.compile(r'((?:\.\./)?assets/(manual\.css|search\.css|search\.js))(?:\?v=[0-9a-f]+)?"')
    pages = list(ROOT.glob("*.html")) + [p for lang in TRANSLATIONS for p in (ROOT / lang).glob("*.html")]
    for page in pages:
        html = page.read_text(encoding="utf-8")
        new = ref.sub(lambda m: f'{m.group(1)}?v={versions[m.group(2)]}"', html)
        if new != html:
            page.write_text(new, encoding="utf-8", newline="\n")


def main() -> None:
    write(build(), OUTPUT, len(PAGES))
    for lang, pages in TRANSLATIONS.items():
        write(build(pages, ROOT / lang), ROOT / "assets" / f"search-index-{lang}.json", len(pages))
    stamp_versions()


if __name__ == "__main__":
    main()
