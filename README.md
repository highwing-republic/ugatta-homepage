# UGATTA Website

合同会社UGATTAの本番サイトです。GitHub Pagesで `https://ugatta-llc.com/` に公開します。

## デプロイ方法

1. GitHub リポジトリで `Settings > Pages` を開く
2. `Build and deployment` で `GitHub Actions` を選択する
3. `main` ブランチに変更をpushすると、Actionsが自動でデプロイされる

## 公開設定

- カスタムドメイン: `ugatta-llc.com`（`CNAME`で管理）
- Google Analytics: `GT-M3S9S5D7`
- `robots.txt` と `sitemap.xml` で検索公開を管理
- `.nojekyll` でJekyll処理を無効化

## 無料ツール

`useful.html` には「観光株シグナル / Tourism Market Signal」を埋め込み表示します。ツール本体は別リポジトリで更新されます。

拡大表示は同じドメインの `report.html` で行います。レポートを埋め込むことで、アドレス欄をUGATTAのドメインに保ち、別リポジトリの最新データを表示します。配信元のURLはHTMLや開発者ツールから確認できます。
