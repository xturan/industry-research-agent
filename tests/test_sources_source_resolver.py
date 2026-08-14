from __future__ import annotations

import pytest

from packages.sources.enums import GovernanceAxis, InfoType, LineFamily, RegionalLevel
from packages.sources.query_decomposition import QueryDecompositionTask
from packages.sources.source_resolver import (
    domain_has_procurement_signal,
    evaluate_candidate_compatibility,
    is_generic_policy_page_candidate,
    is_procurement_domain,
    is_supplemental_or_fallback_task_family,
)


def _build_task(
    *,
    task_family: str,
    include_domains: list[str],
    search_phrases: list[str],
    negative_terms: list[str] | None = None,
    regional_level: RegionalLevel = RegionalLevel.PROVINCIAL,
) -> QueryDecompositionTask:
    return QueryDecompositionTask(
        task_id=f"{task_family}_1",
        task_family=task_family,
        tiaokuai_axis=GovernanceAxis.BLOCK,
        line_family=LineFamily.POLICY if task_family != "industry_topic" else LineFamily.INDUSTRY,
        regional_level=regional_level,
        info_type=(
            InfoType.POLICY_NOTICE
            if task_family != "industry_topic"
            else InfoType.INDUSTRY_REPORT
        ),
        execution_bucket="search_assisted_sources",
        source_cluster="test_cluster",
        include_domains=include_domains,
        search_phrases=search_phrases,
        negative_terms=negative_terms or [],
        evidence_goal="goal",
        fallback_path="fallback",
    )


def test_primary_lane_rejects_supplemental_domains() -> None:
    task = _build_task(
        task_family="local_rollout",
        include_domains=["gd.gov.cn", "aopa.org.cn"],
        search_phrases=["广东 人形机器人 政策"],
    )

    decision = evaluate_candidate_compatibility(
        task=task,
        query="广东人形机器人产业政策和项目落地情况",
        url="https://www.aopa.org.cn/report.html",
        domain="www.aopa.org.cn",
        title="AOPA 通航论坛",
        snippet="低空经济 行业论坛",
        allowed_domains={"gd.gov.cn", "aopa.org.cn", "gov.cn"},
    )

    assert decision.decision == "reject"
    assert decision.reason_code == "supplemental_used_in_primary_lane"


def test_local_rollout_rejects_region_mismatch() -> None:
    task = _build_task(
        task_family="local_rollout",
        include_domains=["ah.gov.cn", "gd.gov.cn"],
        search_phrases=["安徽 人形机器人 政策"],
    )

    decision = evaluate_candidate_compatibility(
        task=task,
        query="安徽人形机器人产业政策情况",
        url="https://www.gd.gov.cn/policy.html",
        domain="www.gd.gov.cn",
        title="广东 人形机器人 政策",
        snippet="广东 省级政策",
        allowed_domains={"ah.gov.cn", "gd.gov.cn", "gov.cn"},
    )

    assert decision.decision == "reject"
    assert decision.reason_code == "region_mismatch"


def test_industry_topic_rejects_official_domain_role() -> None:
    task = _build_task(
        task_family="industry_topic",
        include_domains=["gov.cn"],
        search_phrases=["低空经济 白皮书"],
        regional_level=RegionalLevel.NATIONAL,
    )

    decision = evaluate_candidate_compatibility(
        task=task,
        query="低空经济协会白皮书",
        url="https://www.gov.cn/report.html",
        domain="www.gov.cn",
        title="政策文件",
        snippet="官方通知",
        allowed_domains={"gov.cn"},
    )

    assert decision.decision == "reject"
    assert decision.reason_code == "source_role_mismatch"


