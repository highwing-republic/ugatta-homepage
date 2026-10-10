#!/usr/bin/env python3
"""かんたんフロントマニュアルのサイト内検索インデックスを作る。

使い方（どのディレクトリからでも可）:
    python case-study/araki-smart-manual/scripts/build_search_index.py

- 各ページを h2 / h3 ごとの節に分け、assets/search-index.json に書き出す。
- 本文テキストには figcaption（画像のキャプション）も含む。1節6,000字で打ち切る。
- すべての h2 / h3 に id が必要（検索結果はその id へ直接リンクする）。id の無い見出しがあるとエラーで止まる。

運用ルール: ページを更新したら必ずこのスクリプトを再実行し、
assets/search-index.json も同じ commit に含めること。
Python 3 の標準ライブラリだけで動く。
"""
from __future__ import annotations

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


def build() -> list[dict]:
    entries: list[dict] = []
    errors: list[str] = []
    for page, title in PAGES:
        parser = SectionParser(page)
        parser.feed((ROOT / page).read_text(encoding="utf-8"))
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


def main() -> None:
    entries = build()
    body = ",\n".join(json.dumps(e, ensure_ascii=False) for e in entries)
    OUTPUT.write_text("[\n" + body + "\n]\n", encoding="utf-8", newline="\n")
    print(f"{OUTPUT.relative_to(ROOT)}: {len(entries)} sections from {len(PAGES)} pages")


if __name__ == "__main__":
    main()
