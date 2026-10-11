# English version: translation rules

The English pages in `en/` mirror the Japanese pages one to one (same file names, same heading ids).
Readers are front-desk staff who read English but operate HOTEL SMART, whose screens are in Japanese.

## How sync works

- Every `h2` / `h3` has an id, and the English page uses exactly the same ids. The id is the unit of translation.
- `scripts/translation_status.py` compares each Japanese section with the version that was last translated
  (fingerprints in `en/translation-sources.json`) and lists the sections that changed, are missing or are extra.
- After re-translating a section, record it: `python scripts/translation_status.py --lang en --mark front-operations.html#scene4-split`
  (or `--mark front-operations.html` for the whole page). Then rebuild the search index.
- New Japanese page: `python scripts/make_lang_page.py --lang en new-page.html` makes `en/new-page.html` (paths fixed, language
  switch added) with the Japanese text still in it; translate it, add it to `PAGES_EN` in `build_search_index.py`, then `--mark` it.
- After editing an English page, run `python scripts/protect_japanese.py`. It wraps the Japanese in the English pages
  (screen labels, official titles) in `<span translate="no" lang="ja">` so that Chrome / Edge page translation
  (used by Myanmar staff to read the English pages in Burmese) leaves it untouched. It is safe to run repeatedly.
- Another language (for example Burmese, `my/`) uses the same mechanism: it is listed in `LANGS` in `make_lang_page.py`,
  gets its own page titles in `TRANSLATIONS` in `build_search_index.py`, its own `my/translation-sources.json`,
  and its own wording in `assets/search.js` and rules file.

## What to translate

- Translate only human-visible text: text between tags, and the `alt`, `title`, `aria-label`, `placeholder`
  attributes, `<title>` and `<meta name="description">`.
- Never change tags, ids, classes, `href`, `src`, inline CSS or scripts. Image and asset paths already point to `../`.
- Translate everything that is there and add nothing. Do not add explanations, steps or facts that are not in the Japanese page.

## Screen labels (buttons, menus, fields, statuses)

HOTEL SMART shows Japanese on screen, so staff need the Japanese label to find it.
Keep the Japanese label exactly as written, in its original brackets, and add the English in parentheses right after it:

- `【売上管理】` → `【売上管理】 (Sales management)`
- `「宿泊変更」をクリック` → `Click 「宿泊変更」 (Change stay)`
- Paths: `【清掃管理】＞【手配設定】` → `【清掃管理】＞【手配設定】 (Cleaning management > Arrangement settings)`

Quoted words that are not screen labels (example search words, things a guest says, general terms) are simply translated.

## Fixed phrases (tags used across the manual)

| Japanese | English |
|---|---|
| 公式マニュアルより | from the official manual |
| あらきホテルでは未確認 | not yet confirmed at Araki Hotel |
| （2026/10/11 オーナー決定） | (owner's decision, 2026-10-11) |
| （2026/10/09確認） | (checked 2026-10-09) |
| 実画面で確認 | checked on the real screen |
| 責任者 | the manager (person in charge) on first use per page, then "the manager" |
| 責任者判断 / 責任者の判断 | the manager's decision |

Keep the parentheses style of the original (a tag in （…） stays in (…)).

## Official manual references

- Titles of official HOTEL SMART documents and articles (for example 「HOTEL SMART フロント運用マニュアル 2024.1〜」, link text that points to pms-manual.xxxaz.jp)
  stay in Japanese exactly as written. You may add a plain description after them, such as "(official manual, in Japanese)".
  Do not invent an English title that could be mistaken for an official one.
- Never copy text from the official manual. Only translate this manual's own Japanese.

## Terms

| Japanese | English |
|---|---|
| あらきホテル | Araki Hotel |
| 種子島 | Tanegashima |
| かんたんフロントマニュアル | Front Desk Quick Manual |
| 予約 / 個人予約 / 団体予約 | reservation / individual reservation / group reservation |
| 予約詳細 | reservation details |
| 予約経路 | booking channel |
| 部屋割り / アサイン | room assignment (assign a room) |
| 未部屋割り / 未割当 | unassigned |
| 自動部屋割り | automatic room assignment |
| 部屋割り表 | room allocation chart |
| 客室の状況表 | room status chart |
| 部屋タイプ | room type |
| 客室ブロック / ブロック | room block / block |
| ルームチェンジ | room change |
| 連泊 | multi-night stay |
| チェックイン / チェックアウト | check-in / check-out (verb: check in / check out) |
| ノーショー | no-show |
| 料金 | charges |
| 精算 | payment (settlement) |
| 未収金 | outstanding balance |
| 前受金 | advance payment |
| 滞在未収金 | in-house receivable |
| 事前決済 / 現地決済 | prepaid / pay at the hotel |
| 利用明細 | statement (itemized bill) |
| 領収書 | receipt |
| 返金 | refund |
| 日次締め | daily closing |
| 帳票 | reports |
| ダッシュボード | dashboard |
| 清掃 / 清掃予定表 | cleaning / cleaning schedule |
| 共有事項 / オペレーターメモ | shared notes / operator memo |
| マイページ | guest My Page |
| セルフチェックイン（タブレット） | tablet self check-in |
| サイトコントローラー | site controller |
| TLリンカーン | TL-Lincoln |
| 2way連携 | two-way integration |
| 販売在庫 | sales inventory |
| 付帯設備 | facilities (add-on facilities) |
| 入湯税 / 宿泊税 | bathing tax / accommodation tax |
| プラン | rate plan |
| OTA | OTA (online travel agency) |

## Style

- US English, plain and short. Steps are imperative ("Click …", "Check …").
- Keep numbers, dates, times, amounts and room numbers as they are. Write dates as 2026-10-11.
- Keep emphasis markup (`<strong>`, `<span class="label">`) around the matching English words.