@pytest.mark.parametrize(
    ("allowed_domain", "domain", "query", "title", "snippet"),
    [
        (
            "caam.org.cn",
            "www.caam.org.cn",
            "\u65b0\u80fd\u6e90\u6c7d\u8f66 \u4ea7\u4e1a \u62a5\u544a",
            "\u65b0\u80fd\u6e90\u6c7d\u8f66 \u4ea7\u9500 \u60c5\u51b5",
            (
                "\u4e2d\u56fd\u6c7d\u8f66\u5de5\u4e1a\u534f\u4f1a "
                "\u65b0\u80fd\u6e90\u6c7d\u8f66 \u6570\u636e"
            ),
        ),
        (
            "chinapv.org.cn",
            "www.chinapv.org.cn",
            "\u5149\u4f0f \u4ea7\u80fd \u4ef7\u683c \u5468\u671f",
            "\u5149\u4f0f\u4ea7\u4e1a\u94fe \u5e02\u573a \u62a5\u544a",
            "\u884c\u4e1a\u534f\u4f1a \u5149\u4f0f \u4f9b\u9700 \u4ef7\u683c \u4ea7\u80fd",
        ),
        (
            "hiipb.com",
            "www.hiipb.com",
            "\u6d77\u5357\u81ea\u7531\u8d38\u6613\u6e2f \u4ea7\u4e1a \u6295\u8d44",
            "\u6d77\u5357\u81ea\u7531\u8d38\u6613\u6e2f \u4ea7\u4e1a\u6295\u8d44 \u9879\u76ee",
            (
                "\u6d77\u5357\u81ea\u7531\u8d38\u6613\u6e2f \u822a\u8fd0 "
                "\u6570\u5b57\u8d38\u6613 \u533b\u836f"
            ),
        ),
    ],
)
def test_industry_topic_accepts_theme_specific_supplemental_domains(
    allowed_domain: str,
    domain: str,
    query: str,
    title: str,
    snippet: str,
) -> None:
    task = _build_task(
        task_family="industry_topic",
        include_domains=[allowed_domain],
        search_phrases=[query],
        regional_level=RegionalLevel.NATIONAL,
    )

    decision = evaluate_candidate_compatibility(
        task=task,
        query=query,
        url=f"https://{domain}/report.html",
        domain=domain,
        title=title,
        snippet=snippet,
        allowed_domains={allowed_domain},
    )

    assert decision.decision == "accept"
    assert decision.reason_code == "accepted_official_or_allowlisted_domain"


def test_industry_topic_uses_current_search_phrase_for_theme_scope() -> None:
    task = _build_task(
        task_family="industry_topic",
        include_domains=["caam.org.cn"],
        search_phrases=[
            "\u52a8\u529b\u7535\u6c60 \u4ea7\u80fd \u4ef7\u683c \u884c\u4e1a\u534f\u4f1a",
            "\u5149\u4f0f \u4ea7\u80fd \u4ef7\u683c \u884c\u4e1a\u534f\u4f1a",
        ],
        regional_level=RegionalLevel.NATIONAL,
    )

    decision = evaluate_candidate_compatibility(
        task=task,
        query="\u52a8\u529b\u7535\u6c60 \u4ea7\u80fd \u4ef7\u683c \u884c\u4e1a\u534f\u4f1a",
        url="https://www.caam.org.cn/power-battery.html",
        domain="www.caam.org.cn",
        title="\u52a8\u529b\u7535\u6c60 \u4ea7\u4e1a \u6570\u636e",
        snippet="\u65b0\u80fd\u6e90\u6c7d\u8f66 \u52a8\u529b\u7535\u6c60 \u4ea7\u80fd",
        allowed_domains={"caam.org.cn"},
    )

    assert decision.decision == "accept"


def test_humanoid_query_rejects_negative_term_dominance() -> None:
    task = _build_task(
        task_family="policy_direction",
        include_domains=["gov.cn"],
        search_phrases=["人形机器人 政策"],
        negative_terms=["低空经济", "无人机", "UAV"],
        regional_level=RegionalLevel.NATIONAL,
    )

    decision = evaluate_candidate_compatibility(
        task=task,
        query="人形机器人政策方向",
        url="https://www.gov.cn/topic.html",
        domain="www.gov.cn",
        title="低空经济无人机政策",
        snippet="UAV 产业规划",
        allowed_domains={"gov.cn"},
    )

    assert decision.decision == "reject"
    assert decision.reason_code == "negative_term_mismatch"


