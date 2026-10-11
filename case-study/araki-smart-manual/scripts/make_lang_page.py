#!/usr/bin/env python3
"""翻訳版ページ（英語 en/、ミャンマー語 my/ など）の下書きを作り、言語の切り替えリンクを付ける。

使い方（どのディレクトリからでも可）:
    python case-study/araki-smart-manual/scripts/make_lang_page.py --lang en ページ.html [...]
    python case-study/araki-smart-manual/scripts/make_lang_page.py --switch-only   # 切り替えリンクだけ全ページに付け直す

- 日本語ページ（ページ.html）をもとに <言語>/ページ.html を作る。中身は日本語のままなので、このあと本文を訳す。
  すでにあるときは上書きしない（--force で上書き）。
- 翻訳版では lang="<言語>" にし、assets/ と screenshots/ への参照を ../ 付きに直す。
  ページ同士のリンク（daily-operations.html#checkin など）はそのまま＝同じ言語のページへ移動する。
- 各ページに、そのページがある他の言語への切り替えリンク（.lang-switch）と <link rel="alternate" hreflang> を付ける。
  言語を足したら --switch-only で全ページを付け直す。切り替えでは assets/search.js が今いる見出し（#id）を引き継ぐ。
- 見出しの id は日本語版と同じにする（id が言語間の対応づけと、訳し直しの単位になる。translation_status.py 参照）。

Python 3 の標準ライブラリだけで動く。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (言語コード, 切り替えリンクの表示, フォルダ)。日本語が元。翻訳版を足すときはここに加える。
LANGS = [
    ("ja", "日本語", ""),
    ("en", "English", "en/"),
    ("my", "မြန်မာ", "my/"),
]
TRANSLATED = [code for code, _label, folder in LANGS if folder]

SWITCH_RE = re.compile(r'\s*<span class="lang-switch"[^>]*>.*?</span>', re.S)
ALT_RE = re.compile(r'<link rel="alternate" hreflang="[^"]*" href="[^"]*">\s*')


def folder_of(code: str) -> str:
    return next(f for c, _l, f in LANGS if c == code)


def available(page: str) -> list[tuple[str, str, str]]:
    """このページがある言語（日本語＋翻訳済みのフォルダにあるもの）。"""
    return [(c, l, f) for c, l, f in LANGS if (ROOT / f / page).exists()]


def rel(from_code: str, to_folder: str, page: str) -> str:
    if to_folder == folder_of(from_code):
        return page
    up = "../" if folder_of(from_code) else ""
    return f"{up}{to_folder}{page}"


def add_switch(html: str, code: str, page: str) -> str:
    """切り替えリンクと hreflang を（付け直しも含めて）入れる。"""
    html = SWITCH_RE.sub("", html)
    html = ALT_RE.sub("", html)
    langs = available(page)
    others = [(c, l, f) for c, l, f in langs if c != code]
    if others:
        links = "".join(
            f'<a href="{rel(code, f, page)}" hreflang="{c}" lang="{c}" data-lang-switch>{l}</a>' for c, l, f in others)
        switch = f'<span class="lang-switch" role="group" aria-label="Language">{links}</span>'
        if '<header class="site-header' in html:
            # ヘッダー：グローバルナビの直後（検索ボックスの手前）
            nav_end = html.find("</nav>", html.index('<header class="site-header'))
            if nav_end == -1:
                raise SystemExit(f"{page}: site-header の </nav> が見つかりません")
            pos = nav_end + len("</nav>")
            html = html[:pos] + switch + html[pos:]
        elif '<div class="manual-topbar">' in html:
            pos = html.find("</a>", html.index('<div class="manual-topbar">')) + len("</a>")
            html = html[:pos] + "\n  " + switch + html[pos:]
        else:
            raise SystemExit(f"{page}: 切り替えリンクを置く場所（site-header / manual-topbar）がありません")
    alts = "".join(f'<link rel="alternate" hreflang="{c}" href="{rel(code, f, page)}">' for c, _l, f in langs)
    pos = html.index("</head>")
    return html[:pos] + alts + html[pos:]


def to_skeleton(html: str, code: str) -> str:
    html = re.sub(r'<html lang="ja">', f'<html lang="{code}">', html, count=1)
    # 画像・CSS・JS は日本語版と共用（<言語>/ から見て ../）
    return re.sub(r'((?:src|href)=")((?:assets|screenshots)/)', r"\1../\2", html)


def all_pages() -> list[tuple[str, str]]:
    """(言語コード, パス) の一覧。"""
    out = [("ja", p) for p in sorted(ROOT.glob("*.html"))]
    for code in TRANSLATED:
        out += [(code, p) for p in sorted((ROOT / folder_of(code)).glob("*.html"))]
    return out


def switch_all() -> None:
    for code, path in all_pages():
        path.write_text(add_switch(path.read_text(encoding="utf-8"), code, path.name), encoding="utf-8", newline="\n")


def main(argv: list[str]) -> None:
    if "--switch-only" in argv:
        switch_all()
        print("切り替えリンクを付け直しました")
        return
    force = "--force" in argv
    code = None
    args = []
    it = iter(argv)
    for a in it:
        if a == "--lang":
            code = next(it, None)
        elif not a.startswith("--"):
            args.append(a)
    if code not in TRANSLATED or not args:
        sys.exit(__doc__ + f"\n--lang は {', '.join(TRANSLATED)} のどれか")
    out_dir = ROOT / folder_of(code)
    out_dir.mkdir(exist_ok=True)
    for page in args:
        page = Path(page).name
        dst = out_dir / page
        if dst.exists() and not force:
            print(f"skip（既にあります）: {folder_of(code)}{page}")
            continue
        dst.write_text(to_skeleton((ROOT / page).read_text(encoding="utf-8"), code), encoding="utf-8", newline="\n")
        print(f"作成: {folder_of(code)}{page}（本文はまだ日本語です。訳してください）")
    switch_all()


if __name__ == "__main__":
    main(sys.argv[1:])
