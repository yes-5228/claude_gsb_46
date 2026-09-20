"""数据质量标记: 离群值 / 仪器异常 / 人工修正, 全程留痕."""
from datetime import datetime

from sqlalchemy import or_

from ..domain import exceedance_rules
from ..domain.constants import QUALITY_FLAG_LABELS
from ..domain.standards import get_pollutant
from ..errors import NotFoundError, ValidationError
from ..extensions import db
from ..models import Measurement, QualityFlagLog, Station

FLAG_CHOICES = tuple(QUALITY_FLAG_LABELS.keys())


def get_measurement(measurement_id):
    measurement = db.session.get(Measurement, measurement_id)
    if measurement is None:
        raise NotFoundError("监测数据不存在: id=%s" % measurement_id)
    return measurement


def _write_log(measurement, action, reason, marked_by, value_before, value_after, flag=None):
    log = QualityFlagLog(
        measurement_id=measurement.id,
        action=action,
        quality_flag=flag if flag is not None else measurement.quality_flag,
        reason=reason,
        marked_by=marked_by,
        marked_at=datetime.now(),
        value_before=value_before,
        value_after=value_after,
    )
    db.session.add(log)
    return log


def flag_measurement(measurement, flag, reason, marked_by=None, corrected_value=None):
    """把一条读数标记为离群值 / 仪器异常 / 人工修正.

    - 标记原因必填, 标记人默认 "未署名", 标记时间自动记录;
    - 人工修正必须给出修正后的监测值, 并按限值重新判定超标;
    - 离群值 / 仪器异常不改变读数, 但读数被视为无效, 不参与达标率与排名.
    """
    if flag not in FLAG_CHOICES:
        raise ValidationError(
            "质量标记取值不合法, 可选: %s" % ", ".join(FLAG_CHOICES),
            fields={"quality_flag": "unknown"},
        )
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("标记原因不能为空", fields={"reason": "required"})
    marked_by = (marked_by or "").strip() or "未署名"

    value_before = measurement.value
    value_after = value_before

    if flag == "corrected":
        if corrected_value is None or str(corrected_value).strip() == "":
            raise ValidationError(
                "人工修正必须填写修正后的监测值",
                fields={"corrected_value": "required"},
            )
        try:
            corrected_value = float(corrected_value)
        except (TypeError, ValueError):
            raise ValidationError(
                "修正后的监测值必须为数字", fields={"corrected_value": "invalid_number"}
            )
        # 保留最早的原始读数, 多次修正也能追溯到最初值.
        measurement.original_value = (
            measurement.original_value if measurement.original_value is not None else value_before
        )
        measurement.value = corrected_value
        value_after = corrected_value
        _re_evaluate(measurement)

    measurement.quality_flag = flag
    measurement.quality_reason = reason
    measurement.quality_marked_by = marked_by
    measurement.quality_marked_at = datetime.now()

    _write_log(measurement, "flag", reason, marked_by, value_before, value_after, flag=flag)
    db.session.commit()
    return measurement


def clear_flag(measurement, reason, marked_by=None):
    """撤销质量标记 (留痕保留); 人工修正得到的新值仍作为正式读数."""
    if not measurement.quality_flag:
        raise ValidationError("该读数当前没有质量标记", fields={"quality_flag": "not_flagged"})
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("撤销标记必须填写原因", fields={"reason": "required"})
    marked_by = (marked_by or "").strip() or "未署名"

    value_before = value_after = measurement.value
    _write_log(measurement, "clear", reason, marked_by, value_before, value_after)

    measurement.quality_flag = None
    measurement.quality_reason = None
    measurement.quality_marked_by = None
    measurement.quality_marked_at = None
    measurement.original_value = None

    db.session.commit()
    return measurement