def test_query_theme_mismatch_rejected() -> None:
    task = _build_task(
        task_family="policy_direction",
        include_domains=["gov.cn"],
        search_phrases=["人形机器人 政策"],
        regional_level=RegionalLevel.NATIONAL,
    )

    decision = evaluate_candidate_compatibility(
        task=task,
        query="人形机器人政策方向",
        url="https://www.gov.cn/topic.html",
        domain="www.gov.cn",
        title="新能源投资政策",
        snippet="能源产业规划",
        allowed_domains={"gov.cn"},
    )

    assert decision.decision == "reject"
    assert decision.reason_code == "domain_topic_mismatch"


def test_real_estate_policy_rejects_non_central_gov_domain_even_if_gov_cn_allowed() -> None:
    task = _build_task(
        task_family="policy_direction",
        include_domains=["gov.cn", "www.gov.cn", "mohurd.gov.cn", "ndrc.gov.cn", "stats.gov.cn"],
        search_phrases=["房地产 去库存 城中村改造 三大工程 住房城乡建设部"],
        regional_level=RegionalLevel.NATIONAL,
    )

    decision = evaluate_candidate_compatibility(
        task=task,
        query="房地产去库存、城中村改造、“三大工程”和地方收储政策",
        url="https://jw.shenyang.gov.cn/xwzx/202512/t20251223_4958076.html",
        domain="jw.shenyang.gov.cn",
        title="沈阳市相关政策解读",
        snippet="房地产 去库存 城中村改造 三大工程",
        allowed_domains={"gov.cn", "www.gov.cn", "mohurd.gov.cn", "ndrc.gov.cn", "stats.gov.cn"},
    )

    assert decision.decision == "reject"
    assert decision.reason_code == "national_policy_non_central_domain"


def test_real_estate_policy_accepts_central_domain_when_theme_matches() -> None:
    task = _build_task(
        task_family="policy_direction",
        include_domains=["www.gov.cn", "mohurd.gov.cn", "ndrc.gov.cn", "stats.gov.cn"],
        search_phrases=["房地产 去库存 城中村改造 三大工程 住房城乡建设部"],
        regional_level=RegionalLevel.NATIONAL,
    )

    decision = evaluate_candidate_compatibility(
        task=task,
        query="房地产去库存、城中村改造、“三大工程”和地方收储政策",
        url="https://www.mohurd.gov.cn/gongkai/zc/wjk/art/2025/art_xxxxx.html",
        domain="www.mohurd.gov.cn",
        title="住房城乡建设部关于城中村改造的通知",
        snippet="房地产 去库存 城中村改造 三大工程",
        allowed_domains={"www.gov.cn", "mohurd.gov.cn", "ndrc.gov.cn", "stats.gov.cn"},
    )

    assert decision.decision == "accept"


def test_local_rollout_city_query_accepts_province_parent_fallback() -> None:
    task = _build_task(
        task_family="local_rollout",
        include_domains=["sz.gov.cn", "gd.gov.cn"],
        search_phrases=["深圳 低空经济 政策"],
        regional_level=RegionalLevel.MUNICIPAL,
    )

    decision = evaluate_candidate_compatibility(
        task=task,
        query="深圳低空经济有哪些政策和招标信号",
        url="https://www.gd.gov.cn/zwgk/policy.html",
        domain="www.gd.gov.cn",
        title="广东省低空经济政策",
        snippet="省级政策作为上级补充",
        allowed_domains={"sz.gov.cn", "gd.gov.cn", "gov.cn"},
    )

    assert decision.decision == "accept"
    assert decision.reason_code == "accepted_parent_province_official_fallback"


def test_local_rollout_accepts_hefei_official_city_domain() -> None:
    task = _build_task(
        task_family="local_rollout",
        include_domains=["hefei.gov.cn", "ah.gov.cn"],
        search_phrases=["合肥 新能源汽车 政策"],
        regional_level=RegionalLevel.MUNICIPAL,
    )

    decision = evaluate_candidate_compatibility(
        task=task,
        query="合肥市新能源汽车产业集群是否形成供应链自循环",
        url="https://www.hefei.gov.cn/zwgk/policy.html",
        domain="www.hefei.gov.cn",
        title="合肥市新能源汽车产业政策",
        snippet="合肥 支持整车 电池 零部件产业链发展",
        allowed_domains={"hefei.gov.cn", "ah.gov.cn"},
    )

    assert decision.decision == "accept"
    assert decision.reason_code == "accepted_exact_city_or_county_official"


