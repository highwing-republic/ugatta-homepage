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

`useful.html` では「旅館・ホテルDXかんたん診断」と「観光株シグナル / Tourism Market Signal」を案内します。各ツール本体は別プロジェクトで更新されるため、片方の更新がもう片方へ影響しない構成です。

観光株シグナルの拡大表示は同じドメインの `report.html`、DX診断は `dx-diagnosis.html` で行います。各ツールを埋め込むことで、アドレス欄をUGATTAのドメインに保ちながら、別プロジェクトの最新版を表示します。
