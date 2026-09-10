from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

import requests

try:
    from scripts.update_inbound_data import PREFECTURES, validate_dataset
except ModuleNotFoundError:  # Direct execution: python scripts/generate_inbound_insights.py
    from update_inbound_data import PREFECTURES, validate_dataset


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "inbound" / "latest.json"
OUTPUT_PATH = ROOT / "data" / "inbound" / "insights.json"
DEFAULT_MODEL = "gemini-2.5-flash"
API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"
BATCH_SIZE = 6
REQUEST_INTERVAL_SECONDS = 6.0
KINDS = ("observation", "comparison", "action")
FACT_IDS = (
    "period",
    "total",
    "national_share",
    "largest_market",
    "specialized_market",
    "monthly_change",
    "top_markets",
)
FORBIDDEN_PHRASES = (
    "必ず",
    "確実に",
    "需要が伸びる",
    "需要が増える",
    "成長が見込まれる",
    "原因は",
    "投資すべき",
)


def ensure_github_actions_environment() -> None:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("Geminiによるインサイト生成はGitHub Actions内でのみ実行できます。")


def canonical_digest(dataset: dict[str, Any]) -> str:
    canonical = json.dumps(
        dataset,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def generator_digest() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def format_number(value: float | int) -> str:
    return f"{round(value):,}"


def format_percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def market_rows(dataset: dict[str, Any], area: str) -> list[dict[str, Any]]:
    record = dataset["national"] if area == "全国" else dataset["prefectures"][area]
    local_total = record["foreign_guest_nights"]
    national = dataset["national"]
    national_total = national["foreign_guest_nights"]
    rows = []
    for name, value in record["nationality"].items():
        if name == "その他" or value <= 0:
            continue
        national_value = national["nationality"].get(name, 0)
        local_share = value / local_total if local_total else 0
        national_share = national_value / national_total if national_total else 0
        specialization = local_share / national_share if national_share else 0
        rows.append(
            {
                "name": name,
                "value": value,
                "local_share": local_share,
                "national_share": national_share,
                "specialization": specialization,
            }
        )
    return sorted(rows, key=lambda row: row["value"], reverse=True)


def build_area_facts(dataset: dict[str, Any], area: str) -> dict[str, Any]:
    record = dataset["national"] if area == "全国" else dataset["prefectures"][area]
    metadata = dataset["metadata"]
    rows = market_rows(dataset, area)
    if not rows:
        raise ValueError(f"{area}の国・地域別データがありません。")

    largest = rows[0]
    specialized = max(rows, key=lambda row: row["specialization"])
    national_total = dataset["national"]["foreign_guest_nights"]
    national_share = record["foreign_guest_nights"] / national_total if national_total else 0
    monthly = record["monthly"]
    latest = monthly[-1]
    previous = monthly[-2] if len(monthly) > 1 else None

    facts = [
        {
            "id": "period",
            "text": f"分析対象は{metadata['year']}年{metadata['month']}月（{metadata['release_type']}）です。",
        },
        {
            "id": "total",
            "text": f"{area}の外国人延べ宿泊者数は{format_number(record['foreign_guest_nights'])}人泊です。",
        },
        {
            "id": "national_share",
            "text": (
                f"{area}の全国シェアは{format_percent(national_share)}です。"
                if area != "全国"
                else "全国値のため都道府県別の全国シェア比較は行いません。"
            ),
        },
        {
            "id": "largest_market",
            "text": (
                f"宿泊者数が最大の市場は{largest['name']}で、{format_number(largest['value'])}人泊、"
                f"地域内シェアは{format_percent(largest['local_share'])}です。"
            ),
        },
        {
            "id": "specialized_market",
            "text": (
                f"全国比で地域特化度が最も高い市場は{specialized['name']}で、指数は{specialized['specialization']:.2f}です。"
                if area != "全国"
                else "全国値では地域特化度を市場の優先判断に使用しません。"
            ),
        },
    ]

    if previous and previous["foreign_guest_nights"]:
        change = (latest["foreign_guest_nights"] - previous["foreign_guest_nights"]) / previous["foreign_guest_nights"]
        facts.append(
            {
                "id": "monthly_change",
                "text": (
                    f"直近月は{format_number(latest['foreign_guest_nights'])}人泊で、"
                    f"前月の{format_number(previous['foreign_guest_nights'])}人泊から{format_percent(change)}変化しました。"
                ),
            }
        )
    else:
        facts.append({"id": "monthly_change", "text": "前月比を算出できません。"})

    top_markets = "、".join(
        f"{row['name']} {format_number(row['value'])}人泊（地域内{format_percent(row['local_share'])}）"
        for row in rows[:5]
    )
    facts.append({"id": "top_markets", "text": f"宿泊者数上位5市場は、{top_markets}です。"})
    return {"area": area, "facts": facts}


def response_schema(areas: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "insights": {
                "type": "array",
                "minItems": len(areas),
                "maxItems": len(areas),
                "items": {
                    "type": "object",
                    "properties": {
                        "area": {"type": "string", "enum": areas},
                        "paragraphs": {
                            "type": "array",
                            "minItems": 3,
                            "maxItems": 3,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "kind": {"type": "string", "enum": list(KINDS)},
                                    "text": {"type": "string"},
                                    "fact_ids": {
                                        "type": "array",
                                        "minItems": 1,
                                        "maxItems": 4,
                                        "items": {"type": "string", "enum": list(FACT_IDS)},
                                    },
                                },
                                "required": ["kind", "text", "fact_ids"],
                            },
                        },
                    },
                    "required": ["area", "paragraphs"],
                },
            }
        },
        "required": ["insights"],
    }


