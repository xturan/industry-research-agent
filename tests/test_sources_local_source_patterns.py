from __future__ import annotations

from packages.sources.local_source_patterns import (
    classify_local_region_match,
    generic_local_region_terms,
    local_evidence_backbone_for_source_class,
    local_source_domains_for_backbones,
    local_source_domains_for_regions,
    local_source_region_for_domain,
)


def test_exact_county_project_patterns_include_local_and_parent_public_resource() -> None:
    domains = local_source_domains_for_regions(
        ["\u80a5\u897f"],
        "project_public_resource",
        include_parent=True,
    )

    assert "ahfeixi.gov.cn" in domains
    assert "ggzy.hefei.gov.cn" in domains
    assert "aopa.org.cn" not in domains


def test_exact_county_record_patterns_include_environment_and_land_backbones() -> None:
    domains = local_source_domains_for_regions(
        ["\u82e5\u7f8c"],
        "environmental_or_land_record",
        include_parent=True,
    )

    assert "xjrq.gov.cn" in domains
    assert "xjbz.gov.cn" in domains
    assert "sthjt.xinjiang.gov.cn" in domains
    assert "zrzyt.xinjiang.gov.cn" in domains


def test_local_statistics_patterns_include_fiscal_and_parent_statistics() -> None:
    domains = local_source_domains_for_regions(
        ["\u795e\u6728"],
        "statistics",
        include_parent=True,
        include_fiscal=True,
    )

    assert "sxsm.gov.cn" in domains
    assert "tjj.shaanxi.gov.cn" in domains
    assert "czt.shaanxi.gov.cn" in domains


def test_statistics_fiscal_backbone_includes_energy_constraint_domains_when_available() -> None:
    domains = local_source_domains_for_backbones(
        ["\u5185\u8499\u53e4"],
        ["statistics_fiscal"],
        include_parent=True,
    )
    energy_domains = local_source_domains_for_regions(
        ["\u5185\u8499\u53e4"],
        "energy_constraint_data",
        include_parent=True,
    )

    assert "tj.nmg.gov.cn" in domains
    assert "nyj.nmg.gov.cn" in domains
    assert "nyj.nmg.gov.cn" in energy_domains


def test_local_source_domain_region_lookup_supports_new_pattern_domains() -> None:
    assert local_source_region_for_domain("www.ggzy.hefei.gov.cn") == "\u5408\u80a5"
    assert local_source_region_for_domain("sthjt.xinjiang.gov.cn") == "\u65b0\u7586"
    assert local_source_region_for_domain("xcaib.xa.gov.cn") == "\u897f\u5b89"


def test_generic_local_region_terms_rejects_non_admin_suffix_words() -> None:
    terms = generic_local_region_terms(
        "\u5730\u65b9\u6276\u6301\u548c\u5e02\u573a\u4ef7\u683c\uff0c"
        "\u8bf7\u533a\u5206\u653f\u7b56\u76ee\u6807\u548c\u8d44\u91d1\u6765\u6e90\u3002"
    )

    assert terms == []


def test_generic_local_region_terms_accepts_unknown_city_county_flag_names() -> None:
    terms = generic_local_region_terms(
        "\u6606\u5c71\u5e02\u7535\u5b50\u4fe1\u606f\u3001"
        "\u66f9\u53bf\u7535\u5546\u548c\u51c6\u683c\u5c14\u65d7\u80fd\u6e90\u9879\u76ee"
    )

    assert terms == ["\u6606\u5c71", "\u66f9\u53bf", "\u51c6\u683c\u5c14"]


def test_source_classes_map_to_general_local_evidence_backbones() -> None:
    assert local_evidence_backbone_for_source_class("local_government") == "local_government"
    assert local_evidence_backbone_for_source_class("project_list") == "project_public_resource"
    assert (
        local_evidence_backbone_for_source_class("tender_or_procurement")
        == "project_public_resource"
    )
    assert local_evidence_backbone_for_source_class("statistics") == "statistics_fiscal"
    assert (
        local_evidence_backbone_for_source_class("environmental_record")
        == "environmental_land_record"
    )
    assert local_evidence_backbone_for_source_class("unknown_source_class") is None


