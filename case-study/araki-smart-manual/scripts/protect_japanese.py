#!/usr/bin/env python3
"""翻訳版ページ（en/ など）の日本語（画面のボタン名・メニュー名、公式の記事名）を、ブラウザの自動翻訳から守る。

使い方（どのディレクトリからでも可）:
    python case-study/araki-smart-manual/scripts/protect_japanese.py

- 英語版を Chrome / Edge の「翻訳」でミャンマー語などに訳して読むとき、【売上管理】のような日本語の画面名まで
  訳されると、実際の画面で探せなくなる。そこで本文中の日本語を <span translate="no" lang="ja">…</span> で囲む。
  （括弧つきの【…】「…」なども、括弧ごと囲む。）
- 何度実行しても同じ結果になる（すでに囲んである所はそのまま）。翻訳版を直したら実行し、検索インデックスも作り直す。
- <title>・<style>・<script> の中と、属性の値と、言語の切り替えリンクは変えない。

Python 3 の標準ライブラリだけで動く。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_search_index import ROOT, TRANSLATIONS  # noqa: E402

OPEN = '<span translate="no" lang="ja">'
JA_CHARS = r"々぀-ヿ一-鿿！-～・ー〜"
BRACKETS = r"[【「『〖［《][^】」』〗］》<]*[】」』〗］》]"
RUN = rf"[{JA_CHARS}]+(?:[0-9A-Za-z_ ]*[{JA_CHARS}]+)*"
JA = re.compile(rf"{BRACKETS}|{RUN}")
# 本文のテキスト部分（タグとタグの間）。<title>/<style>/<script> は丸ごと飛ばす。
SKIP_BLOCK = re.compile(r"<(title|style|script)\b.*?</\1>", re.S | re.I)
TAG = re.compile(r"<[^>]+>")


def protect(html: str) -> str:
    out = []
    pos = 0
    for m in SKIP_BLOCK.finditer(html):
        out.append(protect_part(html[pos:m.start()]))
        out.append(m.group(0))
        pos = m.end()
    out.append(protect_part(html[pos:]))
    return "".join(out)


def protect_part(html: str) -> str:
    out = []
    pos = 0
    prev_tag = ""
    for m in TAG.finditer(html):
        out.append(wrap(html[pos:m.start()], prev_tag))
        out.append(m.group(0))
        prev_tag = m.group(0)
        pos = m.end()
    out.append(wrap(html[pos:], prev_tag))
    return "".join(out)


def wrap(text: str, prev_tag: str) -> str:
    if not text or prev_tag == OPEN or "data-lang-switch" in prev_tag:
        return text
    return JA.sub(lambda m: OPEN + m.group(0) + "</span>", text)


def main() -> None:
    changed = 0
    for lang in TRANSLATIONS:
        for path in sorted((ROOT / lang).glob("*.html")):
            html = path.read_text(encoding="utf-8")
            new = protect(html)
            if new != html:
                path.write_text(new, encoding="utf-8", newline="\n")
                changed += 1
                print(f"更新: {lang}/{path.name}")
    print(f"{changed} ファイルを更新しました")


if __name__ == "__main__":
    main()
