# かんたんフロントマニュアル（case-study/araki-smart-manual）

## サイト内検索の運用ルール

- ページ（*.html）を更新したら、必ず検索インデックスを作り直し、`assets/search-index.json` も同じ commit に含める。

  ```
  python case-study/araki-smart-manual/scripts/build_search_index.py
  ```

- このスクリプトは、全ページの CSS・JS への参照に `?v=内容のハッシュ` も付け直す。CSS・JS・検索データを直したときも必ず実行する（実行しないと、公開後もしばらくブラウザに古いファイルが残り、英語ページで日本語の検索結果が出るなどの食い違いが起きる）。
- 新しく h2 / h3 を足すときは、英数字の短い id を付ける（例：`id="scene6-refund"`）。id の無い見出しがあるとスクリプトはエラーで止まる。
- 既存の id は変えない（検索結果・トップページの「よくある操作」・他ページからのリンクが壊れる）。
- 言い換え（同義語・読みがな）は `assets/search-synonyms.json` に追加する。同じ配列の語は、どれで検索しても互いにヒットする。
- 検索の画面側は `assets/search.js` と `assets/search.css`（依存ライブラリなし。外部サービス・CDN は使わない）。
  - 候補の下の「すべての結果を見る」は `search.html?q=語`（全件・ページ別の絞り込み）。search.html は検索対象に入れない。
  - 結果のリンクは `ページ?hl=語#見出しid`。移動先では、その見出しから次の h2 / h3 までの一致語に印を付ける。
  - 見つからないときは、言い換え辞書の語を先に切り出してから助詞・言い回し（「〜したい」「やり方」など）で区切って探し直し、それでも無ければ辞書の近い語（打ち間違い）で探す。
- 動作確認はローカルHTTPサーバーで行う（`file://` では fetch が失敗する）。

  ```
  python -m http.server 8000   # case-study/araki-smart-manual で実行し、http://localhost:8000/ を開く
  ```

## 見た目（配色・書体）とヘッダー

- 配色は水墨画風のグレースケール（和紙・淡墨・中墨・濃墨）で、全体は明るい色調（ヘッダー・ヒーロー・見出し帯・フッターは白紙と淡墨。2026-10-11 オーナー指示「暗くて見にくい」）。書体は明朝（Noto Serif JP）。色と書体のトークン（`--lab-*`）は `assets/shell.css` だけで定義する。`assets/manual.css` と フロント運用編・初期設定編の `<style>` は、そのトークンを参照するだけで色の値を書かない。
- 朱（`--lab-red`）は「止める」「禁止」の印にだけ使う（落款の色）。注意は墨の濃淡（縁の太さ・二重線）で区別する。
- ヘッダー（ブランド・主要メニュー・言語切替・検索）は全ページ共通。メニューの項目やページを変えたら、次を実行してから `build_search_index.py` を実行する。

  ```
  python case-study/araki-smart-manual/scripts/make_site_header.py
  ```

- 860px 以下ではメニューを隠さず 2 行目に横スクロールで出す。フロント運用編・初期設定編の目次（`nav.toc` の `details[data-toc]`）はスマホで折りたたみ、PC では search.js が常に開く。
- 各ページのフッターの更新日は、commit の直前に次で git の日付にそろえる（手で書かない）。

  ```
  python case-study/araki-smart-manual/scripts/update_page_dates.py
  ```

- 画像には `loading="lazy" decoding="async"` を付ける（フロント運用編は 164 枚あるため）。
- あらきホテルのロゴは `assets/logo-araki.svg`（墨色。濃い背景では CSS の invert で白抜き）。トップのヒーローの背景は `assets/hero-bg.webp`（港から見たホテルの写真をグレースケール・低コントラスト・明るめにした物。スマホ用は hero-bg-960.webp）。元画像を差し替えるときは同じ加工（グレースケール、コントラスト 0.7、明るさ 1.25、幅 1920 / 960、WebP 品質 72）で作る。ヒーローでは和紙色の帯を重ねて文字を墨色で載せる。

## 公式オンラインマニュアルの記事索引

- `assets/official-manual-index.json` に、HOTEL SMART 公式オンラインマニュアル（pms-manual.xxxaz.jp）の記事名・カテゴリ・URLを置く。検索でヒットすると「公式マニュアル」として表示し、公式サイトの記事を別タブで開く。
- 記事の本文は取り込まない（転載の許諾は画像8点分だけ）。タイトルとリンクだけにする。
- 作り直すときは、公式サイトのトップ・マニュアル一覧・各カテゴリページ（/category/…、2ページ目以降も）を保存した HTML を全部まとめて渡して実行する。スクリプトはネットに接続しない。
  - 公式サイトは robots.txt で自動取得を断っており、WordPress の API（/wp-json）も 403 になる。2026-10-10 の取り込みは、オーナーの了承を得てカテゴリページを3秒間隔で取得した。自動取得をやり直すときは、改めてオーナーに確認する。

  ```
  python case-study/araki-smart-manual/scripts/import_official_index.py トップ.html マニュアル一覧.html カテゴリ/*.html
  ```

## 翻訳版（英語 en/ など）

- 英語版は `en/` に日本語版と同じファイル名・同じ見出し id で置く。画像・CSS・JS は日本語版のものを共用（`../assets/`・`../screenshots/`）。
- 各ページの言語の切り替えリンクと hreflang は `scripts/make_lang_page.py` が付ける。ページや言語を足したら `--switch-only` で付け直す。
- 翻訳のルール（画面のボタン名は日本語のまま＋英語、「公式マニュアルより」「あらきホテルでは未確認」の訳し方、公式の記事名は訳さない など）は `en/TRANSLATION.md`。
- 日本語ページを直したら、翻訳版のずれを確かめる。変わった節（見出し id 単位）が一覧に出るので、その節だけ訳し直して記録する。

  ```
  python case-study/araki-smart-manual/scripts/translation_status.py                 # 訳し直しが要る節
  python case-study/araki-smart-manual/scripts/translation_status.py --lang en --mark ページ.html#見出しid
  ```

- 英語版を直したら `scripts/protect_japanese.py` を実行する。英語版の中の日本語（画面のボタン名・公式の記事名）を `translate="no"` で囲み、ミャンマー人スタッフが Chrome / Edge の翻訳で英語版をミャンマー語にして読んでも、日本語の画面名が残るようにする（2026-10-11 オーナー判断：ミャンマー語版は作らず、ブラウザの翻訳で読む）。
- 検索インデックスは翻訳版の分（`assets/search-index-en.json`）も `build_search_index.py` が一緒に作る。英語の言い換えは `assets/search-synonyms-en.json`。
- 言語を足す（例：確認済みのミャンマー語訳を載せる `my/`）ときは、`make_lang_page.py` の `LANGS`、`build_search_index.py` の `TRANSLATIONS`、`assets/search.js` の文言（`T`）に加える。
