import json
import math
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from openpyxl import Workbook

from scripts.generate_inbound_insights import (
    GeminiRequestError,
    build_area_facts,
    canonical_digest,
    ensure_github_actions_environment as ensure_insight_actions_environment,
    existing_output_is_current,
    generator_digest,
    request_gemini,
    validate_batch_output,
)
from scripts.update_inbound_data import (
    PREFECTURES,
    ensure_github_actions_environment,
    extract_nationality_table,
    validate_dataset,
)


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "inbound" / "latest.json"
INSIGHTS_PATH = ROOT / "data" / "inbound" / "insights.json"
HTML_PATH = ROOT / "inbound-analysis.html"
JS_PATH = ROOT / "js" / "inbound-analysis.js"
CSS_PATH = ROOT / "css" / "inbound-analysis.css"
USEFUL_PATH = ROOT / "useful.html"
INDEX_PATH = ROOT / "index.html"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "update-inbound-data.yml"


def load_data():
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def load_insights():
    return json.loads(INSIGHTS_PATH.read_text(encoding="utf-8"))


def walk_values(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from walk_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_values(child)
    else:
        yield value


def test_json_schema():
    data = load_data()
    assert set(data) == {"metadata", "national", "prefectures"}
    assert data["metadata"]["release_type"] == "第2次速報"
    assert data["metadata"]["unit"] == "人泊"
    assert {"foreign_guest_nights", "nationality", "monthly"} <= set(data["national"])


def test_checked_in_dataset_passes_release_validation():
    validate_dataset(load_data())


def test_checked_in_insight_placeholder_is_safe_and_local():
    insights = load_insights()
    assert insights["metadata"]["generator"] == "Gemini API"
    assert insights["metadata"]["status"] in {"pending", "generated"}
    assert isinstance(insights["insights"], dict)
    if insights["metadata"]["status"] == "pending":
        assert insights["insights"] == {}
    else:
        assert insights["metadata"]["data_sha256"] == canonical_digest(load_data())
        assert set(insights["insights"]) == {"全国", *PREFECTURES}


def test_area_facts_are_derived_from_checked_in_statistics():
    dataset = load_data()
    area_facts = build_area_facts(dataset, "長野県")
    assert area_facts["area"] == "長野県"
    assert {fact["id"] for fact in area_facts["facts"]} == {
        "period", "total", "national_share", "largest_market",
        "specialized_market", "monthly_change", "top_markets",
    }
    assert str(dataset["prefectures"]["長野県"]["foreign_guest_nights"])[0] in "".join(
        fact["text"].replace(",", "") for fact in area_facts["facts"]
    )


def test_gemini_output_validation_accepts_grounded_three_part_insight():
    area_facts = build_area_facts(load_data(), "長野県")
    largest_market = next(
        fact["text"].split("市場は", 1)[1].split("で", 1)[0]
        for fact in area_facts["facts"]
        if fact["id"] == "largest_market"
    )
    payload = {
        "insights": [{
            "area": "長野県",
            "paragraphs": [
                {"kind": "observation", "text": f"長野県では、{largest_market}が宿泊者数で最大の市場となっており、構成を確認する際の起点になります。", "fact_ids": ["largest_market"]},
                {"kind": "comparison", "text": "全国との構成比の違いを見ることで、この地域で相対的に特徴のある市場を整理できます。", "fact_ids": ["national_share", "specialized_market"]},
                {"kind": "action", "text": "上位市場と地域特化度を比較し、既存の予約実績と照合しながら情報発信の優先候補を検討できます。", "fact_ids": ["top_markets", "specialized_market"]},
            ],
        }]
    }
    result = validate_batch_output(payload, [area_facts])
    assert result["長野県"]["paragraphs"][0]["kind"] == "observation"


def test_gemini_output_validation_rejects_unsupported_numbers():
    area_facts = build_area_facts(load_data(), "長野県")
    payload = {
        "insights": [{
            "area": "長野県",
            "paragraphs": [
                {"kind": "observation", "text": "長野県では9,999,999人泊という根拠のない数値を含む文章です。", "fact_ids": ["total"]},
                {"kind": "comparison", "text": "全国との構成比の違いを確認し、地域の市場構成を比較するための参考情報として扱います。", "fact_ids": ["national_share"]},
                {"kind": "action", "text": "公的統計と施設の予約実績を照合しながら、情報発信の対象市場を慎重に検討できます。", "fact_ids": ["top_markets"]},
            ],
        }]
    }
    with pytest.raises(ValueError, match="根拠のない数字"):
        validate_batch_output(payload, [area_facts])


def test_current_ai_output_detection_uses_data_digest_and_model():
    dataset = load_data()
    digest = canonical_digest(dataset)
    areas = ["全国", *PREFECTURES]
    content = json.dumps({
        "metadata": {"status": "generated", "data_sha256": digest, "generator_sha256": generator_digest(), "model": "gemini-2.5-flash"},
        "insights": {area: {} for area in areas},
    }, ensure_ascii=False)

    class FakePath:
        @staticmethod
        def exists():
            return True

        @staticmethod
        def read_text(encoding):
            assert encoding == "utf-8"
            return content

    path = FakePath()
    assert existing_output_is_current(path, digest, "gemini-2.5-flash", areas)
    assert not existing_output_is_current(path, "different", "gemini-2.5-flash", areas)


def test_gemini_request_uses_current_response_format_and_redacts_errors():
    area_facts = build_area_facts(load_data(), "長野県")
    captured = {}

    class BadResponse:
        status_code = 400
        text = 'invalid request for secret-key-value'

    def fake_post(url, *, headers, json, timeout):
        captured.update(url=url, headers=headers, json=json, timeout=timeout)
        return BadResponse()

    with pytest.raises(GeminiRequestError) as exc_info:
        request_gemini(
            "secret-key-value",
            "gemini-2.5-flash",
            [area_facts],
            post=fake_post,
        )

    generation_config = captured["json"]["generationConfig"]
    assert "responseFormat" in generation_config
    assert "responseSchema" not in generation_config
    assert generation_config["responseFormat"]["text"]["mimeType"] == "APPLICATION_JSON"
    assert generation_config["thinkingConfig"] == {"thinkingBudget": 0}
    assert generation_config["maxOutputTokens"] == 8192
    assert "secret-key-value" not in str(exc_info.value)


def test_all_prefectures_exist():
    data = load_data()
    assert set(data["prefectures"]) == set(PREFECTURES)
    assert len(data["prefectures"]) == 47


def test_national_data_exists():
    national = load_data()["national"]
    assert isinstance(national["foreign_guest_nights"], int)
    assert national["foreign_guest_nights"] > 0
    assert len(national["monthly"]) >= 6


def test_no_negative_values():
    data = load_data()
    for record in [data["national"], *data["prefectures"].values()]:
        assert record["foreign_guest_nights"] >= 0
        assert all(value >= 0 for value in record["nationality"].values())
        assert all(item["foreign_guest_nights"] >= 0 for item in record["monthly"])


def test_nationality_data_exists():
    data = load_data()
    assert len(data["national"]["nationality"]) >= 10
    assert all(len(record["nationality"]) >= 10 for record in data["prefectures"].values())


def test_latest_month_valid():
    metadata = load_data()["metadata"]
    assert 2007 <= metadata["year"] <= date.today().year + 1
    assert 1 <= metadata["month"] <= 12


def test_no_nan():
    for value in walk_values(load_data()):
        if isinstance(value, float):
            assert math.isfinite(value)


def test_excel_table_parser_uses_headers_and_prefecture_labels():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "参考第1表(6月)"
    sheet.append(["施設所在地(47区分)、国籍（出身地）別外国人延べ宿泊者数"])
    sheet.append(["（客室数20室以上の施設）"])
    sheet.append([])
    sheet.append(["施設所在地（47区分）", "外国人延べ宿泊者数", "国籍（出身地）"])
    countries = ["韓国", "中国", "香港", "台湾", "米国", "カナダ", "英国", "ドイツ", "フランス", "その他"]
    sheet.append([None, None, *countries])
    sheet.append([])
    sheet.append(["令和8年6月", 47000, *([1000] * len(countries))])
    for index, prefecture in enumerate(PREFECTURES, 1):
        sheet.append([f"　{index:02d}{prefecture}", 1000, *([10] * len(countries))])

    parsed = extract_nationality_table(workbook)
    assert parsed["survey_scope"] == "客室数20室以上の施設"
    assert parsed["national"]["foreign_guest_nights"] == 47000
    assert parsed["prefectures"]["長野県"]["nationality"]["台湾"] == 10


def test_validation_rejects_first_preliminary_data():
    data = deepcopy(load_data())
    data["metadata"]["release_type"] = "第1次速報"
    with pytest.raises(ValueError, match="第2次速報以外"):
        validate_dataset(data)


def test_validation_rejects_missing_prefecture():
    data = deepcopy(load_data())
    data["prefectures"].pop("沖縄県")
    with pytest.raises(ValueError, match="47都道府県"):
        validate_dataset(data)


def test_initial_html_exposes_only_loading_state():
    soup = BeautifulSoup(HTML_PATH.read_text(encoding="utf-8"), "html.parser")
    loading = soup.find(id="data-loading")
    error = soup.find(id="data-error")
    dashboard = soup.find(id="analysis-dashboard")

    assert loading and not loading.has_attr("hidden")
    assert loading.get_text(" ", strip=True) == "最新統計を読み込んでいます"
    assert error and error.has_attr("hidden") and not error.get_text(strip=True)
    assert dashboard and dashboard.has_attr("hidden") and dashboard.has_attr("inert")
    assert "現在、最新統計を取得できません" not in HTML_PATH.read_text(encoding="utf-8")
    assert soup.find("noscript").get_text(" ", strip=True) == "JavaScriptを有効にしてください この分析ツールの表示にはJavaScriptが必要です。"
    assert all(not soup.find(id=element_id).get_text(strip=True) for element_id in (
        "kpi-total", "kpi-total-unit", "kpi-national-share", "kpi-largest-market",
        "kpi-largest-value", "kpi-specialized-market", "kpi-specialized-value",
        "source-period", "source-updated", "source-unit", "source-scope",
    ))


def test_monthly_series_has_latest_twelve_second_preliminary_months():
    data = load_data()
    expected_latest = (data["metadata"]["year"], data["metadata"]["month"])
    for record in [data["national"], *data["prefectures"].values()]:
        monthly = record["monthly"]
        periods = [(item["year"], item["month"]) for item in monthly]
        assert len(monthly) == 12
        assert periods == sorted(periods)
        assert len(set(periods)) == 12
        assert periods[-1] == expected_latest


def test_all_market_calculations_are_finite_and_scores_are_bounded():
    data = load_data()
    national = data["national"]
    national_total = national["foreign_guest_nights"]
    assert national_total > 0

    for record in [national, *data["prefectures"].values()]:
        local_total = record["foreign_guest_nights"]
        assert 0 <= local_total <= national_total
        markets = []
        for name, value in record["nationality"].items():
            if name == "その他" or value <= 0:
                continue
            national_value = national["nationality"].get(name, 0)
            local_share = value / local_total if local_total else 0
            national_share = national_value / national_total if national_total else 0
            specialization = local_share / national_share if national_share else 0
            assert all(math.isfinite(number) for number in (local_share, national_share, specialization))
            assert 0 <= local_share <= 1
            assert 0 <= national_share <= 1
            markets.append((value, specialization))

        assert markets
        max_value = max(value for value, _ in markets)
        for value, specialization in markets:
            score = (value / max_value) * 0.6 + min(specialization / 2.5, 1) * 0.4
            assert math.isfinite(score)
            assert 0 <= score <= 1


def test_prefecture_slugs_cover_all_prefectures():
    import re

    javascript = JS_PATH.read_text(encoding="utf-8")
    pairs = re.findall(r"\['([^']+)', '([a-z]+)'\]", javascript)
    assert len(pairs) == 47
    assert {name for name, _ in pairs} == set(PREFECTURES)
    assert len({slug for _, slug in pairs}) == 47
    assert ("鹿児島県", "kagoshima") in pairs
    assert "return slugToPrefecture.get(slug) || '全国';" in javascript
    assert "url.searchParams.set('pref', prefectureToSlug.get(area));" in javascript


def test_runtime_assets_are_local_except_existing_google_analytics():
    soup = BeautifulSoup(HTML_PATH.read_text(encoding="utf-8"), "html.parser")
    runtime_urls = []
    for tag in soup.find_all(["script", "link", "img", "iframe"]):
        if tag.name == "link" and "stylesheet" not in (tag.get("rel") or []):
            continue
        url = tag.get("src") or tag.get("href")
        if url:
            runtime_urls.append(url)

    external = [url for url in runtime_urls if url.startswith(("http://", "https://", "//"))]
    assert external == ["https://www.googletagmanager.com/gtag/js?id=GT-M3S9S5D7"]
    assert soup.find("iframe") is None
    javascript = JS_PATH.read_text(encoding="utf-8")
    assert "fetch('data/inbound/latest.json'" in javascript
    assert "fetch('data/inbound/insights.json'" in javascript
    assert "https://" not in javascript
    stylesheet = CSS_PATH.read_text(encoding="utf-8")
    assert "@import" not in stylesheet
    assert "url(http" not in stylesheet


def test_old_demo_implementation_is_absent():
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (HTML_PATH, JS_PATH, USEFUL_PATH, INDEX_PATH)
    ).lower()
    for forbidden in ("sample", "demo", "サンプル", "デモ", "chatgpt.site", "lab.ugatta-llc.com", "iframe"):
        assert forbidden not in combined


