from packages.sources.profiles.china_exchange import (
    build_cn_exchange_announcement_generic_profile,
    build_cn_exchange_szse_notice_v1_profile,
)
from packages.sources.profiles.china_industry import (
    build_cn_industry_association_generic_profile,
)
from packages.sources.profiles.china_policy import (
    build_cn_policy_generic_profile,
    build_cn_policy_ndrc_tzgg_v1_profile,
)


def build_domestic_source_profiles():
    return [
        build_cn_policy_generic_profile(),
        build_cn_policy_ndrc_tzgg_v1_profile(),
        build_cn_exchange_announcement_generic_profile(),
        build_cn_exchange_szse_notice_v1_profile(),
        build_cn_industry_association_generic_profile(),
    ]


__all__ = [
    "build_cn_exchange_announcement_generic_profile",
    "build_cn_exchange_szse_notice_v1_profile",
    "build_cn_industry_association_generic_profile",
    "build_cn_policy_generic_profile",
    "build_cn_policy_ndrc_tzgg_v1_profile",
    "build_domestic_source_profiles",
]
