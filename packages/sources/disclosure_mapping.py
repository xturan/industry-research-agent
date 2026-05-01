from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class DisclosureEntityCandidate:
    name: str
    ticker: str | None = None
    exchange: str | None = None
    role: str = "evidence_anchor"
    confidence: float = 0.7
    tags: tuple[str, ...] = field(default_factory=tuple)

    def search_label(self) -> str:
        return f"{self.name} {self.ticker}".strip() if self.ticker else self.name


@dataclass(frozen=True)
class DisclosureAnnouncementSearchSpec:
    query: str
    entity_candidates: tuple[DisclosureEntityCandidate, ...]
    topic_keywords: tuple[str, ...]
    announcement_types: tuple[str, ...]
    source_ids: tuple[str, ...]
    no_match_reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["entity_candidates"] = [asdict(candidate) for candidate in self.entity_candidates]
        return payload


DIRECT_DISCLOSURE_SOURCE_IDS = (
    "cn_exchange_cninfo_announcement_v1",
    "cn_exchange_sse_notice_v1",
    "cn_exchange_szse_notice_v1",
)

BSE_DISCLOSURE_SOURCE_ID = "cn_exchange_bse_notice_v1"

DEFAULT_ANNOUNCEMENT_TYPES = (
    "年报",
    "半年报",
    "项目进展",
    "投资公告",
    "合同订单",
    "问询回复",
    "风险提示",
)


def build_disclosure_search_spec(text: str) -> DisclosureAnnouncementSearchSpec:
    normalized = " ".join(text.split())
    explicit = _explicit_entity_candidate(normalized)
    topic_keywords = _topic_keywords(normalized)
    candidates = explicit or _topic_entity_candidates(normalized)
    source_ids = _source_ids_for_candidates(candidates)
    if not candidates:
        return DisclosureAnnouncementSearchSpec(
            query=normalized,
            entity_candidates=(),
            topic_keywords=topic_keywords,
            announcement_types=DEFAULT_ANNOUNCEMENT_TYPES,
            source_ids=source_ids,
            no_match_reason="disclosure_no_entity_candidate",
        )
    query = _build_query(candidates, topic_keywords)
    return DisclosureAnnouncementSearchSpec(
        query=query,
        entity_candidates=tuple(candidates),
        topic_keywords=topic_keywords,
        announcement_types=DEFAULT_ANNOUNCEMENT_TYPES,
        source_ids=source_ids,
    )


def disclosure_document_matches_spec(
    *,
    title: str,
    raw_text: str,
    source_uri: str,
    spec_payload: dict[str, object] | None,
) -> bool:
    if not spec_payload:
        return True
    candidates = spec_payload.get("entity_candidates")
    if not isinstance(candidates, list) or not candidates:
        return False
    haystack = f"{title} {raw_text} {source_uri}".lower()
    for item in candidates:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip().lower()
        ticker = str(item.get("ticker") or "").strip().lower()
        ticker_root = ticker.split(".", 1)[0] if ticker else ""
        if name and name in haystack:
            return True
        if ticker and ticker in haystack:
            return True
        if ticker_root and ticker_root in haystack:
            return True
    return False


def _explicit_entity_candidate(text: str) -> tuple[DisclosureEntityCandidate, ...]:
    ticker_match = re.search(r"\b(\d{6})(?:\.(SZ|SH|BJ))?\b", text, flags=re.IGNORECASE)
    company_match = re.search(r"([\u4e00-\u9fa5A-Za-z0-9]{2,16})(?:股份|集团|公司)", text)
    generic_company_names = {"上市", "相关", "重点", "地方", "项目", "产业"}
    if company_match and company_match.group(1) in generic_company_names:
        company_match = None
    if not ticker_match and not company_match:
        return ()
    ticker = None
    exchange = None
    if ticker_match:
        suffix = (ticker_match.group(2) or "").upper()
        exchange = suffix or None
        ticker = f"{ticker_match.group(1)}.{suffix}" if suffix else ticker_match.group(1)
    name = company_match.group(1) if company_match else ticker_match.group(1)
    return (
        DisclosureEntityCandidate(
            name=name,
            ticker=ticker,
            exchange=exchange,
            role="explicit_query_entity",
            confidence=0.95,
            tags=("explicit",),
        ),
    )


def _topic_keywords(text: str) -> tuple[str, ...]:
    rules = (
        (("低空经济", "通航", "无人机", "eVTOL"), ("低空经济", "通用航空", "无人机")),
        (("新能源汽车", "动力电池", "汽车零部件"), ("新能源汽车", "动力电池", "零部件")),
        (("光伏", "储能", "动力电池"), ("光伏", "储能", "动力电池")),
        (("东数西算", "算力", "数据中心", "IDC"), ("算力", "数据中心", "服务器")),
        (("房地产", "城中村", "三大工程", "收储"), ("房地产", "开工", "收入")),
        (("煤炭", "煤化工", "绿氢", "绿电"), ("煤炭", "煤化工", "新能源")),
        (("盐湖", "锂钾", "锂资源"), ("盐湖", "锂", "钾")),
        (("商业航天", "卫星", "硬科技"), ("商业航天", "卫星", "硬科技")),
        (("自由贸易港", "海南", "航运", "医药", "数字贸易"), ("海南", "自贸港", "航运")),
    )
    keywords: list[str] = []
    for triggers, values in rules:
        if any(trigger.lower() in text.lower() for trigger in triggers):
            keywords.extend(values)
    return tuple(_dedupe(keywords))