def build_prompt(batch: list[dict[str, Any]]) -> str:
    facts_json = json.dumps(batch, ensure_ascii=False, indent=2)
    return f"""あなたは旅館・ホテル経営者向けの統計分析編集者です。
以下のFACTSだけを根拠として、各地域のショートインサイトを日本語で作成してください。

厳守事項:
- 各地域について observation、comparison、action の順で3段落を作る。
- 各段落は45〜130文字、改行・Markdown・URLを含めない。
- 数字はFACTSに書かれた表記をそのまま使い、新しい数字や計算結果を作らない。
- 旅行者の動機、増減の原因、将来需要、施策の成果を推測・断定しない。
- actionは確認・検討の観点を示すに留め、投資や成果を断定しない。
- 各段落のfact_idsには、その文章で実際に使ったFACTSのidだけを入れる。
- 外部知識を使わず、与えられた市場名以外の地名・施設・イベントを追加しない。
- JSONスキーマに一致するJSONだけを返す。

FACTS:
{facts_json}
"""


def _normalise_number(token: str) -> str:
    return token.replace(",", "")


def _numeric_tokens(text: str) -> set[str]:
    return {
        _normalise_number(match)
        for match in re.findall(r"\d[\d,]*(?:\.\d+)?%?", text)
    }


def validate_area_insight(entry: dict[str, Any], area_facts: dict[str, Any]) -> dict[str, Any]:
    area = area_facts["area"]
    if entry.get("area") != area:
        raise ValueError(f"地域名が一致しません: {entry.get('area')} / {area}")
    paragraphs = entry.get("paragraphs")
    if not isinstance(paragraphs, list) or len(paragraphs) != 3:
        raise ValueError(f"{area}の段落数が3ではありません。")
    if [paragraph.get("kind") for paragraph in paragraphs] != list(KINDS):
        raise ValueError(f"{area}の段落種別または順序が不正です。")

    facts_by_id = {fact["id"]: fact["text"] for fact in area_facts["facts"]}
    allowed_markets = {
        name
        for name in dataset_market_names(area_facts)
    }

    for paragraph in paragraphs:
        text = paragraph.get("text")
        fact_ids = paragraph.get("fact_ids")
        if not isinstance(text, str) or not 20 <= len(text) <= 180:
            raise ValueError(f"{area}の文章長が不正です。")
        if "\n" in text or "http" in text.lower() or any(mark in text for mark in ("#", "*", "```")):
            raise ValueError(f"{area}の文章に禁止形式が含まれます。")
        if any(phrase in text for phrase in FORBIDDEN_PHRASES):
            raise ValueError(f"{area}の文章に断定的な表現が含まれます。")
        if not isinstance(fact_ids, list) or not fact_ids or not set(fact_ids) <= set(facts_by_id):
            raise ValueError(f"{area}のfact_idsが不正です。")
        referenced_numbers = _numeric_tokens(" ".join(facts_by_id[fact_id] for fact_id in fact_ids))
        if not _numeric_tokens(text) <= referenced_numbers:
            raise ValueError(f"{area}の文章に根拠のない数字が含まれます。")

    combined = "".join(paragraph["text"] for paragraph in paragraphs)
    if area not in combined and not any(market in combined for market in allowed_markets):
        raise ValueError(f"{area}の文章が地域または市場の事実に結び付いていません。")
    if not any(word in paragraphs[2]["text"] for word in ("確認", "検討", "候補", "材料", "比較")):
        raise ValueError(f"{area}のaction段落が検討事項として書かれていません。")
    return entry


def dataset_market_names(area_facts: dict[str, Any]) -> set[str]:
    top_text = next(
        fact["text"] for fact in area_facts["facts"] if fact["id"] == "top_markets"
    )
    return {
        name
        for name in (
            "韓国", "中国", "香港", "台湾", "米国", "カナダ", "英国", "ドイツ", "フランス",
            "ロシア", "シンガポール", "タイ", "マレーシア", "インド", "オーストラリア",
            "インドネシア", "ベトナム", "フィリピン", "イタリア", "スペイン", "北欧地域",
            "中東地域", "メキシコ",
        )
        if name in top_text
    }


