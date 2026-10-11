"""各ページのフッターの更新日を、そのファイルが最後に変わった git の日付にそろえる。

- 日本語版の「更新：YYYY-MM-DD」「最終確認：YYYY-MM-DD」、翻訳版の「Updated: …」「Last checked: …」を、
  すべて「更新：」「Updated:」＋ git の最終コミット日（未コミットの変更があれば今日）に書き換える。
- 公開前（commit の直前）に実行する。build_search_index.py の前でも後でも良い。

    python case-study/araki-smart-manual/scripts/update_page_dates.py
"""
from __future__ import annotations

import datetime as dt
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = [
    (re.compile(r"(更新|最終確認)：\d{4}-\d{2}-\d{2}"), "更新：{d}"),
    (re.compile(r"更新 \d{4}-\d{2}-\d{2}"), "更新 {d}"),
    (re.compile(r"(Updated|Last checked): \d{4}-\d{2}-\d{2}"), "Updated: {d}"),
    (re.compile(r"Updated \d{4}-\d{2}-\d{2}"), "Updated {d}"),
]


def last_change(path: Path) -> str:
    dirty = subprocess.run(["git", "status", "--porcelain", "--", str(path)], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    if dirty:
        return dt.date.today().isoformat()
    out = subprocess.run(["git", "log", "-1", "--format=%cs", "--", str(path)], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    return out or dt.date.today().isoformat()


def main() -> None:
    n = 0
    for page in sorted(ROOT.glob("*.html")) + sorted(ROOT.glob("*/*.html")):
        html = page.read_text(encoding="utf-8")
        d = last_change(page)
        new = html
        for rx, fmt in PATTERNS:
            new = rx.sub(fmt.format(d=d), new)
        if new != html:
            page.write_text(new, encoding="utf-8", newline="\n")
            n += 1
            print("date:", page.relative_to(ROOT), d)
    print(f"{n} ファイルを更新しました")


if __name__ == "__main__":
    main()