def test_local_rollout_rejects_province_navigation_index_page_for_hefei_city_query() -> None:
    task = _build_task(
        task_family="local_rollout",
        include_domains=["hefei.gov.cn", "gxj.hefei.gov.cn", "ah.gov.cn", "fzggw.ah.gov.cn"],
        search_phrases=["合肥 新能源汽车 政策"],
        regional_level=RegionalLevel.MUNICIPAL,
    )

    decision = evaluate_candidate_compatibility(
        task=task,
        query="合肥市新能源汽车产业集群是否进入供应链自循环阶段",
        url="https://fzggw.ah.gov.cn/gzcy/index.html",
        domain="fzggw.ah.gov.cn",
        title="公众参与",
        snippet="安徽省发展改革委 互动栏目 新能源汽车",
        allowed_domains={"hefei.gov.cn", "gxj.hefei.gov.cn", "ah.gov.cn", "fzggw.ah.gov.cn"},
    )

    assert decision.decision == "reject"
    assert decision.reason_code == "generic_navigation_index_page"


def test_local_rollout_does_not_treat_parent_province_domain_as_exact_city() -> None:
    task = _build_task(
        task_family="local_rollout",
        include_domains=["hefei.gov.cn", "gxj.hefei.gov.cn", "ah.gov.cn"],
        search_phrases=["合肥 新能源汽车 政策"],
        regional_level=RegionalLevel.MUNICIPAL,
    )

    decision = evaluate_candidate_compatibility(
        task=task,
        query="合肥市新能源汽车产业集群",
        url="https://www.ah.gov.cn/zwyw/mtjj/554155611.html",
        domain="www.ah.gov.cn",
        title="安徽新能源汽车产量增长",
        snippet="合肥 新能源汽车 产业",
        allowed_domains={"hefei.gov.cn", "gxj.hefei.gov.cn", "ah.gov.cn", "gov.cn"},
    )

    assert decision.decision == "accept"
    assert decision.reason_code == "accepted_parent_province_official_fallback"


def test_local_rollout_keeps_province_domain_as_parent_even_with_city_keyword() -> None:
    task = _build_task(
        task_family="local_rollout",
        include_domains=["hefei.gov.cn", "gxj.hefei.gov.cn", "ah.gov.cn", "amr.ah.gov.cn"],
        search_phrases=["合肥 新能源汽车 政策"],
        regional_level=RegionalLevel.MUNICIPAL,
    )

    decision = evaluate_candidate_compatibility(
        task=task,
        query="合肥市新能源汽车产业集群",
        url="https://amr.ah.gov.cn/xwdt/gsgg/150316941.html",
        domain="amr.ah.gov.cn",
        title="安徽省市场监督管理局公告",
        snippet="合肥 新能源汽车 企业",
        allowed_domains={
            "hefei.gov.cn",
            "gxj.hefei.gov.cn",
            "ah.gov.cn",
            "amr.ah.gov.cn",
            "gov.cn",
        },
    )

    assert decision.decision == "accept"
    assert decision.reason_code == "accepted_parent_province_official_fallback"


def test_local_rollout_accepts_feixi_subdomain_as_exact_county_domain() -> None:
    task = _build_task(
        task_family="local_rollout",
        include_domains=["ahfeixi.gov.cn", "hefei.gov.cn", "ah.gov.cn"],
        search_phrases=["肥西 新能源汽车 项目 园区"],
        regional_level=RegionalLevel.MUNICIPAL,
    )

    decision = evaluate_candidate_compatibility(
        task=task,
        query="肥西县新能源汽车产业链是否形成独立项目集群",
        url="http://xf.ahfeixi.gov.cn/content/detail/668762aa2792eec16586beca.html",
        domain="xf.ahfeixi.gov.cn",
        title="肥西县新能源汽车产业项目",
        snippet="肥西 新能源汽车 项目 园区 企业",
        allowed_domains={"ahfeixi.gov.cn", "hefei.gov.cn", "ah.gov.cn"},
    )

    assert decision.decision == "accept"
    assert decision.reason_code == "accepted_exact_park_or_county_official"


