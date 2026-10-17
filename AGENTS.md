# UGATTA公式サイト
- このリポジトリは合同会社UGATTAの公式サイト（https://ugatta-llc.com/）です。
- 宿泊DXラボ（https://lab.ugatta-llc.com/）は別リポジトリ highwing-republic/ugatta-lab（旧名 makoto-consulting）です。無料ツールはラボ側で編集します。
- 公開方式：GitHub Pages（main ブランチ / root、Jekyll）。README、tests/、*.md は _config.yml の exclude で公開対象から外れます。公開しないファイルを新しく置くときは exclude に追加してください。
- 作業の始め方：git fetch origin → git status → 新しいブランチは origin/main から作ります。
- 公開リポジトリです。個人情報、顧客資料、.env、認証情報はコミットしないでください。
- テスト：python -m unittest discover -s tests -p "test_*.py"
