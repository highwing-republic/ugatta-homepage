# かんたんフロントマニュアル（case-study/araki-smart-manual）

## サイト内検索の運用ルール

- ページ（*.html）を更新したら、必ず検索インデックスを作り直し、`assets/search-index.json` も同じ commit に含める。

  ```
  python case-study/araki-smart-manual/scripts/build_search_index.py
  ```

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

## 公式オンラインマニュアルの記事索引

- `assets/official-manual-index.json` に、HOTEL SMART 公式オンラインマニュアル（pms-manual.xxxaz.jp）の記事名・カテゴリ・URLを置く。検索でヒットすると「公式マニュアル」として表示し、公式サイトの記事を別タブで開く。
- 記事の本文は取り込まない（転載の許諾は画像8点分だけ）。タイトルとリンクだけにする。
- 作り直すときは、公式サイトの記事一覧ページを保存した HTML か、一覧を貼り付けたテキストを渡して実行する（公式サイトは自動取得を拒否しているため、スクリプトはネットに接続しない）。

  ```
  python case-study/araki-smart-manual/scripts/import_official_index.py トップ.html 記事一覧.html
  ```
