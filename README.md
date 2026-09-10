# UGATTA Website

合同会社UGATTAの公式サイトです。GitHub Pagesで `https://ugatta-llc.com/` に公開します。

## 公開設定

- カスタムドメイン: `ugatta-llc.com`（`CNAME`で管理）
- Google Analytics: `GT-M3S9S5D7`
- `robots.txt` と `sitemap.xml` で検索公開を管理
- `.nojekyll` でJekyll処理を無効化

## 更新・デプロイ

GitHub Pages の **Deploy from a branch** を使い、`main` ブランチの `/ (root)` を公開します。`main` へ push すると自動的に反映されます。

## インバウンド宿泊者分析データ

- 表示データ: `data/inbound/latest.json`
- メタデータ: `data/inbound/metadata.json`
- 生成処理: `scripts/update_inbound_data.py`
- 検証: `python -m pytest -q`
- 自動更新: `.github/workflows/update-inbound-data.yml`

観光庁「宿泊旅行統計調査」の最新第2次速報をGitHub Actionsで週次確認します。取得・解析・検証がすべて成功し、JSONに変更がある場合だけコミットします。観光庁への取得処理はGitHub Actions内に限定しています。

## 無料ツール

`useful.html` からDX診断、インバウンド宿泊者分析、観光株シグナルへ同一ドメイン内で移動できます。
