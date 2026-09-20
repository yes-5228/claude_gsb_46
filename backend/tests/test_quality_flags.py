"""数据质量标记接口与统计剔除规则测试."""
from app.extensions import db
from app.models import Exceedance, Measurement, QualityFlagLog


def _create_reading(client, station, entry_payload, pollutant="SO2", value=900.0):
    client.post(
        "/api/measurements/entries",
        json=entry_payload(
            station.id,
            entries=[{"pollutant": pollutant, "value": value}],
        ),
    )
    return Measurement.query.filter_by(pollutant=pollutant).one()


def test_mark_outlier_keeps_audit_fields(client, station, entry_payload):
    reading = _create_reading(client, station, entry_payload)
    response = client.patch(
        "/api/measurements/%s/quality" % reading.id,
        json={"flag": "outlier", "reason": "相邻时段偏差过大", "marked_by": "王敏"},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["quality_flag"] == "outlier"
    assert body["quality_flag_label"] == "离群值"
    assert body["quality_reason"] == "相邻时段偏差过大"
    assert body["quality_marked_by"] == "王敏"
    assert body["quality_marked_at"] is not None
    assert body["is_quality_invalid"] is True
    assert QualityFlagLog.query.filter_by(measurement_id=reading.id, action="mark").count() == 1


def test_mark_requires_reason(client, station, entry_payload):
    reading = _create_reading(client, station, entry_payload)
    response = client.patch(
        "/api/measurements/%s/quality" % reading.id,
        json={"flag": "outlier", "reason": "  ", "marked_by": "王敏"},
    )
    assert response.status_code == 422
    assert "reason" in response.get_json()["error"]["fields"]


def test_marked_invalid_reading_excluded_from_compliance_stats(client, station, second_station,
                                                              entry_payload):
    # 站点 A: 1 条超标 + 1 条达标, 超标读数标记为仪器异常 (无效)
    client.post(
        "/api/measurements/entries",
        json=entry_payload(station.id, measured_at="2026-09-01 10:00",
                           entries=[{"pollutant": "SO2", "value": 900.0}]),
    )
    client.post(
        "/api/measurements/entries",
        json=entry_payload(station.id, measured_at="2026-09-01 11:00",
                           entries=[{"pollutant": "SO2", "value": 100.0}]),
    )
    exceeded = Measurement.query.filter_by(is_exceeded=True, station_id=station.id).one()
    client.patch(
        "/api/measurements/%s/quality" % exceeded.id,
        json={"flag": "instrument", "reason": "设备故障", "marked_by": "李静"},
    )
    # 站点 B: 1 条超标 (有效)
    client.post(
        "/api/measurements/entries",
        json=entry_payload(second_station.id, measured_at="2026-09-01 10:00",
                           entries=[{"pollutant": "SO2", "value": 800.0}]),
    )

    summary = client.get("/api/query/measurements?station_id=%s" % station.id).get_json()["summary"]
    # 有效口径: 只剩 1 条达标读数
    assert summary["total"] == 1
    assert summary["exceeded_count"] == 0
    assert summary["compliance_rate"] == 1.0
    assert summary["invalid_excluded"] is True
    assert summary["quality"]["invalid_count"] == 1

    # 全部口径: include_invalid=true 恢复 2 条
    raw = client.get(
        "/api/query/measurements?station_id=%s&include_invalid=true" % station.id
    ).get_json()["summary"]
    assert raw["total"] == 2
    assert raw["exceeded_count"] == 1
    assert raw["compliance_rate"] == 0.5

    # 明细仍可查到被标记的数据
    listed = client.get(
        "/api/query/measurements?station_id=%s&quality_state=invalid" % station.id
    ).get_json()
    assert listed["total"] == 1
    assert listed["items"][0]["quality_flag"] == "instrument"

    # 站点排名: A 达标率 100% 排第 1, B 达标率 0 排第 2
    stats = client.get(
        "/api/query/statistics?group_by=station&metric=count"
    ).get_json()
    ranks = {item["key"]: item for item in stats["items"]}
    station_a = [item for item in stats["items"] if item["label"].startswith("TEST-001")][0]
    station_b = [item for item in stats["items"] if item["label"].startswith("TEST-002")][0]
    assert station_a["rank"] == 1
    assert station_a["count"] == 1
    assert station_b["rank"] == 2
    assert station_b["exceeded_count"] == 1


def test_invalid_exceedance_hidden_from_workbench_by_default(client, station, entry_payload):
    reading = _create_reading(client, station, entry_payload)
    assert Exceedance.query.count() == 1
    client.patch(
        "/api/measurements/%s/quality" % reading.id,
        json={"flag": "instrument", "reason": "设备故障", "marked_by": "李静"},
    )
    assert client.get("/api/exceedances").get_json()["total"] == 0
    # 显式包含无效数据时仍可在明细查到
    assert client.get("/api/exceedances?include_invalid=true").get_json()["total"] == 1
    assert client.get("/api/exceedances/summary").get_json()["total"] == 0
    assert client.get("/api/exceedances/summary?include_invalid=true").get_json()["total"] == 1


def test_corrected_reading_keeps_original_and_re_evaluates(client, station, entry_payload):
    reading = _create_reading(client, station, entry_payload, value=900.0)
    assert reading.is_exceeded is True
    response = client.patch(
        "/api/measurements/%s/quality" % reading.id,
        json={"flag": "corrected", "reason": "按人工比对值修正", "marked_by": "赵宇",
              "corrected_value": 120.0},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["original_value"] == 900.0
    assert body["value"] == 120.0
    assert body["is_quality_invalid"] is False
    # 修正后不再超标, 超标单被撤销
    assert db.session.get(Measurement, reading.id).is_exceeded is False
    assert Exceedance.query.count() == 0

    # 人工修正属于有效数据, 仍计入达标率
    summary = client.get("/api/query/measurements").get_json()["summary"]
    assert summary["total"] == 1
    assert summary["compliance_rate"] == 1.0
    assert summary["quality"]["corrected_count"] == 1


def test_correction_requires_value(client, station, entry_payload):
    reading = _create_reading(client, station, entry_payload)
    response = client.patch(
        "/api/measurements/%s/quality" % reading.id,
        json={"flag": "corrected", "reason": "修正", "marked_by": "赵宇"},
    )
    assert response.status_code == 422
    assert response.get_json()["error"]["fields"]["corrected_value"] == "required"


def test_unmark_correction_restores_original(client, station, entry_payload):
    reading = _create_reading(client, station, entry_payload, value=900.0)
    client.patch(
        "/api/measurements/%s/quality" % reading.id,
        json={"flag": "corrected", "reason": "修正", "marked_by": "赵宇",
              "corrected_value": 120.0},
    )
    assert Exceedance.query.count() == 0
    response = client.delete(
        "/api/measurements/%s/quality" % reading.id,
        json={"reason": "修正依据不足, 恢复原值", "marked_by": "赵宇"},
    )
    assert response.status_code == 200
    restored = db.session.get(Measurement, reading.id)
    assert restored.value == 900.0
    assert restored.original_value is None
    assert restored.quality_flag is None
    assert restored.is_exceeded is True
    # 超标单随原值恢复
    assert Exceedance.query.count() == 1


def test_unmark_clears_flag_but_keeps_log(client, station, entry_payload):
    reading = _create_reading(client, station, entry_payload)
    client.patch(
        "/api/measurements/%s/quality" % reading.id,
        json={"flag": "outlier", "reason": "离群", "marked_by": "王敏"},
    )
    response = client.delete(
        "/api/measurements/%s/quality" % reading.id,
        json={"reason": "复测正常", "marked_by": "王敏"},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["quality_flag"] is None
    assert body["is_quality_invalid"] is False
    logs = QualityFlagLog.query.filter_by(measurement_id=reading.id).all()
    assert [log.action for log in logs] == ["mark", "unmark"]


def test_overwrite_entry_auto_clears_quality_flag(client, station, entry_payload):
    reading = _create_reading(client, station, entry_payload)
    client.patch(
        "/api/measurements/%s/quality" % reading.id,
        json={"flag": "outlier", "reason": "离群", "marked_by": "王敏"},
    )
    response = client.post(
        "/api/measurements/entries",
        json=entry_payload(station.id, overwrite=True,
                           entries=[{"pollutant": "SO2", "value": 200.0}]),
    )
    assert response.status_code == 201
    updated = db.session.get(Measurement, reading.id)
    assert updated.quality_flag is None
    actions = [log.action for log in QualityFlagLog.query.filter_by(measurement_id=reading.id)]
    assert actions == ["mark", "unmark"]


def test_quality_logs_endpoint_lists_history(client, station, entry_payload):
    reading = _create_reading(client, station, entry_payload)
    client.patch(
        "/api/measurements/%s/quality" % reading.id,
        json={"flag": "outlier", "reason": "离群", "marked_by": "王敏"},
    )
    response = client.get("/api/measurements/quality-logs")
    assert response.status_code == 200
    body = response.get_json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["flag"] == "outlier"
    assert item["measurement"]["pollutant"] == "SO2"

    filtered = client.get("/api/measurements/quality-logs?flag=instrument")
    assert filtered.get_json()["total"] == 0


def test_quality_filter_by_flag(client, station, entry_payload):
    reading = _create_reading(client, station, entry_payload)
    client.patch(
        "/api/measurements/%s/quality" % reading.id,
        json={"flag": "outlier", "reason": "离群", "marked_by": "王敏"},
    )
    response = client.get("/api/measurements?quality_flag=outlier")
    body = response.get_json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == reading.id
