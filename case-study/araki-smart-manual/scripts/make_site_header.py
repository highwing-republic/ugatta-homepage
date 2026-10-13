"""全ページ（日本語版・翻訳版）のヘッダーを同じ物にそろえる。

- <header class="site-header">…</header>（無ければ旧 .manual-topbar の帯）を、ブランド＋主要メニュー＋言語切替＋検索の
  共通ヘッダーに置き換える。言語切替（.lang-switch）と検索フォーム（form[data-site-search]）は、ページにある物をそのまま使う。
- <head> に assets/shell.css（配色・書体・ヘッダーの共通CSS）とフォント読み込みを入れる。
- ページを足したとき・メニューを変えたときは、これを実行してから build_search_index.py を実行する。

    python case-study/araki-smart-manual/scripts/make_site_header.py
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGS = {"": "ja", "en": "en"}  # サブフォルダ → 言語

NAV = {
    "ja": [
        ("daily-operations.html", "1日の業務"),
        ("reservation-guide.html", "予約・会計"),
        ("room-assignment.html", "部屋割り"),
        ("service-operations.html", "客室・清掃"),
        ("troubleshooting.html", "困ったとき"),
        ("glossary.html", "用語集"),
        ("quick-reference.html", "早見表"),
        ("how-to-use.html", "使い方"),
    ],
    "en": [
        ("daily-operations.html", "Daily tasks"),
        ("reservation-guide.html", "Reservations &amp; billing"),
        ("room-assignment.html", "Room assignment"),
        ("service-operations.html", "Rooms &amp; cleaning"),
        ("troubleshooting.html", "Troubleshooting"),
        ("glossary.html", "Glossary"),
        ("quick-reference.html", "Quick reference"),
        ("how-to-use.html", "How to use"),
    ],
}
BRAND = {"ja": ("あらきホテル", "かんたんフロントマニュアル"), "en": ("Araki Hotel", "Front Desk Quick Manual")}
NAV_LABEL = {"ja": "主要メニュー", "en": "Main menu"}
SKIP = {"ja": "本文へ移動", "en": "Skip to main content"}
FONT = '<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&display=swap" rel="stylesheet">'

HEADER_RE = re.compile(r'<header class="site-header[^"]*">.*?</header>', re.S)
TOPBAR_RE = re.compile(r'<div class="manual-topbar">.*?</div>\n?', re.S)
SKIP_RE = re.compile(r'\s*<a class="skip-link"[^>]*>[^<]*</a>')
LANG_RE = re.compile(r'<span class="lang-switch".*?</span>', re.S)
FORM_RE = re.compile(r'<form class="site-search[^"]*"[^>]*data-site-search>.*?</form>', re.S)


def header_html(lang: str, page: str, lang_switch: str, form: str) -> str:
    name, sub = BRAND[lang]
    prefix = "" if lang == "ja" else "../"
    links = "".join(
        f'<a{" aria-current=\"page\"" if f == page else ""} href="{f}">{label}</a>' for f, label in NAV[lang]
    )
    return (
        f'<header class="site-header"><div class="header-inner">'
        f'<a class="brand" href="index.html"><img class="brand-mark" src="{prefix}assets/logo-araki.svg" alt="" width="52" height="80"><span>{name}<small>{sub}</small></span></a>'
        f'<nav class="global-nav" aria-label="{NAV_LABEL[lang]}">{links}</nav>'
        f'{lang_switch}{form}</div></header>'
    )


def update(path: Path, lang: str) -> bool:
    html = path.read_text(encoding="utf-8")
    old = html
    m = HEADER_RE.search(html) or TOPBAR_RE.search(html)
    if not m:
        return False
    block = m.group(0)
    lang_switch = (LANG_RE.search(block) or LANG_RE.search(html))
    form = FORM_RE.search(block) or FORM_RE.search(html)
    new_header = header_html(lang, path.name, lang_switch.group(0) if lang_switch else "", form.group(0) if form else "")
    html = html[: m.start()] + new_header + ("\n" if block.endswith("\n") else "") + html[m.end():]
    # 本文へのスキップリンク（ヘッダーの直前）
    html = SKIP_RE.sub("", html, count=1)
    html = html.replace("<body>", f'<body>\n<a class="skip-link" href="#main">{SKIP[lang]}</a>', 1)
    if 'id="main"' not in html:
        html = re.sub(r"<main(?![^>]*\bid=)", '<main id="main"', html, count=1)
    # シーン別ページの重複した戻るリンク（ブランドのリンクと同じ）
    html = re.sub(r'\s*<a class="backlink" href="\./index\.html">[^<]*</a>', "", html, count=1)
    # 共通CSSと明朝体
    html = re.sub(r'<link href="https://fonts\.googleapis\.com/css2\?family=[^"]*" rel="stylesheet">', FONT, html, count=1)
    prefix = "../" if lang != "ja" else ""
    if not re.search(r'href="(\.\./)?assets/shell\.css', html):
        html = re.sub(r'(<link rel="stylesheet")', f'<link rel="stylesheet" href="{prefix}assets/shell.css">\\1', html, count=1)
    if html != old:
        path.write_text(html, encoding="utf-8", newline="\n")
        return True
    return False


def main() -> None:
    n = 0
    for sub, lang in LANGS.items():
        for page in sorted((ROOT / sub).glob("*.html")):
            if update(page, lang):
                n += 1
                print("header:", page.relative_to(ROOT))
    print(f"{n} ファイルを更新しました")


if __name__ == "__main__":
    main()