def test_metadata_and_accessible_structure_are_complete():
    soup = BeautifulSoup(HTML_PATH.read_text(encoding="utf-8"), "html.parser")
    assert len(soup.find_all("h1")) == 1
    assert soup.find("label", attrs={"for": "prefecture-select"})
    assert soup.find(id="trend-chart", attrs={"role": "img"})
    assert soup.find(id="trend-values")
    assert soup.find("link", attrs={"rel": "canonical"})["href"] == "https://ugatta-llc.com/inbound-analysis.html"
    assert "公的統計" in soup.find("meta", attrs={"name": "twitter:description"})["content"]
    structured_data = json.loads(soup.find("script", attrs={"type": "application/ld+json"}).string)
    types = {item["@type"] for item in structured_data["@graph"]}
    assert {"BreadcrumbList", "WebApplication", "FAQPage"} <= types


def test_update_workflow_is_scheduled_manual_and_fail_closed():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "schedule:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "python scripts/update_inbound_data.py" in workflow
    assert "GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}" in workflow
    assert "python scripts/generate_inbound_insights.py" in workflow
    assert "data/inbound/insights.json" in workflow
    assert "python -m pytest -q" in workflow
    assert "git diff --quiet" in workflow
    assert "git push" in workflow


def test_data_update_is_blocked_outside_github_actions(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(RuntimeError, match="GitHub Actions"):
        ensure_github_actions_environment()


def test_ai_generation_is_blocked_outside_github_actions(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(RuntimeError, match="GitHub Actions"):
        ensure_insight_actions_environment()


def test_data_metadata_points_to_official_source_and_excel():
    metadata = load_data()["metadata"]
    assert metadata["source"] == "観光庁 宿泊旅行統計調査"
    assert metadata["source_url"].startswith("https://www.mlit.go.jp/kankocho/")
    assert metadata["excel_url"].startswith("https://www.mlit.go.jp/kankocho/content/")
    assert metadata["excel_url"].endswith(".xlsx")
    assert metadata["nationality_coverage"]
