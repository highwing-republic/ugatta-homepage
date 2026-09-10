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
- AIインサイト: `data/inbound/insights.json`
- Gemini生成処理: `scripts/generate_inbound_insights.py`
- 検証: `python -m pytest -q`
- 自動更新: `.github/workflows/update-inbound-data.yml`

観光庁「宿泊旅行統計調査」の最新第2次速報をGitHub Actionsで週次確認します。取得・解析・検証がすべて成功し、JSONに変更がある場合だけコミットします。観光庁への取得処理はGitHub Actions内に限定しています。

### Gemini AIインサイト

本番リポジトリのGitHub Actions Secretに `GEMINI_API_KEY` を登録すると、統計更新時にGeminiが全国・47都道府県のショートインサイトを事前生成します。既定モデルは `gemini-2.5-flash` で、必要な場合はワークフローの `GEMINI_MODEL` で変更できます。

生成文は3段落の構造、参照した事実ID、文章内の数値、断定表現を検証してから `data/inbound/insights.json` に保存します。APIキー未設定、生成失敗、統計との更新月不一致の場合、分析ページは既存の統計値ベース文章へ自動的に切り替わります。ページ閲覧時にGemini APIへアクセスすることはありません。

## 無料ツール

`useful.html` からDX診断、インバウンド宿泊者分析、観光株シグナルへ同一ドメイン内で移動できます。