def extract_response_payload(response: dict[str, Any]) -> dict[str, Any]:
    try:
        parts = response["candidates"][0]["content"]["parts"]
        text = "".join(part.get("text", "") for part in parts)
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("Geminiの応答本文を取得できません。") from exc
    if not text.strip():
        raise ValueError("Geminiの応答本文が空です。")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("Geminiの応答がJSONではありません。") from exc


def request_gemini(
    api_key: str,
    model: str,
    batch: list[dict[str, Any]],
    *,
    post: Callable[..., Any] = requests.post,
    max_attempts: int = 3,
) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", model):
        raise ValueError("Geminiモデル名が不正です。")
    areas = [item["area"] for item in batch]
    payload = {
        "contents": [{"role": "user", "parts": [{"text": build_prompt(batch)}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": response_schema(areas),
            "temperature": 0.2,
            "maxOutputTokens": 4096,
        },
    }
    url = f"{API_ROOT}/{quote(model, safe='-_.')}:generateContent"
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = post(
                url,
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json=payload,
                timeout=120,
            )
            if response.status_code == 429 or response.status_code >= 500:
                raise requests.HTTPError(f"一時的なGemini APIエラー: {response.status_code}")
            response.raise_for_status()
            result = extract_response_payload(response.json())
            validate_batch_output(result, batch)
            return result
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < max_attempts:
                time.sleep(2 ** (attempt - 1))
    raise RuntimeError("Gemini APIによるインサイト生成に失敗しました。") from last_error


def validate_batch_output(
    payload: dict[str, Any],
    batch: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    entries = payload.get("insights")
    if not isinstance(entries, list) or len(entries) != len(batch):
        raise ValueError("Gemini応答の地域数が一致しません。")
    by_area = {}
    facts_by_area = {item["area"]: item for item in batch}
    for entry in entries:
        area = entry.get("area") if isinstance(entry, dict) else None
        if area not in facts_by_area or area in by_area:
            raise ValueError("Gemini応答の地域名が不正または重複しています。")
        by_area[area] = validate_area_insight(entry, facts_by_area[area])
    if set(by_area) != set(facts_by_area):
        raise ValueError("Gemini応答に不足地域があります。")
    return by_area


def existing_output_is_current(path: Path, digest: str, model: str, areas: list[str]) -> bool:
    if not path.exists():
        return False
    try:
        current = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    metadata = current.get("metadata", {})
    return (
        metadata.get("status") == "generated"
        and metadata.get("data_sha256") == digest
        and metadata.get("generator_sha256") == generator_digest()
        and metadata.get("model") == model
        and set(current.get("insights", {})) == set(areas)
    )


def generate_all(
    dataset: dict[str, Any],
    api_key: str,
    model: str,
    *,
    requester: Callable[[str, str, list[dict[str, Any]]], dict[str, Any]] = request_gemini,
) -> dict[str, Any]:
    areas = ["全国", *PREFECTURES]
    insights: dict[str, Any] = {}
    for start in range(0, len(areas), BATCH_SIZE):
        batch_areas = areas[start : start + BATCH_SIZE]
        batch = [build_area_facts(dataset, area) for area in batch_areas]
        print(f"Gemini insight batch: {batch_areas[0]} - {batch_areas[-1]}")
        payload = requester(api_key, model, batch)
        insights.update(validate_batch_output(payload, batch))
        if start + BATCH_SIZE < len(areas):
            time.sleep(max(0.0, float(os.environ.get("GEMINI_REQUEST_INTERVAL_SECONDS", REQUEST_INTERVAL_SECONDS))))

    metadata = dataset["metadata"]
    return {
        "metadata": {
            "status": "generated",
            "generator": "Gemini API",
            "model": model,
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "source_year": metadata["year"],
            "source_month": metadata["month"],
            "source_release_type": metadata["release_type"],
            "source_updated_at": metadata["updated_at"],
            "data_sha256": canonical_digest(dataset),
            "generator_sha256": generator_digest(),
        },
        "insights": insights,
    }


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> None:
    ensure_github_actions_environment()
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEYが設定されていません。")
    model = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    dataset = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    validate_dataset(dataset)
    digest = canonical_digest(dataset)
    areas = ["全国", *PREFECTURES]
    if existing_output_is_current(OUTPUT_PATH, digest, model, areas):
        print("AI insights are already current.")
        return
    result = generate_all(dataset, api_key, model)
    write_json_atomic(OUTPUT_PATH, result)
    print(f"Saved {len(result['insights'])} Gemini insights to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
