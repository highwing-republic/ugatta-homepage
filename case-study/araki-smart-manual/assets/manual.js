const MANUAL_TOPICS = [
  { title: "出勤したら最初に確認すること", url: "daily-operations.html#shift-start", note: "ダッシュボード・連絡事項・本日の予約", keys: "出勤 始業 朝 シフト ダッシュボード 引継ぎ" },
  { title: "予約を検索する", url: "reservation-guide.html#search", note: "名前・予約番号・宿泊日から探す", keys: "予約 検索 見つからない 名前 電話番号 予約番号" },
  { title: "個人予約を登録する", url: "reservation-guide.html#individual", note: "電話・自社予約の新規登録", keys: "個人 予約 新規 電話 自社 登録" },
  { title: "団体予約を登録する", url: "reservation-guide.html#group", note: "部屋割り前の団体枠を作る", keys: "団体 グループ 予約 新規 部屋割り" },
  { title: "手動で部屋を割り当てる", url: "room-assignment.html#manual-detail", note: "予約詳細の宿泊変更から部屋番号を選ぶ", keys: "アサイン 手動 部屋割り 未割当 部屋番号 割り当て" },
  { title: "自動部屋割りの仕組み", url: "room-assignment.html#auto", note: "実行時期・ローテーション・優先順位", keys: "アサイン 自動割当 自動部屋割り バッチ 午前1時 優先順位 ローテーション" },
  { title: "自動部屋割りが失敗した", url: "room-assignment.html#failure", note: "部屋タイプ・空室・定員・時期を確認", keys: "自動割当 失敗 エラー 未部屋割り オーバーブッキング 定員" },
  { title: "フロアを一括で割り当てる", url: "room-assignment.html#floor", note: "団体予約向け・責任者のみ", keys: "フロア 一括割当 団体 修学旅行 オーバーブッキング" },
  { title: "予約内容を変更する", url: "reservation-guide.html#change", note: "日付・人数・部屋・料金の変更", keys: "予約 変更 日程 人数 部屋 料金 延泊 短縮" },
  { title: "予約が見つからない", url: "troubleshooting.html#reservation-missing", note: "条件を外して再検索し、OTAも確認", keys: "予約 ない 見つからない OTA サイトコントローラー" },
  { title: "OTAとPMSの内容が違う", url: "troubleshooting.html#ota-mismatch", note: "変更せず、予約番号と更新時刻を確認", keys: "OTA PMS 違う 連携 同期 サイトコントローラー 金額 人数 日付" },
  { title: "チェックインする", url: "daily-operations.html#checkin", note: "本人確認から部屋キーのお渡しまで", keys: "チェックイン 到着 宿泊者 部屋 キー" },
  { title: "チェックインできない", url: "troubleshooting.html#checkin-error", note: "部屋・支払い・予約状態を確認", keys: "チェックイン できない エラー 部屋 未割当" },
  { title: "チェックアウトする", url: "daily-operations.html#checkout", note: "未精算確認から退室処理まで", keys: "チェックアウト 出発 退室 精算 領収書" },
  { title: "料金を登録・精算する", url: "reservation-guide.html#payment", note: "請求明細・支払方法・領収書", keys: "精算 支払 現金 カード 料金 明細 領収書 入金" },
  { title: "領収書を発行する", url: "reservation-guide.html#receipt", note: "宛名・但し書きを確認してPDF発行", keys: "領収書 宛名 但し書き PDF 印刷" },
  { title: "清掃状況を確認・更新する", url: "service-operations.html#cleaning", note: "未清掃・清掃中・清掃済みをそろえる", keys: "清掃 客室 ステータス 未清掃 清掃中 清掃済" },
  { title: "滞在中の部屋を変更する", url: "service-operations.html#room-change", note: "空室・清掃・鍵・部屋割りを確認", keys: "部屋移動 ルームチェンジ 鍵 連泊 部屋割り" },
  { title: "食事管理は現在使用しない", url: "service-operations.html#unused", note: "あらきホテルでは現在、食事を提供していません", keys: "食事 朝食 夕食 食事管理 使用しない" },
  { title: "客室をブロックする", url: "service-operations.html#room-block", note: "故障・工事などで販売を止める", keys: "部屋 客室 ブロック 売止 故障 工事" },
  { title: "引継ぎを残す", url: "daily-operations.html#handover", note: "未対応・注意事項・金銭差異を記録", keys: "引継ぎ 申し送り メモ 未対応 注意" },
  { title: "日次締めをする", url: "daily-operations.html#daily-close", note: "営業日を確定する管理者業務", keys: "日次 締め 締処理 営業日 管理者" },
  { title: "操作を間違えた", url: "troubleshooting.html#wrong-operation", note: "追加操作を止め、状態を記録して責任者へ", keys: "間違い 誤操作 取消 戻す 返金 二重登録 やり直し" },
  { title: "印刷用フロント早見表", url: "quick-reference.html", note: "毎日の確認と、止める場面を1ページに集約", keys: "早見表 印刷 チェックリスト 初心者" },
  { title: "用語を調べる", url: "glossary.html", note: "OTA・PMS・サイトコントローラーなど", keys: "用語 意味 OTA PMS サイトコントローラー" }
];

function normalizeText(value) {
  return value.toLowerCase().replace(/[\s　・ー]/g, "");
}

function setupManualSearch() {
  const form = document.querySelector("[data-manual-search]");
  if (!form) return;
  const input = form.querySelector("input");
  const results = document.querySelector("[data-search-results]");

  const render = () => {
    const query = normalizeText(input.value.trim());
    if (!query) {
      results.classList.remove("is-open");
      results.innerHTML = "";
      return;
    }
    const matches = MANUAL_TOPICS.filter((item) => normalizeText(`${item.title}${item.note}${item.keys}`).includes(query)).slice(0, 8);
    results.innerHTML = matches.length
      ? matches.map((item) => `<a href="${item.url}"><strong>${item.title}</strong><small>${item.note}</small></a>`).join("")
      : "<p>該当する手順がありません。別の短い言葉で試すか、「困ったとき」を確認してください。</p>";
    results.classList.add("is-open");
  };

  form.addEventListener("submit", (event) => { event.preventDefault(); render(); });
  input.addEventListener("input", render);
}

document.addEventListener("DOMContentLoaded", setupManualSearch);