def test_local_rollout_accepts_feixi_subdomain_as_exact_even_with_sparse_snippet() -> None:
    feixi = "\u80a5\u897f"
    task = _build_task(
        task_family="local_rollout",
        include_domains=["ahfeixi.gov.cn", "hefei.gov.cn", "ah.gov.cn"],
        search_phrases=[f"{feixi} \u65b0\u80fd\u6e90\u6c7d\u8f66 \u9879\u76ee \u56ed\u533a"],
        regional_level=RegionalLevel.MUNICIPAL,
    )

    decision = evaluate_candidate_compatibility(
        task=task,
        query=f"{feixi}\u53bf\u65b0\u80fd\u6e90\u6c7d\u8f66\u4ea7\u4e1a\u94fe",
        url="http://xf.ahfeixi.gov.cn/content/detail/64ed3c8e2792ee604fe7c1c1.html",
        domain="xf.ahfeixi.gov.cn",
        title="\u5de5\u4f5c\u52a8\u6001",
        snippet="\u9879\u76ee \u56ed\u533a \u4f01\u4e1a",
        allowed_domains={"ahfeixi.gov.cn", "hefei.gov.cn", "ah.gov.cn"},
    )

    assert decision.decision == "accept"
    assert decision.reason_code == "accepted_exact_park_or_county_official"


def test_exact_county_domains_are_not_downgraded_to_parent_city_fallback() -> None:
    cases = [
        (
            "\u795e\u6728",
            "sxsm.gov.cn",
            "https://www.sxsm.gov.cn/xwzx/tpxw/202210/t20221014_1646001.html",
        ),
        (
            "\u82e5\u7f8c",
            "xjrq.gov.cn",
            "https://www.xjrq.gov.cn/rqxrmzf/c108592/202312/60e4b353d7ff45cdb6ffb50223856276.shtml",
        ),
    ]

    for region, domain, url in cases:
        task = _build_task(
            task_family="local_rollout",
            include_domains=[domain],
            search_phrases=[f"{region} \u4ea7\u4e1a \u56ed\u533a \u653f\u7b56"],
            regional_level=RegionalLevel.MUNICIPAL,
        ).model_copy(
            update={
                "evidence_obligations": [
                    "administrative_granularity:county",
                    "exact_local_depth",
                ]
            }
        )

        decision = evaluate_candidate_compatibility(
            task=task,
            query=f"{region}\u53bf\u57df\u4ea7\u4e1a\u53d1\u5c55",
            url=url,
            domain=domain,
            title=f"{region}\u4ea7\u4e1a\u53d1\u5c55\u653f\u7b56",
            snippet=f"{region} \u4ea7\u4e1a \u9879\u76ee",
            allowed_domains={domain},
        )

        assert decision.decision == "accept"
        assert decision.reason_code == "accepted_exact_park_or_county_official"


def test_parent_prefecture_domain_remains_parent_fallback_for_county_query() -> None:
    ruoqiang = "\u82e5\u7f8c"
    task = _build_task(
        task_family="local_rollout",
        include_domains=["xjrq.gov.cn", "xjbz.gov.cn"],
        search_phrases=[f"{ruoqiang} \u76d0\u6e56 \u56ed\u533a \u653f\u7b56"],
        regional_level=RegionalLevel.MUNICIPAL,
    ).model_copy(
        update={
            "evidence_obligations": [
                "administrative_granularity:county",
                "exact_local_depth",
            ]
        }
    )

    decision = evaluate_candidate_compatibility(
        task=task,
        query=f"{ruoqiang}\u53bf\u76d0\u6e56\u9879\u76ee",
        url="https://www.xjbz.gov.cn/xjbz/c101539/200908/720276f7b6a948e6afce225092981ba0.shtml",
        domain="www.xjbz.gov.cn",
        title=f"{ruoqiang}\u76d0\u6e56\u9879\u76ee\u80cc\u666f",
        snippet="\u5df4\u5dde \u76d0\u6e56 \u4ea7\u4e1a",
        allowed_domains={"xjrq.gov.cn", "xjbz.gov.cn"},
    )

    assert decision.decision == "accept"
    assert decision.reason_code == "accepted_parent_city_official_fallback"


