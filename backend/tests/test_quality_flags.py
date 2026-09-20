"""数据质量标记接口与业务规则测试."""


def _create_reading(client, station, entry_payload, value=900.0):
    response = client.post(
        "/api/measurements/entries",
        json=entry_payload(
            station.id,
            measured_at="2026-09-01 10:00",
            period="daily",
            entries=[{"pollutant": "SO2", "value": value}],
        ),
    )
    return response.get_json()["created"][0]["id"]


def test_flag_outlier_marks_invalid_and_keeps_detail(client, station, entry_payload):
    measurement_id = _create_reading(client, station, entry_payload)

    response = client.post(
        "/api/measurements/%d/flag" % measurement_id,
        json={
            "quality_flag": "outlier",
            "reason": "相邻时段浓度突变, 判定为离群值",
            "marked_by": "王敏",
        },
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    body = response.get_json()
    assert body["quality_flag"] == "outlier"
    assert body["quality_flag_label"] == "离群值"
    assert body["quality_marked_by"] == "王敏"
    assert body["quality_marked_at"] is not None
    assert body["is_invalid"] is True

    # 明细列表里仍能查到被标记的数据
    rows = client.get("/api/query/measurements").get_json()
    assert rows["total"] == 1
    assert rows["items"][0]["quality_flag"] == "outlier"
    # 但不进入达标率有效口径
    assert rows["summary"]["valid_total"] == 0
    assert rows["summary"]["invalid_count"] == 1


def test_flag_requires_reason(client, station, entry_payload):
    measurement_id = _create_reading(client, station, entry_payload)
    response = client.post(
        "/api/measurements/%d/flag" % measurement_id,
        json={"quality_flag": "instrument"},
    )
    assert response.status_code == 422
    assert "reason" in response.get_json()["error"]["fields"]


def test_unknown_flag_rejected(client, station, entry_payload):
    measurement_id = _create_reading(client, station, entry_payload)
    response = client.post(
        "/api/measurements/%d/flag" % measurement_id,
        json={"quality_flag": "bogus", "reason": "x"},
    )
    assert response.status_code == 422


def test_instrument_flag_excluded_from_statistics(client, station, second_station, entry_payload):
    first_id = _create_reading(client, station, entry_payload, value=900.0)
    _create_reading(client, second_station, entry_payload, value=100.0)

    client.post(
        "/api/measurements/%d/flag" % first_id,
        json={"quality_flag": "instrument", "reason": "分析仪故障"},
    )

    stats = client.get(
        "/api/query/statistics?group_by=station&metric=count"
    ).get_json()
    counts = {item["key"]: item["count"] for item in stats["items"]}
    # 被标记的监测点有效数据为 0, 不参与分组统计; 另一个监测点保留
    assert "TEST-001" not in counts
    assert counts["TEST-002"] == 1

    summary = client.get("/api/query/measurements").get_json()["summary"]
    assert summary["total"] == 2
    assert summary["valid_total"] == 1
    assert summary["invalid_count"] == 1
    assert summary["exceeded_count"] == 0
    assert summary["compliance_rate"] == 1.0


def test_corrected_flag_needs_value_and_re_evaluates(client, station, entry_payload):
    measurement_id = _create_reading(client, station, entry_payload, value=900.0)

    missing = client.post(
        "/api/measurements/%d/flag" % measurement_id,
        json={"quality_flag": "corrected", "reason": "单位错误"},
    )
    assert missing.status_code == 422
    assert "corrected_value" in missing.get_json()["error"]["fields"]

    response = client.post(
        "/api/measurements/%d/flag" % measurement_id,
        json={
            "quality_flag": "corrected",
            "reason": "单位换算错误, 人工订正",
            "marked_by": "陈志强",
            "corrected_value": 100.0,
        },
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["value"] == 100.0
    assert body["original_value"] == 900.0
    assert body["is_exceeded"] is False
    assert body["is_invalid"] is False  # 人工修正后仍是有效数据

    # 原超标记录因修正后达标而撤销
    rows = client.get("/api/query/measurements").get_json()
    assert rows["summary"]["valid_total"] == 1
    assert rows["summary"]["exceeded_count"] == 0


def test_clear_flag_keeps_audit_trail(client, station, entry_payload):
    measurement_id = _create_reading(client, station, entry_payload, value=900.0)
    client.post(
        "/api/measurements/%d/flag" % measurement_id,
        json={"quality_flag": "outlier", "reason": "离群", "marked_by": "王敏"},
    )

    without_reason = client.post(
        "/api/measurements/%d/clear-flag" % measurement_id, json={}
    )
    assert without_reason.status_code == 422

    cleared = client.post(
        "/api/measurements/%d/clear-flag" % measurement_id,
        json={"reason": "复测确认数据有效", "marked_by": "赵宇"},
    )
    assert cleared.status_code == 200
    assert cleared.get_json()["quality_flag"] is None

    history = client.get(
        "/api/measurements/%d/flags" % measurement_id
    ).get_json()
    actions = [(item["action"], item["quality_flag"]) for item in history["items"]]
    assert ("clear", "outlier") in actions
    assert ("flag", "outlier") in actions
    reasons = {item["reason"] for item in history["items"]}
    assert "离群" in reasons
    assert "复测确认数据有效" in reasons


def test_flag_logs_list_and_filters(client, station, entry_payload):
    measurement_id = _create_reading(client, station, entry_payload, value=900.0)
    client.post(
        "/api/measurements/%d/flag" % measurement_id,
        json={"quality_flag": "outlier", "reason": "离群", "marked_by": "王敏"},
    )

    logs = client.get("/api/measurements/flag-logs").get_json()
    assert logs["total"] == 1
    assert logs["items"][0]["quality_flag"] == "outlier"
    assert logs["items"][0]["marked_by"] == "王敏"
    assert logs["items"][0]["station_name"] == "测试监测点"

    filtered = client.get(
        "/api/measurements/flag-logs?quality_flag=instrument"
    ).get_json()
    assert filtered["total"] == 0

    by_marker = client.get(
        "/api/measurements/flag-logs?marked_by=王敏"
    ).get_json()
    assert by_marker["total"] == 1


def test_overwrite_clears_flag_with_trail(client, station, entry_payload):
    measurement_id = _create_reading(client, station, entry_payload, value=900.0)
    client.post(
        "/api/measurements/%d/flag" % measurement_id,
        json={"quality_flag": "outlier", "reason": "离群"},
    )

    response = client.post(
        "/api/measurements/entries",
        json=entry_payload(
            station.id,
            measured_at="2026-09-01 10:00",
            period="daily",
            entries=[{"pollutant": "SO2", "value": 120.0}],
            overwrite=True,
        ),
    )
    assert response.status_code == 201
    updated = response.get_json()["updated"][0]
    assert updated["quality_flag"] is None

    history = client.get(
        "/api/measurements/%d/flags" % measurement_id
    ).get_json()
    assert any(item["action"] == "clear" for item in history["items"])


def test_compliance_ranking_excludes_invalid(client, station, second_station, entry_payload):
    bad_id = _create_reading(client, station, entry_payload, value=900.0)
    _create_reading(client, second_station, entry_payload, value=100.0)
    client.post(
        "/api/measurements/%d/flag" % bad_id,
        json={"quality_flag": "outlier", "reason": "离群"},
    )

    overview = client.get("/api/meta/overview").get_json()
    ranking = overview["compliance_ranking"]
    codes = {item["station_code"] for item in ranking}
    # 仅有的数据被标无效的监测点不进入排名
    assert "TEST-001" not in codes
    assert "TEST-002" in codes
    top = next(item for item in ranking if item["station_code"] == "TEST-002")
    assert top["rank"] == 1
    assert top["compliance_rate"] == 1.0

    assert overview["measurements"]["invalid_count"] == 1


def test_filter_by_quality_flag_and_invalid(client, station, entry_payload):
    outlier_id = _create_reading(client, station, entry_payload, value=900.0)
    _create_reading(
        client,
        station,
        lambda sid, **kw: entry_payload(
            sid, measured_at="2026-09-02 10:00",
            period="daily", entries=[{"pollutant": "SO2", "value": 100.0}],
        ),
    )
    client.post(
        "/api/measurements/%d/flag" % outlier_id,
        json={"quality_flag": "instrument", "reason": "故障"},
    )

    flagged = client.get(
        "/api/query/measurements?quality_flag=instrument"
    ).get_json()
    assert flagged["total"] == 1

    invalid = client.get("/api/query/measurements?is_invalid=true").get_json()
    assert invalid["total"] == 1

    valid = client.get("/api/query/measurements?is_invalid=false").get_json()
    assert valid["total"] == 1
    assert valid["items"][0]["value"] == 100.0
