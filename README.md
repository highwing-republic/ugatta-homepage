# Ugatta website

このサイトは Firebase Hosting から GitHub Pages に移行する構成です。

## デプロイ方法

1. GitHub リポジトリで Settings > Pages を開く
2. "Build and deployment" で "GitHub Actions" を選択する
3. main ブランチに変更を push すると、Actions が自動でデプロイされる

## 変更内容

- Firebase Hosting 設定ファイルを削除
- GitHub Pages 用の GitHub Actions ワークフローを追加
- Jekyll の処理を無効化するための `.nojekyll` を追加