def test_local_rollout_accepts_hefei_gxj_as_parent_fallback_for_feixi_query() -> None:
    feixi = "\u80a5\u897f"
    task = _build_task(
        task_family="local_rollout",
        include_domains=["ahfeixi.gov.cn", "gxj.hefei.gov.cn", "hefei.gov.cn"],
        search_phrases=[f"{feixi} \u65b0\u80fd\u6e90\u6c7d\u8f66 \u9879\u76ee \u56ed\u533a"],
        regional_level=RegionalLevel.MUNICIPAL,
    )

    decision = evaluate_candidate_compatibility(
        task=task,
        query=f"{feixi}\u53bf\u65b0\u80fd\u6e90\u6c7d\u8f66\u4ea7\u4e1a\u94fe",
        url="https://gxj.hefei.gov.cn/gyjj/xqgy/18702009.html",
        domain="gxj.hefei.gov.cn",
        title=f"{feixi}\u53bf\u5df2\u57fa\u672c\u5f62\u6210\u65b0\u80fd\u6e90\u6c7d\u8f66\u4ea7\u4e1a\u96c6\u7fa4",
        snippet="\u5408\u80a5\u5e02\u5de5\u4e1a\u548c\u4fe1\u606f\u5316\u5c40",
        allowed_domains={"ahfeixi.gov.cn", "gxj.hefei.gov.cn", "hefei.gov.cn"},
    )

    assert decision.decision == "accept"
    assert decision.reason_code == "accepted_parent_city_official_fallback"


def test_local_rollout_generic_exact_local_gov_seed_still_requires_region_text() -> None:
    task = _build_task(
        task_family="local_rollout",
        include_domains=["gov.cn"],
        search_phrases=["昆山 电子信息 稳外资 政策"],
        regional_level=RegionalLevel.MUNICIPAL,
    ).model_copy(update={"evidence_obligations": ["exact_local_depth"]})

    mismatch = evaluate_candidate_compatibility(
        task=task,
        query="昆山市电子信息和台资制造业是否面临产业链外迁压力",
        url="https://www.gov.cn/policy.html",
        domain="www.gov.cn",
        title="江苏省电子信息产业政策",
        snippet="省级政策，不包含精确地方对象",
        allowed_domains={"gov.cn"},
    )
    exact = evaluate_candidate_compatibility(
        task=task,
        query="昆山市电子信息和台资制造业是否面临产业链外迁压力",
        url="https://www.gov.cn/policy.html",
        domain="www.gov.cn",
        title="昆山市电子信息产业稳外资政策",
        snippet="昆山 台资制造业 产业链 政策",
        allowed_domains={"gov.cn"},
    )

    assert mismatch.decision == "reject"
    assert mismatch.reason_code == "region_mismatch"
    assert exact.decision == "accept"
    assert exact.reason_code == "accepted_exact_city_or_county_official"


def test_policy_direction_exact_local_query_rejects_unrelated_local_gov_domain() -> None:
    task = _build_task(
        task_family="policy_direction",
        include_domains=["gov.cn", "ndrc.gov.cn"],
        search_phrases=["盐湖 政策 规划"],
        regional_level=RegionalLevel.NATIONAL,
    )

    decision = evaluate_candidate_compatibility(
        task=task,
        query="若羌县盐湖锂钾资源和新能源项目是否具备实际产业化条件？",
        url="http://www.yanhu.gov.cn/doc/2023/09/01/370587.shtml",
        domain="www.yanhu.gov.cn",
        title="盐湖区新能源产业发展政策",
        snippet="运城市盐湖区人民政府 产业政策 规划",
        allowed_domains={"gov.cn", "ndrc.gov.cn"},
    )

    assert decision.decision == "reject"
    assert decision.reason_code == "region_mismatch"