def _topic_entity_candidates(text: str) -> tuple[DisclosureEntityCandidate, ...]:
    mapping = (
        (
            ("低空经济", "通航", "无人机", "eVTOL"),
            (
                ("中信海直", "000099.SZ", "low_altitude_operator"),
                ("万丰奥威", "002085.SZ", "evtol_aircraft_chain"),
                ("宗申动力", "001696.SZ", "aviation_power"),
            ),
        ),
        (
            ("合肥", "安徽", "肥西", "新能源汽车", "动力电池", "汽车零部件"),
            (
                ("江淮汽车", "600418.SH", "vehicle_oem"),
                ("国轩高科", "002074.SZ", "battery_chain"),
            ),
        ),
        (
            ("光伏", "常州", "储能"),
            (
                ("天合光能", "688599.SH", "pv_module"),
                ("亿纬锂能", "300014.SZ", "battery_storage"),
            ),
        ),
        (
            ("东数西算", "算力", "数据中心", "IDC"),
            (
                ("浪潮信息", "000977.SZ", "server"),
                ("中科曙光", "603019.SH", "server_hpc"),
                ("宝信软件", "600845.SH", "idc_software"),
            ),
        ),
        (
            ("房地产", "城中村", "三大工程", "收储"),
            (
                ("三一重工", "600031.SH", "construction_machinery"),
                ("海尔智家", "600690.SH", "home_appliance"),
                ("东方雨虹", "002271.SZ", "building_material"),
                ("中国建筑", "601668.SH", "construction"),
            ),
        ),
        (
            ("煤炭", "煤化工", "神木", "内蒙古", "绿氢", "绿电"),
            (
                ("陕西煤业", "601225.SH", "coal"),
                ("中国神华", "601088.SH", "coal_power"),
                ("宝丰能源", "600989.SH", "coal_chemical"),
            ),
        ),
        (
            ("盐湖", "锂钾", "若羌"),
            (
                ("盐湖股份", "000792.SZ", "salt_lake_resource"),
                ("藏格矿业", "000408.SZ", "lithium_potash"),
            ),
        ),
        (
            ("西安", "商业航天", "卫星", "硬科技"),
            (
                ("铂力特", "688333.SH", "hard_tech"),
                ("中航西飞", "000768.SZ", "aviation_manufacturing"),
            ),
        ),
        (
            ("海南", "自由贸易港", "自贸港", "航运", "医药", "数字贸易"),
            (
                ("海峡股份", "002320.SZ", "shipping"),
                ("海南机场", "600515.SH", "transport_tourism"),
                ("普利制药", "300630.SZ", "pharma"),
            ),
        ),
    )
    candidates: list[DisclosureEntityCandidate] = []
    lowered = text.lower()
    for triggers, entries in mapping:
        if not any(trigger.lower() in lowered for trigger in triggers):
            continue
        for name, ticker, role in entries:
            exchange = ticker.split(".", 1)[1] if "." in ticker else None
            candidates.append(
                DisclosureEntityCandidate(
                    name=name,
                    ticker=ticker,
                    exchange=exchange,
                    role=role,
                    confidence=0.78,
                    tags=tuple(trigger for trigger in triggers if trigger.lower() in lowered),
                )
            )
    return tuple(_dedupe_candidates(_prioritize_region_tagged_candidates(candidates, text)))


def _prioritize_region_tagged_candidates(
    candidates: list[DisclosureEntityCandidate],
    text: str,
) -> list[DisclosureEntityCandidate]:
    region_terms = set(_region_terms_from_disclosure_text(text))
    if not region_terms:
        return candidates
    return sorted(
        candidates,
        key=lambda candidate: (
            0 if region_terms.intersection(candidate.tags) else 1,
        ),
    )


def _region_terms_from_disclosure_text(text: str) -> list[str]:
    known_regions = {
        "安徽",
        "合肥",
        "肥西",
        "海南",
        "常州",
        "内蒙古",
        "神木",
        "若羌",
        "西安",
        "武汉",
        "深圳",
        "苏州",
        "成都",
        "鄂尔多斯",
        "新疆",
        "江苏",
        "浙江",
        "广东",
        "上海",
    }
    terms: list[str] = []
    for token in re.findall(r"[\u4e00-\u9fff]{2,8}", text):
        candidates = [token]
        if token.endswith(("省", "市", "县", "区", "旗", "州", "盟")):
            candidates.append(token[:-1])
        for candidate in candidates:
            if candidate in known_regions and candidate not in terms:
                terms.append(candidate)
    return terms


def _source_ids_for_candidates(
    candidates: tuple[DisclosureEntityCandidate, ...],
) -> tuple[str, ...]:
    source_ids = list(DIRECT_DISCLOSURE_SOURCE_IDS)
    if any(str(candidate.exchange or "").upper() == "BJ" for candidate in candidates):
        source_ids.append(BSE_DISCLOSURE_SOURCE_ID)
    return tuple(_dedupe(source_ids))


def _build_query(
    candidates: tuple[DisclosureEntityCandidate, ...],
    topic_keywords: tuple[str, ...],
) -> str:
    labels = [candidate.search_label() for candidate in candidates[:3]]
    keywords = list(topic_keywords[:4])
    announcement_terms = ["公告", "披露", "年报", "项目进展"]
    return " ".join(_dedupe([*labels, *keywords, *announcement_terms]))


def _dedupe(values: list[str] | tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _dedupe_candidates(
    candidates: list[DisclosureEntityCandidate],
) -> list[DisclosureEntityCandidate]:
    seen: set[str] = set()
    result: list[DisclosureEntityCandidate] = []
    for candidate in candidates:
        key = candidate.ticker or candidate.name
        if key in seen:
            continue
        seen.add(key)
        result.append(candidate)
    return result
