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
- 動作確認はローカルHTTPサーバーで行う（`file://` では fetch が失敗する）。

  ```
  python -m http.server 8000   # case-study/araki-smart-manual で実行し、http://localhost:8000/ を開く
  ```
