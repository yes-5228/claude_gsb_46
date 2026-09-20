"""数据质量标记 API: 标记 / 撤销 / 留痕查询."""
from flask import Blueprint

from ..domain.constants import QUALITY_FLAG_LABELS
from ..services import quality_service
from ..utils.pagination import paginate_query
from ..utils.validation import Validator
from .helpers import json_payload

bp = Blueprint("quality", __name__)


@bp.get("/<int:measurement_id>/flags")
def measurement_flags(measurement_id):
    """单条读数的完整标记留痕 (最新在前)."""
    measurement = quality_service.get_measurement(measurement_id)
    return {
        "measurement": measurement.to_dict(include_station=True),
        "items": [log.to_dict() for log in measurement.quality_logs],
    }


@bp.post("/<int:measurement_id>/flag")
def flag_measurement(measurement_id):
    """把读数标记为离群值 / 仪器异常 / 人工修正."""
    data = json_payload()
    validator = Validator(data)
    flag = validator.choice(
        "quality_flag",
        "质量标记",
        choices=tuple(QUALITY_FLAG_LABELS.keys()),
        required=True,
    )
    reason = validator.text("reason", "标记原因", required=True, max_length=500)
    marked_by = validator.text("marked_by", "标记人", required=False, max_length=64)
    corrected_value = validator.number(
        "corrected_value", "修正后监测值", required=(flag == "corrected")
    )
    validator.raise_if_invalid("标记信息不合法")

    measurement = quality_service.get_measurement(measurement_id)
    measurement = quality_service.flag_measurement(
        measurement,
        flag=flag,
        reason=reason,
        marked_by=marked_by,
        corrected_value=corrected_value,
    )
    return measurement.to_dict(include_station=True)


@bp.post("/<int:measurement_id>/clear-flag")
def clear_measurement_flag(measurement_id):
    """撤销读数的质量标记 (留痕保留)."""
    data = json_payload()
    validator = Validator(data)
    reason = validator.text("reason", "撤销原因", required=True, max_length=500)
    marked_by = validator.text("marked_by", "操作人", required=False, max_length=64)
    validator.raise_if_invalid("撤销信息不合法")

    measurement = quality_service.get_measurement(measurement_id)
    measurement = quality_service.clear_flag(
        measurement, reason=reason, marked_by=marked_by
    )
    return measurement.to_dict(include_station=True)


@bp.get("/flag-logs")
def flag_logs():
    """质量标记留痕分页查询 (跨读数)."""
    from flask import request

    query = quality_service.history_query(request.args)
    return paginate_query(query, lambda row: row.to_dict())