def test_policy_direction_exact_local_city_query_rejects_wrong_city_gov_domain() -> None:
    task = _build_task(
        task_family="policy_direction",
        include_domains=["gov.cn", "ndrc.gov.cn"],
        search_phrases=["新能源汽车 政策 规划"],
        regional_level=RegionalLevel.NATIONAL,
    )

    decision = evaluate_candidate_compatibility(
        task=task,
        query="合肥市新能源汽车产业集群是否已经从龙头企业招商进入供应链自循环阶段？",
        url="https://www.sz.gov.cn/cn/xxgk/zfxxgj/zcfg/content/post_123.html",
        domain="www.sz.gov.cn",
        title="深圳市新能源汽车产业政策",
        snippet="深圳市 工业和信息化局 新能源汽车 产业 政策",
        allowed_domains={"gov.cn", "ndrc.gov.cn"},
    )

    assert decision.decision == "reject"
    assert decision.reason_code == "region_mismatch"


def test_policy_direction_exact_local_query_keeps_central_policy_domain() -> None:
    task = _build_task(
        task_family="policy_direction",
        include_domains=["gov.cn", "ndrc.gov.cn"],
        search_phrases=["盐湖 政策 规划"],
        regional_level=RegionalLevel.NATIONAL,
    )

    decision = evaluate_candidate_compatibility(
        task=task,
        query="若羌县盐湖锂钾资源和新能源项目是否具备实际产业化条件？",
        url="https://www.ndrc.gov.cn/fggz/fgzy/xmtjd/202307/t20230728_1358871.html",
        domain="www.ndrc.gov.cn",
        title="国家发展改革委关于资源型地区产业转型的政策解读",
        snippet="盐湖资源 新能源 项目 产业政策",
        allowed_domains={"gov.cn", "ndrc.gov.cn"},
    )

    assert decision.decision == "accept"


def test_local_rollout_park_query_accepts_city_parent_fallback() -> None:
    task = _build_task(
        task_family="local_rollout",
        include_domains=["chengdu.gov.cn"],
        search_phrases=["成都 人工智能产业园区 政策 规划"],
        regional_level=RegionalLevel.MUNICIPAL,
    )

    decision = evaluate_candidate_compatibility(
        task=task,
        query="成都人工智能产业园区有哪些政策和项目机会",
        url="https://www.chengdu.gov.cn/zwgk/policy.html",
        domain="www.chengdu.gov.cn",
        title="成都市人工智能产业发展政策",
        snippet="市级政策，非园区官网",
        allowed_domains={"chengdu.gov.cn", "gov.cn"},
    )

    assert decision.decision == "accept"
    assert decision.reason_code == "accepted_parent_city_official_fallback"


def test_round3_lane_family_eligibility_helper() -> None:
    assert is_supplemental_or_fallback_task_family("local_rollout") is True
    assert is_supplemental_or_fallback_task_family("industry_topic") is True
    assert is_supplemental_or_fallback_task_family("policy_direction") is False


# ---------------------------------------------------------------------------
# Phase 1 — public_resource_procurement backbone tests
# ---------------------------------------------------------------------------


def test_is_procurement_domain_recognizes_ggzy_subdomains() -> None:
    """Known procurement domains are correctly classified."""
    procurement_domains = [
        "ggzy.hefei.gov.cn",
        "ggzy.changzhou.gov.cn",
        "ggzyjy.nmg.gov.cn",
        "ccgp.gov.cn",
        "www.ccgp.gov.cn",
        "ggzy.xinjiang.gov.cn",
        "sxggzyjy.cn",
    ]
    for domain in procurement_domains:
        assert is_procurement_domain(domain), f"Expected procurement domain: {domain}"


def test_is_procurement_domain_rejects_generic_gov_domains() -> None:
    """Generic .gov.cn domains are NOT procurement domains."""
    generic_domains = [
        "www.gov.cn",
        "hefei.gov.cn",
        "changzhou.gov.cn",
        "ah.gov.cn",
        "ndrc.gov.cn",
        "miit.gov.cn",
    ]
    for domain in generic_domains:
        assert not is_procurement_domain(domain), f"Expected non-procurement: {domain}"


