"""数据质量标记业务逻辑.

支持把单条读数标记为离群值 / 仪器异常 / 人工修正:
- 标记原因、标记人、标记时间全部留痕 (measurements 快照 + quality_flag_logs 追加日志);
- 离群值、仪器异常视为无效数据, 不参与达标率与排名统计, 但明细仍可查询;
- 人工修正可提交修正值, 系统按修正值重新判定超标;
- 取消标记不删除历史日志, 实现可追溯。
"""
from datetime import datetime

from ..domain import exceedance_rules
from ..domain.constants import QUALITY_FLAG_LABELS
from ..errors import NotFoundError, ValidationError
from ..extensions import db
from ..models import Measurement, QualityFlagLog

FLAG_CHOICES = tuple(QUALITY_FLAG_LABELS.keys())


def get_measurement(measurement_id):
    measurement = db.session.get(Measurement, measurement_id)
    if measurement is None:
        raise NotFoundError("监测数据不存在: id=%s" % measurement_id)
    return measurement


def mark(measurement, flag, reason=None, marked_by=None, corrected_value=None):
    """Apply a quality flag to one reading."""
    if flag not in FLAG_CHOICES:
        raise ValidationError(
            "质量标记取值不合法, 可选: %s" % ", ".join(FLAG_CHOICES),
            fields={"flag": "unknown"},
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
                "人工修正必须填写修正后监测值", fields={"corrected_value": "required"}
            )
        try:
            corrected_value = float(corrected_value)
        except (TypeError, ValueError):
            raise ValidationError(
                "修正后监测值必须为数字", fields={"corrected_value": "invalid_number"}
            )
        # 第一次修正保存原始读数; 多次修正始终保留最原始的值
        if measurement.original_value is None:
            measurement.original_value = value_before
        measurement.value = corrected_value
        value_after = corrected_value
        evaluation = exceedance_rules.evaluate(measurement.pollutant, measurement.period,
                                               corrected_value)
        measurement.unit = evaluation["unit"]
        measurement.limit_value = evaluation["limit"]
        measurement.exceed_ratio = evaluation["ratio"]
        measurement.is_exceeded = evaluation["exceeded"]
        # 复用录入流程的超标记录同步逻辑, 保持一条读数最多一条超标记录
        from .measurement_service import _sync_exceedance
        from ..domain.standards import get_pollutant
        _sync_exceedance(measurement, get_pollutant(measurement.pollutant), evaluation)

    measurement.quality_flag = flag
    measurement.quality_reason = reason
    measurement.quality_marked_by = marked_by
    measurement.quality_marked_at = datetime.now()

    db.session.add(
        QualityFlagLog(
            measurement_id=measurement.id,
            station_id=measurement.station_id,
            action="mark",
            flag=flag,
            reason=reason,
            marked_by=marked_by,
            marked_at=measurement.quality_marked_at,
            value_before=value_before,
            value_after=value_after,
        )
    )
    db.session.commit()
    return measurement


def unmark(measurement, reason=None, marked_by=None):
    """Remove the quality flag. Audit history is retained.

    Cancelling a 人工修正 restores the original reading and re-evaluates
    the exceedance status so the rollback is complete.
    """
    if measurement.quality_flag is None:
        raise ValidationError("该读数当前没有质量标记", fields={"flag": "not_flagged"})
    previous_flag = measurement.quality_flag
    value_before = measurement.value
    value_after = value_before

    if previous_flag == "corrected" and measurement.original_value is not None:
        restored = measurement.original_value
        evaluation = exceedance_rules.evaluate(measurement.pollutant, measurement.period, restored)
        measurement.value = restored
        measurement.unit = evaluation["unit"]
        measurement.limit_value = evaluation["limit"]
        measurement.exceed_ratio = evaluation["ratio"]
        measurement.is_exceeded = evaluation["exceeded"]
        from .measurement_service import _sync_exceedance
        from ..domain.standards import get_pollutant
        _sync_exceedance(measurement, get_pollutant(measurement.pollutant), evaluation)
        value_after = restored

    measurement.clear_quality()
    db.session.add(
        QualityFlagLog(
            measurement_id=measurement.id,
            station_id=measurement.station_id,
            action="unmark",
            flag=None,
            reason=(reason or "").strip() or None,
            marked_by=(marked_by or "").strip() or "未署名",
            marked_at=datetime.now(),
            value_before=value_before,
            value_after=value_after,
        )
    )
    db.session.commit()
    return measurement


def log_query(args):
    """Paginated history used by the quality audit view."""
    from sqlalchemy import or_

    query = QualityFlagLog.query.join(
        Measurement, QualityFlagLog.measurement_id == Measurement.id
    )
    measurement_id = args.get("measurement_id")
    if measurement_id:
        query = query.filter(QualityFlagLog.measurement_id == int(measurement_id))
    station_ids = str(args.get("station_id") or "")
    if station_ids.strip():
        query = query.filter(
            QualityFlagLog.station_id.in_([int(item) for item in station_ids.split(",") if item.strip()])
        )
    flags = [item.strip() for item in str(args.get("flag") or "").split(",") if item.strip()]
    if flags:
        query = query.filter(QualityFlagLog.flag.in_(flags))
    keyword = (args.get("keyword") or "").strip()
    if keyword:
        like = "%" + keyword + "%"
        query = query.filter(
            or_(
                QualityFlagLog.reason.like(like),
                QualityFlagLog.marked_by.like(like),
            )
        )
    return query.order_by(QualityFlagLog.marked_at.desc(), QualityFlagLog.id.desc())