def test_backbone_domain_union_reuses_underlying_source_class_patterns() -> None:
    domains = local_source_domains_for_backbones(
        ["\u80a5\u897f"],
        ["project_public_resource", "environmental_land_record"],
        include_parent=True,
    )

    assert "ahfeixi.gov.cn" in domains
    assert "ggzy.hefei.gov.cn" in domains
    assert "sthjj.hefei.gov.cn" in domains
    assert "zrzy.hefei.gov.cn" in domains


def test_backbone_domain_union_respects_fiscal_flag() -> None:
    domains_without_fiscal = local_source_domains_for_backbones(
        ["\u795e\u6728"],
        ["statistics_fiscal"],
        include_parent=True,
        include_fiscal=False,
    )
    domains_with_fiscal = local_source_domains_for_backbones(
        ["\u795e\u6728"],
        ["statistics_fiscal"],
        include_parent=True,
        include_fiscal=True,
    )

    assert "tjj.shaanxi.gov.cn" in domains_without_fiscal
    assert "czt.shaanxi.gov.cn" not in domains_without_fiscal
    assert "czt.shaanxi.gov.cn" in domains_with_fiscal


def test_local_region_match_distinguishes_child_parent_and_unrelated_evidence() -> None:
    child_match = classify_local_region_match(
        ["\u5408\u80a5"],
        "\u5b89\u5fbd\u957f\u4e30\u91cd\u70b9\u9879\u76ee\u5efa\u8bbe\u6295\u4ea7",
        candidate_domain="www.ah.gov.cn",
    )
    parent_match = classify_local_region_match(
        ["\u795e\u6728"],
        "\u9655\u897f\u77012024\u5e74\u56fd\u6c11\u7ecf\u6d4e\u548c\u793e\u4f1a\u53d1\u5c55\u7edf\u8ba1\u516c\u62a5",
        candidate_domain="www.shaanxi.gov.cn",
    )
    parent_domain_exact_mention = classify_local_region_match(
        ["\u5408\u80a5"],
        "\u5b89\u5fbd\u7edf\u8ba1\u516c\u62a5\u63d0\u5230\u5408\u80a5\u65b0\u80fd\u6e90\u6c7d\u8f66\u4ea7\u4e1a",
        candidate_domain="www.ah.gov.cn",
    )
    unrelated_match = classify_local_region_match(
        ["\u5408\u80a5"],
        "\u82cf\u5dde\u673a\u5668\u4eba\u91cd\u70b9\u9879\u76ee\u5f00\u5de5",
        candidate_domain="www.suzhou.gov.cn",
    )

    assert child_match["match_type"] == "child_local"
    assert child_match["matched_region"] == "\u957f\u4e30"
    assert parent_match["match_type"] == "parent_local"
    assert parent_match["matched_region"] == "\u9655\u897f"
    assert parent_domain_exact_mention["match_type"] == "parent_local"
    assert parent_domain_exact_mention["matched_region"] == "\u5b89\u5fbd"
    assert unrelated_match["match_type"] == "unrelated_region"


def test_generic_flag_mention_on_provincial_domain_is_parent_evidence() -> None:
    parent_domain_match = classify_local_region_match(
        ["\u51c6\u683c\u5c14"],
        "\u5185\u8499\u53e4\u7edf\u8ba1\u516c\u62a5\u63d0\u5230\u51c6\u683c\u5c14\u65d7\u7164\u5316\u5de5\u9879\u76ee",
        candidate_domain="www.nmg.gov.cn",
    )

    assert parent_domain_match["match_type"] == "parent_local"
    assert parent_domain_match["matched_region"] == "\u5185\u8499\u53e4"
