#!/usr/bin/env python3
"""日本語版と翻訳版（英語 en/ など）のずれを、見出しの id ごとに調べる。

使い方（どのディレクトリからでも可。--lang を省くと全言語）:
    python case-study/araki-smart-manual/scripts/translation_status.py            # 訳し直しが要る節の一覧
    python case-study/araki-smart-manual/scripts/translation_status.py --lang en --mark ページ.html#見出しid [...]
    python case-study/araki-smart-manual/scripts/translation_status.py --lang en --mark ページ.html   # ページ全体
    python case-study/araki-smart-manual/scripts/translation_status.py --check     # ずれがあれば終了コード1

- 日本語ページを h2 / h3 ごとの節（最初の見出しより前は「(top)」）に分け、本文の指紋（ハッシュ）を取る。
- <言語>/translation-sources.json には「英訳したときの日本語の指紋」が入っている。今の日本語と違う節が「訳し直しが要る節」。
- 翻訳版のページに同じ id の見出しがあるかも調べる（足りない id・余分な id）。
- 節を英訳し直したら --mark で指紋を記録し、build_search_index.py で検索インデックスも作り直す。

Python 3 の標準ライブラリだけで動く。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_search_index import ROOT, TRANSLATIONS, SectionParser, squash  # noqa: E402

TOP = "(top)"


def sources_path(lang: str) -> Path:
    return ROOT / lang / "translation-sources.json"


class AllSectionsParser(SectionParser):
    """最初の見出しより前の本文（ページの導入）も「(top)」として拾う。"""

    def __init__(self, page: str):
        super().__init__(page)
        self.current = {"anchor": TOP, "heading": "", "parts": []}
        self.sections.append(self.current)


def sections(path: Path) -> dict[str, str]:
    """{id: 見出し＋本文} を返す。"""
    parser = AllSectionsParser(path.name)
    parser.feed(path.read_text(encoding="utf-8"))
    parser.close()
    return {s["anchor"]: squash(s["heading"] + " " + "".join(s["parts"])) for s in parser.sections}


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def load_sources(lang: str) -> dict[str, dict[str, str]]:
    if sources_path(lang).exists():
        return json.loads(sources_path(lang).read_text(encoding="utf-8"))
    return {}


def save_sources(lang: str, data: dict) -> None:
    ordered = {p: dict(sorted(data[p].items())) for p in sorted(data)}
    sources_path(lang).write_text(json.dumps(ordered, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


def mark(lang: str, targets: list[str]) -> None:
    data = load_sources(lang)
    for t in targets:
        page, _, anchor = t.partition("#")
        page = Path(page).name
        ja = sections(ROOT / page)
        rec = data.setdefault(page, {})
        if anchor:
            if anchor not in ja:
                sys.exit(f"{page}: 日本語版に id「{anchor}」の節がありません")
            rec[anchor] = fingerprint(ja[anchor])
        else:
            data[page] = {a: fingerprint(t) for a, t in ja.items()}
        print(f"記録: {lang}/{t}")
    save_sources(lang, data)


def report(lang: str) -> int:
    data = load_sources(lang)
    problems = 0
    for page, _title in TRANSLATIONS[lang]:
        ja_path, en_path = ROOT / page, ROOT / lang / page
        if not en_path.exists():
            print(f"{lang}/{page}: 翻訳版がありません（scripts/make_lang_page.py --lang {lang} {page} で作る）")
            problems += 1
            continue
        ja = sections(ja_path)
        en_ids = set(sections(en_path))
        rec = data.get(page, {})
        stale = [a for a in ja if a in rec and rec[a] != fingerprint(ja[a])]
        new = [a for a in ja if a not in rec]
        missing = [a for a in ja if a not in en_ids]
        extra = [a for a in en_ids if a not in ja]
        removed = [a for a in rec if a not in ja]
        lines = []
        if stale:
            lines.append("  日本語が変わった節（訳し直す）: " + ", ".join(stale))
        if new:
            lines.append("  まだ訳していない節: " + ", ".join(new))
        if missing:
            lines.append("  翻訳版に無い見出し id: " + ", ".join(missing))
        if extra:
            lines.append("  翻訳版にだけある見出し id（日本語版で消えた？）: " + ", ".join(sorted(extra)))
        if removed:
            lines.append("  記録にあるが日本語版に無い id（--mark ページ.html で記録を作り直す）: " + ", ".join(removed))
        if lines:
            problems += 1
            print(f"{lang}/{page}:")
            print("\n".join(lines))
    if not problems:
        print(f"{lang}: 日本語版と揃っています")
    return problems


def main(argv: list[str]) -> None:
    lang = None
    if "--lang" in argv:
        i = argv.index("--lang")
        lang = argv[i + 1] if i + 1 < len(argv) else None
        argv = argv[:i] + argv[i + 2:]
        if lang not in TRANSLATIONS:
            sys.exit(f"--lang は {', '.join(TRANSLATIONS)} のどれか")
    if "--mark" in argv:
        targets = [a for a in argv if not a.startswith("--")]
        if not lang or not targets:
            sys.exit("--lang 言語 --mark のあとに ページ.html または ページ.html#見出しid を指定してください")
        mark(lang, targets)
        return
    problems = sum(report(code) for code in ([lang] if lang else TRANSLATIONS))
    if "--check" in argv and problems:
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
