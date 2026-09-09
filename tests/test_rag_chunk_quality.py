from packages.rag.chunk_quality import score_chunk_quality


def test_high_quality_official_policy_chunk():
    score = score_chunk_quality(
        text="广东省人民政府关于印发《广东省推动人工智能与机器人产业创新发展若干政策措施》的通知。"
             "明确提出支持人形机器人产业发展，提出成立产业联盟等举措。2025年3月发布。",
        source_family="official_policy",
        source_tier="A",
    )
    assert score.composite >= 0.6
    assert score.authority >= 0.7


def test_low_quality_noise_chunk():
    score = score_chunk_quality(
        text="下载app 直播 攻略 游戏",
        source_family="unknown",
        source_tier="D",
    )
    assert score.composite < 0.3


def test_policy_document_with_numbers():
    score = score_chunk_quality(
        text="粤府办〔2025〕12号文件指出，2025年全省机器人产业产值目标500亿元。",
        source_family="official_policy",
        source_tier="A",
    )
    assert score.citability >= 0.4
