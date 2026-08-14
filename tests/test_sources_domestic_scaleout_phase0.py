from __future__ import annotations

from packages.sources.domestic_inventory import (
    list_executable_source_keys,
    list_first_wave_sample_sources,
    list_frozen_template_families,
    list_inventory_report_codes,
    list_pack_state_rows,
    list_report_codes,
    list_template_mapping_rows,
)


def test_domestic_inventory_covers_all_report_codes() -> None:
    expected = set(list_report_codes())
    observed = set(list_inventory_report_codes())
    assert observed == expected


def test_template_mapping_and_frozen_template_families() -> None:
    mappings = list_template_mapping_rows()
    assert len(mappings) >= 10

    frozen = list_frozen_template_families()
    assert frozen == ["policy_library_template", "disclosure_template"]

    mapping_templates = {item.template_family for item in mappings}
    assert set(frozen).issubset(mapping_templates)


def test_pack_state_table_is_classified() -> None:
    rows = list_pack_state_rows()
    by_pack = {item["pack_id"]: item for item in rows}

    assert by_pack["policy_pack_cn"]["state"] == "executable"
    assert by_pack["disclosure_pack_cn"]["state"] == "executable"
    assert by_pack["industry_signal_pack_cn"]["state"] == "placeholder"
    assert by_pack["policy_pack_cn_v2"]["state"] == "executable"
    assert by_pack["disclosure_pack_cn_v2"]["state"] == "executable"
    assert by_pack["project_signal_pack_cn_v1"]["state"] == "executable"
    assert by_pack["city_park_pack_cn_v1"]["state"] == "executable"
    assert by_pack["industry_signal_pack_cn_v2"]["state"] == "executable"
    assert by_pack["phase1_sample_pack_cn"]["source_count"] >= 10
    assert by_pack["local_rollout_pack_cn_v2"]["state"] == "executable"


def test_first_wave_sample_shortlist_is_ready() -> None:
    samples = list_first_wave_sample_sources()
    source_ids = {item.source_id for item in samples}

    assert len(samples) >= 10
    assert "cn_policy_state_council_zcwj_v1" in source_ids
    assert "cn_policy_ndrc_tzgg_v1" in source_ids
    assert "cn_exchange_szse_notice_v1" in source_ids
    assert "cn_exchange_cninfo_announcement_v1" in source_ids


def test_phase2_has_at_least_12_executable_sources() -> None:
    executable_source_keys = list_executable_source_keys()
    assert len(executable_source_keys) >= 12
    assert "cn_project_ccgp_procurement_v1" in executable_source_keys
    assert "cn_project_ggzy_trade_v1" in executable_source_keys
    assert "cn_project_ndrc_approval_v1" in executable_source_keys