def _re_evaluate(measurement):
    """按修正后的值重新判定超标, 同步 / 撤销超标记录."""
    meta = get_pollutant(measurement.pollutant)
    evaluation = exceedance_rules.evaluate(
        measurement.pollutant, measurement.period, measurement.value
    )
    measurement.unit = evaluation.get("unit") or measurement.unit
    measurement.limit_value = evaluation["limit"]
    measurement.exceed_ratio = evaluation["ratio"]
    measurement.is_exceeded = evaluation["exceeded"]

    if evaluation["exceeded"]:
        from ..models import Exceedance

        record = measurement.exceedance
        if record is None:
            measurement.exceedance = Exceedance(
                station_id=measurement.station_id,
                pollutant=measurement.pollutant,
                period=measurement.period,
                measured_at=measurement.measured_at,
                value=measurement.value,
                limit_value=evaluation["limit"],
                exceed_ratio=evaluation["ratio"],
                level=evaluation["level"],
                status="pending",
            )
        else:
            record.value = measurement.value
            record.limit_value = evaluation["limit"]
            record.exceed_ratio = evaluation["ratio"]
            record.level = evaluation["level"]
            record.measured_at = measurement.measured_at
            # 修正产生的新超标重新进入待办
            record.status = "pending"
            record.note = None
            record.annotator = None
            record.annotated_at = None
    elif measurement.exceedance is not None:
        db.session.delete(measurement.exceedance)


def reset_quality_state(measurement):
    """读数被重新录入覆盖时清空当前标记 (历史留痕仍保留)."""
    measurement.quality_flag = None
    measurement.quality_reason = None
    measurement.quality_marked_by = None
    measurement.quality_marked_at = None
    measurement.original_value = None


def clear_on_overwrite(measurement, recorder=None, new_value=None):
    """录入覆盖已有读数时自动撤销遗留标记, 并写入一条留痕."""
    if not measurement.quality_flag:
        return
    reason = "该读数被重新录入覆盖, 原标记自动撤销"
    marked_by = (recorder or measurement.quality_marked_by or "系统").strip() or "系统"
    _write_log(
        measurement,
        "clear",
        reason,
        marked_by,
        measurement.value,
        new_value if new_value is not None else measurement.value,
    )
    reset_quality_state(measurement)


def _split(value):
    if not value:
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def history_query(args):
    """质量标记留痕查询 (供留痕列表与审计)."""
    query = (
        db.session.query(QualityFlagLog)
        .join(Measurement, QualityFlagLog.measurement_id == Measurement.id)
        .join(Station, Measurement.station_id == Station.id)
    )

    measurement_id = (args.get("measurement_id") or "").strip()
    if measurement_id:
        try:
            query = query.filter(QualityFlagLog.measurement_id == int(measurement_id))
        except ValueError:
            raise ValidationError(
                "measurement_id 参数必须为整数", fields={"measurement_id": "invalid_integer"}
            )

    station_ids = _split(args.get("station_id"))
    if station_ids:
        try:
            query = query.filter(Measurement.station_id.in_([int(item) for item in station_ids]))
        except ValueError:
            raise ValidationError(
                "station_id 参数必须为整数", fields={"station_id": "invalid_integer"}
            )

    flags = _split(args.get("quality_flag"))
    if flags:
        unknown = [item for item in flags if item not in QUALITY_FLAG_LABELS]
        if unknown:
            raise ValidationError(
                "未知质量标记: %s" % ", ".join(unknown), fields={"quality_flag": "unknown"}
            )
        query = query.filter(QualityFlagLog.quality_flag.in_(flags))

    actions = _split(args.get("action"))
    if actions:
        query = query.filter(QualityFlagLog.action.in_(actions))

    marker = (args.get("marked_by") or "").strip()
    if marker:
        query = query.filter(QualityFlagLog.marked_by.like("%" + marker + "%"))

    keyword = (args.get("keyword") or "").strip()
    if keyword:
        like = "%" + keyword + "%"
        query = query.filter(
            or_(
                Station.name.like(like),
                Station.code.like(like),
                QualityFlagLog.reason.like(like),
            )
        )

    return query.order_by(QualityFlagLog.marked_at.desc(), QualityFlagLog.id.desc())
