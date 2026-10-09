/*
 * かんたんフロントマニュアル サイト内検索
 * - assets/search-index.json（scripts/build_search_index.py で生成）と
 *   assets/search-synonyms.json（言い換え辞書）を読み込んで検索する。
 * - 依存ライブラリなし。ページ内の [data-site-search] フォームに検索機能を付ける。
 * - URL の ?q=語 で検索語を渡すと、最初の検索ボックスに入れて検索する。
 *   search.html では、[data-search-page] の中に全件の結果一覧を出す。
 * - 結果のリンクには ?hl=語 を付け、移動先の節の中で一致した語を強調表示する。
 */
(function () {
  "use strict";

  var MAX_RESULTS = 15;      // 検索ボックスの候補に出す件数（全件は search.html）
  var SNIPPET_LEN_DEFAULT = 60;
  var PAGE_SNIPPET_LEN = 140; // 結果一覧ページの抜粋の長さ
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
      var synonymKeys = Object.keys(synonymMap).filter(function (k) { return k.length >= 2; })
        .sort(function (a, b) { return b.length - a.length; });
      return { entries: entries, synonymMap: synonymMap, synonymKeys: synonymKeys };
    });
    dataPromise.catch(function () { dataPromise = null; });
    return dataPromise;
  }

  // ---------- 検索 ----------
  function expandTerms(query, synonymMap) {
    return normalize(query).split(/\s+/).filter(Boolean).map(function (t) {
      // 言い換えのうち、入力語そのものに含まれる短い語（例：「チェックイン」に対する「イン」）は使わない。
      // 3文字以上なら語幹として使う（例：「取り消し」に対する「取り消」で「取り消す」も拾う）
      var list = (synonymMap[t] || []).filter(function (x) { return t.indexOf(x.s) === -1 || x.s.length >= 3; });
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

  function rank(entries, terms, scorer) {
    var hits = [];
    entries.forEach(function (e) {
      var sc = scorer(e, terms);
      if (sc) hits.push({ e: e, score: sc });
    });
    hits.sort(function (a, b) {
      return b.score - a.score || a.e.pageRank - b.e.pageRank || a.e.order - b.e.order;
    });
    return hits;
  }

  // 「返金のやり方」「部屋を移したい」のような文の形の検索語を、助詞や言い回しで区切る
  var FILLER = /(?:のやりかた|やりかた|のやり方|やり方|のしかた|しかた|の仕方|仕方|の方法|方法|どうやって|どうする|どこで|どこ|できない|できる|したいとき|したい|したら|するには|する|します|ください|ときは|とき|には|では|から|まで|を|が|は|に|で|と|の|へ|や|か|って|たい|ない|ます|です|して|した|ている|てる|\?)/;

  // 言い換え辞書の語（長いものから）を先に切り出し、残りを助詞や言い回しで区切る。
  // 「へんきんの方法」の「へ」のように、辞書の語の中の文字で切ってしまわないため。
  function splitPhrase(t, keys) {
    var out = [], rest = "";
    function flush() {
      rest.split(FILLER).forEach(function (x) { if (x && x.length >= 2) out.push(x); });
      rest = "";
    }
    for (var i = 0; i < t.length;) {
      var hit = null;
      for (var k = 0; k < keys.length; k++) {
        if (t.substr(i, keys[k].length) === keys[k]) { hit = keys[k]; break; }
      }
      if (hit) { flush(); out.push(hit); i += hit.length; }
      else { rest += t[i]; i++; }
    }
    flush();
    return out;
  }

  // 打ち間違いを、言い換え辞書のいちばん近い語に置き換える（例：「ろうしゅうしょ」→「りょうしゅうしょ」）
  function nearestKey(t, keys) {
    var bg = bigrams(t), best = null, bestRatio = 0.6;
    if (bg.length < 2) return null;
    keys.forEach(function (k) {
      if (Math.abs(k.length - t.length) > 2) return;
      var kb = bigrams(k), n = 0;
      bg.forEach(function (b) { if (kb.indexOf(b) !== -1) n++; });
      var ratio = n / Math.max(bg.length, kb.length);
      if (ratio >= bestRatio) { best = k; bestRatio = ratio; }
    });
    return best;
  }

  // 一部だけ一致する節も拾う（どれか1語でも一致すれば候補。一致した語が多いほど上位）
  function scoreAny(e, terms) {
    var total = 0, matched = 0;
    terms.forEach(function (t) {
      var s = scoreEntry(e, [t]);
      if (s) { total += s; matched++; }
    });
    return matched ? matched * 10 + total : 0;
  }

  // 打ち間違い・表記ゆれ用：2文字ずつの組がどれだけ含まれるか（見出し＋本文）
  function bigrams(t) {
    var out = [];
    for (var i = 0; i + 1 < t.length; i++) out.push(t.slice(i, i + 2));
    return out;
  }
  function scoreFuzzy(e, terms) {
    var total = 0;
    for (var i = 0; i < terms.length; i++) {
      var bg = bigrams(terms[i].term);
      if (!bg.length) return 0;
      var inH = 0, inAll = 0;
      bg.forEach(function (b) {
        if (e.nh.indexOf(b) !== -1) { inH++; inAll++; }
        else if (e.nt.indexOf(b) !== -1) inAll++;
      });
      var ratio = inAll / bg.length;
      if (ratio < 0.6) return 0;
      total += ratio * 2 + inH / bg.length;
    }
    return total;
  }

  // mode: exact（そのまま一致）／split（文を区切って全語一致）／any（一部の語が一致）／fuzzy（似た語）
  function search(query, data) {
    var terms = expandTerms(query, data.synonymMap);
    var none = { terms: terms, hits: [], total: 0, mode: "exact" };
    if (!terms.length) return none;
    var hits = rank(data.entries, terms, scoreEntry);
    if (hits.length) return { terms: terms, hits: hits, total: hits.length, mode: "exact" };

    var original = terms.map(function (t) { return t.term; }).join(" ");
    var pieces = [];
    terms.forEach(function (t) {
      var p = splitPhrase(t.term, data.synonymKeys);
      pieces = pieces.concat(p.length ? p : [t.term]);
    });
    var split = expandTerms(pieces.join(" "), data.synonymMap);
    if (pieces.join(" ") !== original) {
      hits = rank(data.entries, split, scoreEntry);
      if (hits.length) return { terms: split, hits: hits, total: hits.length, mode: "split" };
    }
    if (split.length > 1) {
      hits = rank(data.entries, split, scoreAny);
      if (hits.length) return { terms: split, hits: hits, total: hits.length, mode: "any" };
    }
    // 似た語：辞書の近い語に置き換えて探し、それでも無ければ節の文字列と直接比べる
    var fixed = pieces.map(function (p) { return nearestKey(p, data.synonymKeys) || p; });
    if (fixed.join(" ") !== pieces.join(" ")) {
      var ft = expandTerms(fixed.join(" "), data.synonymMap);
      hits = rank(data.entries, ft, scoreEntry);
      if (!hits.length && ft.length > 1) hits = rank(data.entries, ft, scoreAny);
      if (hits.length) return { terms: ft, hits: hits, total: hits.length, mode: "fuzzy" };
    }
    hits = rank(data.entries, split.filter(function (t) { return t.term.length >= 3; }), scoreFuzzy);
    if (hits.length) return { terms: split, hits: hits, total: hits.length, mode: "fuzzy", bigram: true };
    return none;
  }

  // 強調表示に使う語（入力語と言い換え。似た語の検索では2文字の組）
  function matchWords(res) {
    var words = [];
    res.terms.forEach(function (t) {
      words.push(t.term);
      words = words.concat(t.syns);
      if (res.bigram) words = words.concat(bigrams(t.term));
    });
    return words;
  }

  function modeNote(res) {
    var w = res.terms.map(function (t) { return "「" + t.term + "」"; }).join("");
    if (res.mode === "split") return w + "に分けて探しました";
    if (res.mode === "any") return "すべてを含む節が無いため、" + w + "のどれかを含む節を出しています";
    if (res.mode === "fuzzy") return "そのままでは見つからないため、似た言葉" + (res.bigram ? "" : w) + "で探しました";
    return "";
  }

  function resultHref(e, query) {
    return e.page + "?hl=" + encodeURIComponent(query) + "#" + e.anchor;
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

  function snippet(text, words, len) {
    var SNIPPET_LEN = len || SNIPPET_LEN_DEFAULT;
    var nm = normalizeWithMap(text);
    var hit = -1;
    for (var i = 0; i < words.length && hit === -1; i++) {
      var p = nm.text.indexOf(words[i]);
      if (p !== -1) hit = nm.map[p];
    }
    if (hit === -1) hit = 0;
    var start = Math.max(0, hit - Math.round(SNIPPET_LEN / 3));
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
        var words = matchWords(res);
        var note = modeNote(res);
        if (!res.hits.length) {
          box.innerHTML = '<div class="site-search-empty">見つかりません。<a href="troubleshooting.html">『困ったとき』</a>を見るか、用語を変えてお試しください</div>';
        } else {
          box.innerHTML = (note ? '<div class="site-search-note">' + escapeHtml(note) + "</div>" : "") +
            res.hits.slice(0, MAX_RESULTS).map(function (h) {
              var e = h.e;
              return '<a class="site-search-item" role="option" aria-selected="false" href="' + escapeHtml(resultHref(e, q)) + '">' +
                '<span class="site-search-path">' + escapeHtml(e.pageTitle) + " › " + highlight(e.heading, words) + "</span>" +
                '<span class="site-search-snippet">' + snippet(e.text, words) + "</span></a>";
            }).join("") +
            '<a class="site-search-all" href="search.html?q=' + encodeURIComponent(q) + '">' +
            (res.total > MAX_RESULTS ? "すべての結果を見る（" + res.total + "件）" : "結果一覧ページで見る（" + res.total + "件）") + "</a>";
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
      var page = href.split("#")[0].split("?")[0];
      if (page === currentPage && location.hash === "#" + href.split("#")[1]) {
        ev.preventDefault();
        var el = document.getElementById(href.split("#")[1]);
        if (el) {
          el.classList.remove("site-search-flash"); void el.offsetWidth; el.classList.add("site-search-flash"); el.scrollIntoView();
          highlightSection(el, new URLSearchParams(href.split("#")[0].split("?")[1] || "").get("hl"));
        }
      }
    });
    document.addEventListener("click", function (ev) { if (!form.contains(ev.target)) close(); });

    return { input: input, render: render };
  }

  // ---------- 移動先のページで一致した語を強調表示 ----------
  var SKIP_TAGS = { SCRIPT: 1, STYLE: 1, NOSCRIPT: 1, TEXTAREA: 1, INPUT: 1, MARK: 1 };

  function clearHighlights() {
    var marks = document.querySelectorAll("mark.site-search-hl");
    for (var i = 0; i < marks.length; i++) {
      var m = marks[i], parent = m.parentNode;
      parent.replaceChild(document.createTextNode(m.textContent), m);
      parent.normalize();
    }
    var bar = document.querySelector(".site-search-hlbar");
    if (bar) bar.parentNode.removeChild(bar);
  }

  // 見出し el から次の h2/h3 の手前まで（＝検索インデックスの1節）の文字列に印を付ける
  function highlightSection(el, query) {
    clearHighlights();
    if (!el || !query) return;
    loadData().then(function (data) {
      var words = matchWords(search(query, data)).filter(function (w) { return w.length >= 2 || /[^぀-ゟ]/.test(w); });
      if (!words.length) return;
      var nodes = [];
      var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, null);
      walker.currentNode = el;
      var node = el;
      while (node) {
        if (node.nodeType === 1) {
          if (node !== el && !el.contains(node) && /^H[23]$/.test(node.tagName)) break;
          if (SKIP_TAGS[node.tagName] || node.closest("nav, footer, .site-search, .zoom-hint")) {
            node = nextSkippingChildren(walker);
            continue;
          }
        } else if (node.nodeType === 3 && node.nodeValue.trim()) {
          nodes.push(node);
        }
        node = walker.nextNode();
      }
      var count = 0, first = null;
      nodes.forEach(function (tn) {
        var raw = tn.nodeValue;
        var html = highlight(raw, words);
        if (html === escapeHtml(raw)) return;
        var span = document.createElement("span");
        span.innerHTML = html.replace(/<mark>/g, '<mark class="site-search-hl">');
        var frag = document.createDocumentFragment();
        while (span.firstChild) frag.appendChild(span.firstChild);
        count += frag.querySelectorAll("mark").length;
        if (!first) first = frag.querySelector("mark");
        tn.parentNode.replaceChild(frag, tn);
      });
      if (!count) return;
      var bar = document.createElement("div");
      bar.className = "site-search-hlbar";
      bar.setAttribute("role", "status");
      bar.innerHTML = "「" + escapeHtml(query) + "」に一致した語を強調表示しています（" + count + "か所）" +
        '<button type="button">強調を消す</button>';
      bar.querySelector("button").addEventListener("click", function () {
        clearHighlights();
        if (history.replaceState) {
          var u = new URL(location.href); u.searchParams.delete("hl"); history.replaceState(null, "", u.href);
        }
      });
      document.body.appendChild(bar);
    });
  }

  function nextSkippingChildren(walker) {
    var n = walker.nextSibling();
    while (!n) {
      if (!walker.parentNode()) return null;
      n = walker.nextSibling();
    }
    return n;
  }

  function highlightFromUrl() {
    var hl = new URLSearchParams(location.search).get("hl");
    if (!hl || !location.hash) return;
    var el = document.getElementById(decodeURIComponent(location.hash.slice(1)));
    if (el) highlightSection(el, hl);
  }

  // ---------- 結果一覧ページ（search.html） ----------
  function setupResultsPage(root) {
    var form = root.querySelector("form");
    var input = root.querySelector("input[type=search]");
    var filters = root.querySelector("[data-search-filters]");
    var list = root.querySelector("[data-search-list]");
    var status = root.querySelector("[data-search-status]");
    var activePage = "";
    var timer = null;

    function draw() {
      var q = input.value.trim();
      if (history.replaceState) {
        var u = new URL(location.href);
        if (q) u.searchParams.set("q", q); else u.searchParams.delete("q");
        history.replaceState(null, "", u.href);
      }
      document.title = (q ? "「" + q + "」の検索結果｜" : "検索｜") + "あらきホテル";
      if (!q) { status.textContent = "調べたい操作や言葉を入れてください。"; filters.innerHTML = ""; list.innerHTML = ""; return; }
      loadData().then(function (data) {
        if (input.value.trim() !== q) return;
        var res = search(q, data);
        var words = matchWords(res);
        var counts = {}, titles = [];
        res.hits.forEach(function (h) {
          if (!(h.e.page in counts)) { counts[h.e.page] = 0; titles.push(h.e); }
          counts[h.e.page]++;
        });
        if (activePage && !(activePage in counts)) activePage = "";
        titles.sort(function (a, b) { return a.pageRank - b.pageRank; });
        filters.innerHTML = res.hits.length ? ['<button type="button" data-page=""' + (activePage ? "" : ' aria-pressed="true"') + ">すべて（" + res.total + "）</button>"]
          .concat(titles.map(function (e) {
            return '<button type="button" data-page="' + escapeHtml(e.page) + '"' + (activePage === e.page ? ' aria-pressed="true"' : "") + ">" +
              escapeHtml(e.pageTitle) + "（" + counts[e.page] + "）</button>";
          })).join("") : "";
        var shown = res.hits.filter(function (h) { return !activePage || h.e.page === activePage; });
        var note = modeNote(res);
        status.textContent = res.hits.length
          ? "「" + q + "」で " + res.total + " 件見つかりました。" + (note ? note + "。" : "")
          : "「" + q + "」は見つかりませんでした。別の言い方（例：「取消」→「キャンセル」）や、短い言葉でお試しください。";
        list.innerHTML = shown.map(function (h) {
          var e = h.e;
          return '<li><a class="search-result" href="' + escapeHtml(resultHref(e, q)) + '">' +
            '<span class="search-result-page">' + escapeHtml(e.pageTitle) + "</span>" +
            '<span class="search-result-heading">' + highlight(e.heading, words) + "</span>" +
            '<span class="search-result-snippet">' + snippet(e.text, words, PAGE_SNIPPET_LEN) + "</span></a></li>";
        }).join("");
      }).catch(function () {
        status.textContent = "検索データを読み込めませんでした。ページを再読み込みしてください。";
      });
    }

    filters.addEventListener("click", function (ev) {
      var b = ev.target.closest("button[data-page]");
      if (!b) return;
      activePage = b.getAttribute("data-page");
      draw();
    });
    form.addEventListener("submit", function (ev) { ev.preventDefault(); clearTimeout(timer); draw(); });
    input.addEventListener("input", function (ev) { if (ev.isComposing) return; clearTimeout(timer); timer = setTimeout(draw, 150); });
    input.addEventListener("compositionend", function () { clearTimeout(timer); timer = setTimeout(draw, 150); });
    input.value = new URLSearchParams(location.search).get("q") || "";
    draw();
    if (!input.value) input.focus();
  }

  function init() {
    var forms = document.querySelectorAll("[data-site-search]");
    var widgets = [];
    for (var i = 0; i < forms.length; i++) { var w = setup(forms[i]); if (w) widgets.push(w); }
    var resultsPage = document.querySelector("[data-search-page]");
    if (resultsPage) { setupResultsPage(resultsPage); return; }
    var q = new URLSearchParams(location.search).get("q");
    if (q && widgets.length) {
      // トップページでは大きな検索ボックスを優先
      var target = document.querySelector("[data-site-search].site-search--hero input[type=search]");
      var w2 = widgets.filter(function (w) { return w.input === target; })[0] || widgets[0];
      w2.input.value = q;
      w2.render();
    }
    highlightFromUrl();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();

  // テスト用に正規化と検索を公開
  window.ManualSearch = { normalize: normalize, loadData: loadData, search: function (q) { return loadData().then(function (d) { return search(q, d); }); } };
})();