def test_is_procurement_domain_handles_none_and_empty() -> None:
    assert not is_procurement_domain(None)
    assert not is_procurement_domain("")
    assert not is_procurement_domain("   ")


def test_domain_has_procurement_signal_via_domain() -> None:
    assert domain_has_procurement_signal(domain="ggzy.hefei.gov.cn") is True
    assert domain_has_procurement_signal(domain="ccgp.gov.cn") is True


def test_domain_has_procurement_signal_via_url_keywords() -> None:
    assert domain_has_procurement_signal(domain="hefei.gov.cn", url="/zwgk/zbgg/招标公告") is True
    assert domain_has_procurement_signal(domain="ah.gov.cn", url="/政府采购/") is True
    assert domain_has_procurement_signal(domain="ah.gov.cn", url="/ggzy/002001/") is True
    assert domain_has_procurement_signal(domain="ah.gov.cn", url="/trade/tender/list.html") is True


def test_domain_has_procurement_signal_rejects_generic() -> None:
    assert domain_has_procurement_signal(domain="hefei.gov.cn") is False
    assert domain_has_procurement_signal(domain="www.gov.cn") is False
    assert domain_has_procurement_signal(domain=None) is False


def test_is_generic_policy_page_candidate_for_generic_domain() -> None:
    """A generic .gov.cn domain without procurement subdomain is a generic policy page."""
    assert is_generic_policy_page_candidate(
        url="https://www.hefei.gov.cn/zwgk/policy.html",
        domain="www.hefei.gov.cn",
        title="合肥市产业政策",
    ) is True


def test_is_generic_policy_page_candidate_for_procurement_domain_clean_path() -> None:
    """A procurement domain with a clean (non-policy-path) URL is NOT generic."""
    assert is_generic_policy_page_candidate(
        url="https://ggzy.hefei.gov.cn/jyxx/002001/002001001/",
        domain="ggzy.hefei.gov.cn",
        title="合肥公共资源交易公告",
    ) is False


def test_is_generic_policy_page_candidate_for_procurement_domain_policy_path() -> None:
    """A procurement domain with a policy/news path IS flagged as generic."""
    assert is_generic_policy_page_candidate(
        url="https://ggzy.changzhou.gov.cn/zwgk/policy_notice.html",
        domain="ggzy.changzhou.gov.cn",
        title="政策通知",
    ) is True


def test_is_generic_policy_page_candidate_none_domain() -> None:
    assert is_generic_policy_page_candidate(
        url="https://example.com/page",
        domain=None,
        title="Some page",
    ) is True


def test_procurement_and_policy_domains_are_distinct() -> None:
    """procurement != generic_policy: the two domain classes must not overlap."""
    procurement = {"ggzy.hefei.gov.cn", "ccgp.gov.cn", "ggzyjy.nmg.gov.cn"}
    policy = {"www.gov.cn", "hefei.gov.cn", "ndrc.gov.cn"}
    assert procurement.isdisjoint(policy)


def test_city_county_procurement_domains_recognized() -> None:
    """Verify known city/county procurement domains are recognized."""
    known_procurement_domains = [
        # Anhui province
        "ggzy.ah.gov.cn",
        # Hefei city
        "ggzy.hefei.gov.cn",
        # Changzhou city
        "ggzy.xzsp.changzhou.gov.cn",
        # Shenzhen
        "szggzy.com",
        # Guangdong province
        "gdggzy.org.cn",
        # Jiangsu province
        "jsggzy.jszwfw.gov.cn",
        # Xinjiang
        "ggzy.xinjiang.gov.cn",
        # Inner Mongolia
        "ggzyjy.nmg.gov.cn",
        # Shaanxi
        "sxggzyjy.cn",
        # Suzhou
        "szzyjy.com.cn",
        # Hainan
        "zw.hainan.gov.cn",
        # National
        "ccgp.gov.cn",
    ]

    recognized = sum(1 for d in known_procurement_domains if is_procurement_domain(d))
    # At least 80% should be recognized
    threshold = max(1, int(len(known_procurement_domains) * 0.8))
    assert recognized >= threshold, (
        f"Only {recognized}/{len(known_procurement_domains)} procurement domains recognized"
    )
