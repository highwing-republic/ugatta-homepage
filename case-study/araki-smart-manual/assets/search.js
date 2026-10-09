/*
 * かんたんフロントマニュアル サイト内検索
 * - assets/search-index.json（scripts/build_search_index.py で生成）と
 *   assets/search-synonyms.json（言い換え辞書）を読み込んで検索する。
 * - 依存ライブラリなし。ページ内の [data-site-search] フォームに検索機能を付ける。
 * - URL の ?q=語 で検索語を渡すと、最初の検索ボックスに入れて検索する。
 */
(function () {
  "use strict";

  var MAX_RESULTS = 15;
  var SNIPPET_LEN = 60;
  var scriptSrc = (document.currentScript && document.currentScript.src) || "assets/search.js";
  var INDEX_URL = new URL("search-index.json", scriptSrc).href;
  var SYNONYMS_URL = new URL("search-synonyms.json", scriptSrc).href;
  var currentPage = location.pathname.split("/").pop() || "index.html";

  // ---------- 正規化（NFKC・小文字・カタカナ→ひらがな） ----------
  function normalize(s) {
    return String(s).normalize("NFKC").toLowerCase().replace(/[ァ-ヶ]/g, function (c) {
      return String.fromCharCode(c.charCodeAt(0) - 0x60);
    });
  }

  // 元の文字列と、正規化後の各文字が元のどの位置に対応するかの表を作る（スニペット・ハイライト用）
  function normalizeWithMap(s) {
    var out = "";
    var map = [];
    for (var i = 0; i < s.length; i++) {
      var ch = s[i];
      // サロゲートペアは2文字まとめて扱う
      if (/[\ud800-\udbff]/.test(ch) && i + 1 < s.length) { ch += s[i + 1]; }
      var n = normalize(ch);
      for (var k = 0; k < n.length; k++) { out += n[k]; map.push(i); }
      i += ch.length - 1;
    }
    map.push(s.length);
    return { text: out, map: map };
  }

  function escapeHtml(s) {
    return s.replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  // ---------- データ読み込み ----------
  var dataPromise = null;
  function loadData() {
    if (dataPromise) return dataPromise;
    dataPromise = Promise.all([
      fetch(INDEX_URL).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }),
      fetch(SYNONYMS_URL).then(function (r) { return r.ok ? r.json() : []; }).catch(function () { return []; })
    ]).then(function (res) {
      var pageOrder = {};
      var entries = res[0].map(function (e, i) {
        if (!(e.page in pageOrder)) pageOrder[e.page] = Object.keys(pageOrder).length;
        return {
          page: e.page, pageTitle: e.pageTitle, anchor: e.anchor, heading: e.heading, text: e.text,
          nh: normalize(e.heading), nt: normalize(e.text), order: i
        };
      });
      entries.forEach(function (e) { e.pageRank = pageOrder[e.page]; });
      // 語 → 同じ組のほかの語。組の先頭の語（代表語）には canon を付ける
      var synonymMap = {};
      (res[1] || []).forEach(function (group) {
        var ng = group.map(normalize);
        ng.forEach(function (w) {
          var others = ng.filter(function (x) { return x !== w; }).map(function (x) { return { s: x, canon: x === ng[0] }; });
          synonymMap[w] = (synonymMap[w] || []).concat(others);
        });
      });
      return { entries: entries, synonymMap: synonymMap };
    });
    dataPromise.catch(function () { dataPromise = null; });
    return dataPromise;
  }

  // ---------- 検索 ----------
  function expandTerms(query, synonymMap) {
    return normalize(query).split(/\s+/).filter(Boolean).map(function (t) {
      // 言い換えのうち、入力語そのものに含まれる短い語（例：「チェックイン」に対する「イン」）は使わない
      var list = (synonymMap[t] || []).filter(function (x) { return t.indexOf(x.s) === -1; });
      return {
        term: t,
        syns: list.map(function (x) { return x.s; }),
        canon: list.filter(function (x) { return x.canon; }).map(function (x) { return x.s; })
      };
    });
  }

  function containsAny(str, words) {
    return words.some(function (x) { return str.indexOf(x) !== -1; });
  }

  function scoreEntry(e, terms) {
    var total = 0;
    for (var i = 0; i < terms.length; i++) {
      var t = terms[i], s = 0;
      if (e.nh.indexOf(t.term) !== -1) s = 4;              // 見出しに一致
      else if (containsAny(e.nh, t.canon)) s = 3.5;         // 言い換え（代表語）で見出しに一致
      else if (containsAny(e.nh, t.syns)) s = 3;            // 言い換えで見出しに一致
      else if (e.nt.indexOf(t.term) !== -1) s = 2;          // 本文に一致
      else if (containsAny(e.nt, t.syns)) s = 1;            // 言い換えで本文に一致
      if (!s) return 0;
      total += s;
    }
    return total;
  }

  function search(query, data) {
    var terms = expandTerms(query, data.synonymMap);
    if (!terms.length) return { terms: terms, hits: [] };
    var hits = [];
    data.entries.forEach(function (e) {
      var sc = scoreEntry(e, terms);
      if (sc) hits.push({ e: e, score: sc });
    });
    hits.sort(function (a, b) {
      return b.score - a.score || a.e.pageRank - b.e.pageRank || a.e.order - b.e.order;
    });
    return { terms: terms, hits: hits.slice(0, MAX_RESULTS) };
  }

  // 文字列中の一致語を <mark> で囲んだ HTML を返す
  function highlight(raw, words) {
    var nm = normalizeWithMap(raw);
    var ranges = [];
    words.forEach(function (w) {
      if (!w) return;
      var from = 0, p;
      while ((p = nm.text.indexOf(w, from)) !== -1) {
        ranges.push([nm.map[p], nm.map[p + w.length - 1] + 1]);
        from = p + w.length;
      }
    });
    if (!ranges.length) return escapeHtml(raw);
    ranges.sort(function (a, b) { return a[0] - b[0]; });
    var merged = [ranges[0]];
    for (var i = 1; i < ranges.length; i++) {
      var last = merged[merged.length - 1];
      if (ranges[i][0] <= last[1]) last[1] = Math.max(last[1], ranges[i][1]);
      else merged.push(ranges[i]);
    }
    var html = "", pos = 0;
    merged.forEach(function (r) {
      html += escapeHtml(raw.slice(pos, r[0])) + "<mark>" + escapeHtml(raw.slice(r[0], r[1])) + "</mark>";
      pos = r[1];
    });
    return html + escapeHtml(raw.slice(pos));
  }

  function snippet(text, words) {
    var nm = normalizeWithMap(text);
    var hit = -1;
    for (var i = 0; i < words.length && hit === -1; i++) {
      var p = nm.text.indexOf(words[i]);
      if (p !== -1) hit = nm.map[p];
    }
    if (hit === -1) hit = 0;
    var start = Math.max(0, hit - 20);
    var end = Math.min(text.length, start + SNIPPET_LEN);
    start = Math.max(0, end - SNIPPET_LEN);
    return (start > 0 ? "…" : "") + highlight(text.slice(start, end), words) + (end < text.length ? "…" : "");
  }

  // ---------- 表示 ----------
  var uid = 0;

  function setup(form) {
    var input = form.querySelector("input[type=search]");
    if (!input) return;
    var listId = "site-search-results-" + (++uid);
    var box = document.createElement("div");
    box.className = "site-search-results";
    box.id = listId;
    box.setAttribute("role", "listbox");
    box.hidden = true;
    form.appendChild(box);
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-controls", listId);
    input.setAttribute("aria-expanded", "false");
    input.setAttribute("aria-autocomplete", "list");

    var active = -1;
    var timer = null;
    var lastQuery = null;

    function items() { return box.querySelectorAll(".site-search-item"); }

    function setActive(i) {
      var list = items();
      if (!list.length) { active = -1; return; }
      active = (i + list.length) % list.length;
      for (var k = 0; k < list.length; k++) {
        list[k].classList.toggle("is-active", k === active);
        list[k].setAttribute("aria-selected", k === active ? "true" : "false");
      }
      list[active].scrollIntoView({ block: "nearest" });
    }

    function open() { box.hidden = false; input.setAttribute("aria-expanded", "true"); }
    function close() { box.hidden = true; input.setAttribute("aria-expanded", "false"); active = -1; }

    function render() {
      var q = input.value.trim();
      if (!q) { lastQuery = null; box.innerHTML = ""; close(); return; }
      if (q === lastQuery && !box.hidden) return;
      lastQuery = q;
      loadData().then(function (data) {
        if (input.value.trim() !== q) return;
        var res = search(q, data);
        var words = [];
        res.terms.forEach(function (t) { words.push(t.term); words = words.concat(t.syns); });
        if (!res.hits.length) {
          box.innerHTML = '<div class="site-search-empty">見つかりません。<a href="troubleshooting.html">『困ったとき』</a>を見るか、用語を変えてお試しください</div>';
        } else {
          box.innerHTML = res.hits.map(function (h) {
            var e = h.e;
            return '<a class="site-search-item" role="option" aria-selected="false" href="' + escapeHtml(e.page + "#" + e.anchor) + '">' +
              '<span class="site-search-path">' + escapeHtml(e.pageTitle) + " › " + highlight(e.heading, words) + "</span>" +
              '<span class="site-search-snippet">' + snippet(e.text, words) + "</span></a>";
          }).join("");
        }
        active = -1;
        open();
      }).catch(function () {
        box.innerHTML = '<div class="site-search-empty">検索データを読み込めませんでした。ページを再読み込みしてください。</div>';
        open();
      });
    }

    function schedule() { clearTimeout(timer); timer = setTimeout(render, 120); }

    input.addEventListener("input", function (ev) { if (ev.isComposing) return; schedule(); });
    input.addEventListener("compositionend", schedule);
    input.addEventListener("focus", function () { loadData(); if (input.value.trim()) { lastQuery = null; render(); } });
    input.addEventListener("keydown", function (ev) {
      if (ev.isComposing || ev.keyCode === 229) return;
      if (ev.key === "ArrowDown") { ev.preventDefault(); if (box.hidden) render(); else setActive(active + 1); }
      else if (ev.key === "ArrowUp") { ev.preventDefault(); setActive(active - 1); }
      else if (ev.key === "Escape") { close(); }
      else if (ev.key === "Enter") {
        ev.preventDefault();
        var list = items();
        if (list.length) list[active >= 0 ? active : 0].click();
        else render();
      }
    });
    form.addEventListener("submit", function (ev) { ev.preventDefault(); });
    box.addEventListener("click", function (ev) {
      var a = ev.target.closest("a.site-search-item");
      if (!a) return;
      close();
      // 同じページ内の見出しへ移動するとき、同じ見出しでもハイライトをやり直す
      var href = a.getAttribute("href");
      var page = href.split("#")[0];
      if (page === currentPage && location.hash === "#" + href.split("#")[1]) {
        ev.preventDefault();
        var el = document.getElementById(href.split("#")[1]);
        if (el) { el.classList.remove("site-search-flash"); void el.offsetWidth; el.classList.add("site-search-flash"); el.scrollIntoView(); }
      }
    });
    document.addEventListener("click", function (ev) { if (!form.contains(ev.target)) close(); });

    return { input: input, render: render };
  }

  function init() {
    var forms = document.querySelectorAll("[data-site-search]");
    var widgets = [];
    for (var i = 0; i < forms.length; i++) { var w = setup(forms[i]); if (w) widgets.push(w); }
    var q = new URLSearchParams(location.search).get("q");
    if (q && widgets.length) {
      // トップページでは大きな検索ボックスを優先
      var target = document.querySelector("[data-site-search].site-search--hero input[type=search]");
      var w2 = widgets.filter(function (w) { return w.input === target; })[0] || widgets[0];
      w2.input.value = q;
      w2.render();
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();

  // テスト用に正規化と検索を公開
  window.ManualSearch = { normalize: normalize, loadData: loadData, search: function (q) { return loadData().then(function (d) { return search(q, d); }); } };
})();
