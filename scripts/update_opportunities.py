#!/usr/bin/env python3
"""기업마당 지원사업정보 API -> GitHub Pages 공개 공고 JSON.

Requires BIZINFO_API_KEY in GitHub Actions repository secret. Uses Python stdlib.
Never stores API credentials, company-specific internal material or personal data.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "opportunities.json"
BIZINFO = "https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do"
TYPES = [
    ("오픈이노베이션", "오픈이노베이션", "open innovation", "협업 프로그램", "민관협력", "대기업 협력"),
    ("실증·PoC", "실증", "테스트베드", "시범사업", "poc", "성능검증", "사업화 검증"),
    ("투자·IR", "투자유치", "ir 데이", "벤처투자", "데모데이", "투자설명회"),
    ("행사·네트워킹", "네트워킹", "박람회", "세미나", "컨퍼런스", "포럼", "설명회", "교육생"),
    ("R&D·기술", "연구개발", "r&d", "기술개발", "기술고도화", "과제수행"),
    ("사업화·자금", "창업지원", "사업화", "바우처", "수출지원", "판로", "자금지원", "패키지"),
]
KEYWORDS = ("기후", "탄소", "에너지", "친환경", "자원순환", "폐기물", "환경", "수소", "태양", "풍력", "전력", "ESS", "배터리", "수처리", "대기", "소재", "바이오", "공정", "재활용", "수출", "글로벌", "실증", "개발", "창업", "스타트업", "중소기업", "투자", "IR", "혁신", "사업화", "오픈이노베이션", "기술", "제품", "네트워킹", "행사", "인증", "시험", "검증")


def clean_text(s: object) -> str:
    s = re.sub(r"<[^>]*>", " ", str(s or ""))
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def first(obj: dict, *fields: str) -> str:
    for f in fields:
        if obj.get(f):
            return clean_text(obj[f])
    return ""


def parse_dates(s: str) -> tuple[str, str]:
    # Example: '20261101 ~ 20261215', '2026-11-01 ~ 2026-12-15'
    chunks = re.findall(r"(?:20\d{2})[-./]?(?:0[1-9]|1[0-2])[-./]?(?:[0-2]\d|3[01])", s or "")
    values = []
    for raw in chunks[:2]:
        digits = re.sub(r"\D", "", raw)
        try:
            values.append(dt.date(int(digits[:4]), int(digits[4:6]), int(digits[6:8])).isoformat())
        except ValueError:
            pass
    return (values[0] if len(values) > 1 else "", values[-1] if values else "")


def safe_url(value: str) -> str:
    try:
        url = urlparse(value)
        return value if url.scheme in {"http", "https"} and url.netloc else ""
    except (ValueError, TypeError):
        return ""


def get_type(text: str, raw_type: str = "") -> str:
    text = text.lower()
    for row in TYPES:
        if any(key.lower() in text for key in row[1:]):
            return row[0]
    raw = raw_type.lower()
    if raw in ("기술", "인력"):
        return "R&D·기술"
    if raw in ("창업", "금융", "수출", "내수", "경영"):
        return "사업화·자금"
    return "기타"


def normalize(item: dict) -> dict | None:
    title = first(item, "pblancNm", "title")
    url = safe_url(first(item, "pblancUrl", "link"))
    if not title or not url:
        return None
    period = first(item, "reqstBeginEndDe", "reqstDt")
    start, end = parse_dates(period)
    summary = first(item, "bsnsSumryCn", "description")[:650]
    eligibility = first(item, "trgetNm", "supportTarget", "aply_trgt_ctnt")[:240]
    notes = first(item, "reqstMthPapersCn", "refrncNm")[:300]
    agency = first(item, "jrsdInsttNm", "author", "excInsttNm")
    org = first(item, "excInsttNm", "jrsdInsttNm", "author") or agency
    raw_type = first(item, "pldirSportRealmLclasCodeNm", "lcategory")
    rid = first(item, "pblancId", "seq") or hashlib.sha256(url.encode()).hexdigest()[:20]
    haystack = f"{title} {summary} {raw_type} {first(item,'hashTags')}"
    words = [x for x in KEYWORDS if x.lower() in haystack.lower()]
    restriction = "needs_review" if any(word in f"{title} {summary} {eligibility} {notes}" for word in ("중복지원", "중복수혜", "타 사업", "타사업", "동시수행", "지원제외", "신청제외")) else "unverified"
    return {
        "id": f"bizinfo-{rid}",
        "title": title,
        "organization": org,
        "agency": agency,
        "type": get_type(haystack, raw_type),
        "deadline": end,
        "start_date": start,
        "summary": summary,
        "eligibility": eligibility,
        "url": url,
        "published_at": first(item, "creatPnttm", "pubDate")[:19],
        "keywords": words,
        "restriction": restriction,
        "source": "기업마당",
        "source_note": "공고 목록에서 추출한 요약입니다. 지원자격·DIPS 중복수혜 여부는 원문을 확인하세요.",
    }


def json_items(data: object) -> list[dict]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if not isinstance(data, dict):
        return []
    channel = data.get("jsonArray", data.get("channel", data.get("rss", data)))
    if isinstance(channel, dict) and "channel" in channel:
        channel = channel["channel"]
    items = channel.get("item", []) if isinstance(channel, dict) else []
    if isinstance(items, dict):
        items = [items]
    return [x for x in items if isinstance(x, dict)]


def xml_items(body: bytes) -> list[dict]:
    root = ET.fromstring(body)
    results = []
    for node in root.iter("item"):
        results.append({child.tag: "".join(child.itertext()) for child in node})
    return results


def fetch_bizinfo(api_key: str) -> list[dict]:
    url = BIZINFO + "?" + urlencode({"crtfcKey": api_key, "dataType": "json", "searchCnt": "600"})
    req = Request(url, headers={"User-Agent": "KETEP-DIPS-newsletter-prototype/1.0", "Accept": "application/json, application/xml, text/xml"})
    with urlopen(req, timeout=40) as resp:
        body = resp.read(15 * 1024 * 1024)
    try:
        raw = json_items(json.loads(body.decode("utf-8-sig")))
    except (json.JSONDecodeError, UnicodeError):
        raw = xml_items(body)
    if not raw:
        raise RuntimeError("기업마당 API 응답에서 공고 목록을 찾지 못했습니다. API 키·이용권한·응답형식을 확인하세요.")
    items = []
    for r in raw:
        x = normalize(r)
        if x:
            items.append(x)
    return items


def read_previous() -> dict:
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"items": []}


def merged_items(previous: list[dict], incoming: list[dict]) -> list[dict]:
    # Preserve notices if they temporarily disappear from the latest API window.
    entries = {item["id"]: item for item in previous if isinstance(item, dict) and item.get("id")}
    entries.update({item["id"]: item for item in incoming})
    now = dt.date.today()
    kept = []
    for o in entries.values():
        expiry = o.get("deadline") or ""
        if expiry:
            try:
                if (now - dt.date.fromisoformat(expiry)).days > 7:
                    continue
            except ValueError:
                pass
        kept.append(o)
    kept.sort(key=lambda a: (a.get("published_at") or "", a.get("deadline") or ""), reverse=True)
    return kept[:1500]


def main() -> int:
    key = os.environ.get("BIZINFO_API_KEY", "").strip()
    if not key:
        print("[안내] BIZINFO_API_KEY 미설정: 기존 데이터 유지. 자동 수집은 실행되지 않았습니다.")
        return 0
    previous = read_previous()
    try:
        fresh = fetch_bizinfo(key)
        merged = merged_items(previous.get("items", []), fresh)
        now = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(timespec="seconds")
        output = {"updated_at": now, "source_status": f"기업마당 수집 {len(fresh)}건, 저장 {len(merged)}건. 중복수혜 미확인", "items": merged}
        DATA_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"기업마당 수집 {len(fresh)}건, 합계 {len(merged)}건 / {now}")
    except Exception as exc:
        # Never replace a good result with an empty/stale success result.
        print(f"[오류] 수집 실패. 기존 JSON을 보존합니다: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
