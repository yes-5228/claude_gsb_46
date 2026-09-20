"""监测数据查询: 过滤条件解析, 统计聚合与导出数据准备."""
from datetime import datetime, time

from sqlalchemy import cast, func, or_

from ..domain.constants import (
    DATA_SOURCE_LABELS,
    EXCEEDANCE_STATUS_LABELS,
    PERIOD_LABELS,
    QUALITY_FLAG_INVALID,
    QUALITY_FLAG_LABELS,
    STATION_TYPE_LABELS,
)
from ..domain.standards import POLLUTANT_CODES, get_pollutant
from ..errors import ValidationError
from ..extensions import db
from ..models import Exceedance, Measurement, Station
from ..models.base import iso
from ..utils.validation import parse_date

GROUP_BY_CHOICES = ("station", "area", "pollutant", "period", "day", "month", "data_source")
METRIC_CHOICES = ("avg", "max", "min", "count", "sum")
SORT_CHOICES = ("measured_at", "value", "exceed_ratio", "pollutant", "station_code", "created_at")


def _split(value):
    if not value:
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _int_list(args, name):
    values = []
    for item in _split(args.get(name)):
        try:
            values.append(int(item))
        except ValueError:
            raise ValidationError("%s 参数必须为整数" % name, fields={name: "invalid_integer"})
    return values


def _float_arg(args, name):
    raw = args.get(name)
    if raw in (None, ""):
        return None
    try:
        return float(raw)
    except ValueError:
        raise ValidationError("%s 参数必须为数字" % name, fields={name: "invalid_number"})


def _bool_arg(args, name):
    raw = args.get(name)
    if raw in (None, ""):
        return None
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _date_arg(args, name, end_of_day=False):
    raw = args.get(name)
    if raw in (None, ""):
        return None
    parsed = parse_date(raw, name)
    return datetime.combine(parsed, time.max if end_of_day else time.min)


def parse_filters(args):
    """Translate request args into a normalised filter dictionary."""
    pollutants = [item.upper() for item in _split(args.get("pollutant"))]
    unknown = [item for item in pollutants if item not in POLLUTANT_CODES]
    if unknown:
        raise ValidationError(
            "未知监测因子: %s" % ", ".join(unknown), fields={"pollutant": "unknown"}
        )

    periods = _split(args.get("period"))
    for period in periods:
        if period not in PERIOD_LABELS:
            raise ValidationError("未知数据周期: %s" % period, fields={"period": "unknown"})

    quality_flags = _split(args.get("quality_flag"))
    for flag in quality_flags:
        if flag not in QUALITY_FLAG_LABELS:
            raise ValidationError(
                "未知质量标记: %s" % flag, fields={"quality_flag": "unknown"}
            )
    quality_state = (args.get("quality_state") or "").strip()
    if quality_state and quality_state not in ("valid", "invalid", "marked", "unmarked"):
        raise ValidationError(
            "quality_state 仅支持: valid / invalid / marked / unmarked",
            fields={"quality_state": "unknown"},
        )

    filters = {
        "station_ids": _int_list(args, "station_id"),
        "areas": _split(args.get("area")),
        "station_types": _split(args.get("station_type")),
        "pollutants": pollutants,
        "periods": periods,
        "data_sources": _split(args.get("data_source")),
        "is_exceeded": _bool_arg(args, "is_exceeded"),
        "exceedance_status": _split(args.get("exceedance_status")),
        "quality_flags": quality_flags,
        "quality_state": quality_state or None,
        "include_invalid": _bool_arg(args, "include_invalid") is True,
        "date_from": _date_arg(args, "date_from"),
        "date_to": _date_arg(args, "date_to", end_of_day=True),
        "min_value": _float_arg(args, "min_value"),
        "max_value": _float_arg(args, "max_value"),
        "keyword": (args.get("keyword") or "").strip(),
        "recorder": (args.get("recorder") or "").strip(),
    }
    if filters["date_from"] and filters["date_to"] and filters["date_from"] > filters["date_to"]:
        raise ValidationError(
            "开始时间不能晚于结束时间", fields={"date_from": "range_invalid"}
        )
    if (
        filters["min_value"] is not None
        and filters["max_value"] is not None
        and filters["min_value"] > filters["max_value"]
    ):
        raise ValidationError("最小值不能大于最大值", fields={"min_value": "range_invalid"})
    return filters


def apply_filters(query, filters):
    query = query.join(Station, Measurement.station_id == Station.id)
    if filters["station_ids"]:
        query = query.filter(Measurement.station_id.in_(filters["station_ids"]))
    if filters["areas"]:
        query = query.filter(Station.area.in_(filters["areas"]))
    if filters["station_types"]:
        query = query.filter(Station.station_type.in_(filters["station_types"]))
    if filters["pollutants"]:
        query = query.filter(Measurement.pollutant.in_(filters["pollutants"]))
    if filters["periods"]:
        query = query.filter(Measurement.period.in_(filters["periods"]))
    if filters["data_sources"]:
        query = query.filter(Measurement.data_source.in_(filters["data_sources"]))
    if filters["is_exceeded"] is not None:
        query = query.filter(Measurement.is_exceeded.is_(filters["is_exceeded"]))
    if filters["quality_flags"]:
        query = query.filter(Measurement.quality_flag.in_(filters["quality_flags"]))
    if filters.get("quality_state"):
        state = filters["quality_state"]
        if state == "valid":
            query = query.filter(
                or_(Measurement.quality_flag.is_(None),
                    Measurement.quality_flag.notin_(tuple(QUALITY_FLAG_INVALID)))
            )
        elif state == "invalid":
            query = query.filter(Measurement.quality_flag.in_(tuple(QUALITY_FLAG_INVALID)))
        elif state == "marked":
            query = query.filter(Measurement.quality_flag.isnot(None))
        else:  # unmarked
            query = query.filter(Measurement.quality_flag.is_(None))
    if filters["date_from"]:
        query = query.filter(Measurement.measured_at >= filters["date_from"])
    if filters["date_to"]:
        query = query.filter(Measurement.measured_at <= filters["date_to"])
    if filters["min_value"] is not None:
        query = query.filter(Measurement.value >= filters["min_value"])
    if filters["max_value"] is not None:
        query = query.filter(Measurement.value <= filters["max_value"])
    if filters["recorder"]:
        query = query.filter(Measurement.recorder.like("%" + filters["recorder"] + "%"))
    if filters["keyword"]:
        like = "%" + filters["keyword"] + "%"
        query = query.filter(
            or_(Station.name.like(like), Station.code.like(like), Station.address.like(like))
        )
    if filters["exceedance_status"]:
        query = query.join(Exceedance, Exceedance.measurement_id == Measurement.id).filter(
            Exceedance.status.in_(filters["exceedance_status"])
        )
    return query


def exclude_invalid(query):
    """Filter out readings marked as 离群值 / 仪器异常 (used by statistics & ranking)."""
    return query.filter(
        or_(Measurement.quality_flag.is_(None),
            Measurement.quality_flag.notin_(tuple(QUALITY_FLAG_INVALID)))
    )


def _effective_filters(args):
    """Filters for aggregation: invalid readings are excluded unless explicitly requested."""
    filters = parse_filters(args)
    invalid_requested = bool(filters["quality_flags"]) and set(filters["quality_flags"]) <= QUALITY_FLAG_INVALID
    if not filters["include_invalid"] and not invalid_requested and filters["quality_state"] != "invalid":
        filters["_drop_invalid"] = True
    else:
        filters["_drop_invalid"] = False
    return filters


def _aggregate_query(filters):
    def builder(*entities):
        query = db.session.query(*entities)
        query = apply_filters(query, filters)
        if filters.get("_drop_invalid"):
            query = exclude_invalid(query)
        return query
    return builder


def apply_sort(query, sort=None, order="desc"):
    sort = sort if sort in SORT_CHOICES else "measured_at"
    column = {
        "measured_at": Measurement.measured_at,
        "value": Measurement.value,
        "exceed_ratio": Measurement.exceed_ratio,
        "pollutant": Measurement.pollutant,
        "station_code": Station.code,
        "created_at": Measurement.created_at,
    }[sort]
    primary = column.desc() if (order or "desc").lower() == "desc" else column.asc()
    return query.order_by(primary, Measurement.id.desc())


def measurement_query(args):
    filters = parse_filters(args)
    query = apply_filters(db.session.query(Measurement), filters)
    return apply_sort(query, args.get("sort"), args.get("order")), filters


def _quality_counts(filters):
    """Count flagged / invalid / corrected readings within the filter scope."""
    base = apply_filters(db.session.query(Measurement), filters)
    rows = (
        base.with_entities(Measurement.quality_flag, func.count(Measurement.id))
        .filter(Measurement.quality_flag.isnot(None))
        .group_by(Measurement.quality_flag)
        .all()
    )
    by_flag = {flag: int(count) for flag, count in rows}
    invalid_count = sum(by_flag.get(flag, 0) for flag in QUALITY_FLAG_INVALID)
    return {
        "by_flag": [
            {"key": flag, "label": QUALITY_FLAG_LABELS[flag], "count": by_flag.get(flag, 0)}
            for flag in QUALITY_FLAG_LABELS
        ],
        "marked_count": sum(by_flag.values()),
        "invalid_count": invalid_count,
        "corrected_count": by_flag.get("corrected", 0),
    }


def summary(filters, exclude_invalid_data=None):
    """Aggregate counters shown above the query result table.

    Invalid readings (离群值 / 仪器异常) are excluded from the rate calculations;
    the raw counts are returned separately under ``quality`` so the UI can show
    both 全部 and 有效数据 口径.
    """
    if exclude_invalid_data is None:
        # 默认统计口径剔除无效数据; 显式 include_invalid=true 或筛选无效数据时保留
        invalid_requested = bool(filters["quality_flags"]) and set(
            filters["quality_flags"]) <= QUALITY_FLAG_INVALID
        exclude_invalid_data = (
            not filters["include_invalid"]
            and not invalid_requested
            and filters.get("quality_state") != "invalid"
        )
    query = apply_filters(
        db.session.query(
            func.count(Measurement.id),
            func.sum(cast(Measurement.is_exceeded, db.Integer)),
            func.count(func.distinct(Measurement.station_id)),
            func.min(Measurement.measured_at),
            func.max(Measurement.measured_at),
            func.avg(Measurement.value),
        ),
        filters,
    )
    if exclude_invalid_data:
        query = exclude_invalid(query)
    total, exceeded, stations, first_at, last_at, avg_value = query.one()
    total = int(total or 0)
    exceeded = int(exceeded or 0)

    # 原始口径 (含无效读数), 供概览/卡片展示"有效 X / 全部 Y"
    raw_row = apply_filters(
        db.session.query(
            func.count(Measurement.id),
            func.sum(cast(Measurement.is_exceeded, db.Integer)),
        ),
        filters,
    ).one()
    raw_total = int(raw_row[0] or 0)
    raw_exceeded = int(raw_row[1] or 0)

    return {
        "total": total,
        "exceeded_count": exceeded,
        "compliance_count": total - exceeded,
        "exceed_rate": round(exceeded / total, 4) if total else 0.0,
        "compliance_rate": round((total - exceeded) / total, 4) if total else 0.0,
        "raw_total": raw_total,
        "raw_exceeded_count": raw_exceeded,
        "station_count": int(stations or 0),
        "first_measured_at": iso(first_at),
        "last_measured_at": iso(last_at),
        "avg_value": round(float(avg_value), 2) if avg_value is not None else None,
        "invalid_excluded": exclude_invalid_data,
        "quality": _quality_counts(filters),
    }


def _metric_expression(metric):
    return {
        "avg": func.avg(Measurement.value),
        "max": func.max(Measurement.value),
        "min": func.min(Measurement.value),
        "count": func.count(Measurement.id),
        "sum": func.sum(Measurement.value),
    }[metric]


def statistics(args):
    """Grouped aggregation used by the query page statistics panel.

    Invalid readings (离群值 / 仪器异常) are excluded by default; pass
    ``include_invalid=true`` to compute on the raw data. Grouping by station
    yields the compliance ranking (sorted by compliance rate).
    """
    filters = _effective_filters(args)
    group_by = args.get("group_by") or "pollutant"
    metric = args.get("metric") or "avg"
    if group_by not in GROUP_BY_CHOICES:
        raise ValidationError(
            "group_by 仅支持: %s" % ", ".join(GROUP_BY_CHOICES), fields={"group_by": "unknown"}
        )
    if metric not in METRIC_CHOICES:
        raise ValidationError(
            "metric 仅支持: %s" % ", ".join(METRIC_CHOICES), fields={"metric": "unknown"}
        )

    build = _aggregate_query(filters)
    value_expr = _metric_expression(metric).label("metric_value")
    count_expr = func.count(Measurement.id).label("row_count")
    exceeded_expr = func.sum(cast(Measurement.is_exceeded, db.Integer)).label("exceeded_count")

    if group_by == "station":
        query = build(
            Station.id.label("station_id"),
            Station.code.label("station_code"),
            Station.name.label("station_name"),
            Station.area.label("area"),
            value_expr,
            count_expr,
            exceeded_expr,
        ).group_by(Station.id, Station.code, Station.name, Station.area)
        is_time_group = False
    elif group_by == "area":
        query = build(
            Station.area.label("area"), value_expr, count_expr, exceeded_expr
        ).group_by(Station.area)
        is_time_group = False
    elif group_by == "day":
        bucket = func.date(Measurement.measured_at).label("bucket")
        query = build(bucket, value_expr, count_expr, exceeded_expr).group_by(bucket)
        is_time_group = True
    elif group_by == "month":
        year = func.extract("year", Measurement.measured_at).label("year")
        month = func.extract("month", Measurement.measured_at).label("month")
        query = build(year, month, value_expr, count_expr, exceeded_expr).group_by(
            year, month
        )
        is_time_group = True
    else:
        column = {
            "pollutant": Measurement.pollutant,
            "period": Measurement.period,
            "data_source": Measurement.data_source,
        }[group_by]
        query = build(
            column.label("bucket"), value_expr, count_expr, exceeded_expr
        ).group_by(column)
        is_time_group = False

    rows = query.all()

    items = []
    for row in rows:
        data = dict(row._mapping)
        count = int(data.get("row_count") or 0)
        exceeded = int(data.get("exceeded_count") or 0)
        raw_value = data.get("metric_value")
        if group_by == "station":
            key = data.get("station_code")
            label = "%s %s" % (data.get("station_code"), data.get("station_name"))
        elif group_by == "area":
            key = label = data.get("area")
        elif group_by == "day":
            key = str(data.get("bucket"))
            label = key
        elif group_by == "month":
            key = "%04d-%02d" % (int(data.get("year")), int(data.get("month")))
            label = key
        elif group_by == "pollutant":
            key = data.get("bucket")
            meta = get_pollutant(key)
            label = meta["label"] if meta else key
        elif group_by == "period":
            key = data.get("bucket")
            label = PERIOD_LABELS.get(key, key)
        else:
            key = data.get("bucket")
            label = DATA_SOURCE_LABELS.get(key, key)

        items.append(
            {
                "key": key,
                "label": label,
                "value": round(float(raw_value), 2) if raw_value is not None else None,
                "count": count,
                "exceeded_count": exceeded,
                "compliance_count": count - exceeded,
                "exceed_rate": round(exceeded / count, 4) if count else 0.0,
                "compliance_rate": round((count - exceeded) / count, 4) if count else 0.0,
            }
        )

    if is_time_group:
        items.sort(key=lambda item: item["key"])
    elif group_by == "station":
        # 站点分组即达标率排名: 达标率高者靠前, 达标率相同数据量多者靠前
        items.sort(key=lambda item: (-item["compliance_rate"], -item["count"]))
        for index, item in enumerate(items, start=1):
            item["rank"] = index
    else:
        items.sort(key=lambda item: (item["value"] is None, -(item["value"] or 0)))

    return {
        "group_by": group_by,
        "metric": metric,
        "invalid_excluded": filters["_drop_invalid"],
        "items": items,
        "totals": {
            "count": sum(item["count"] for item in items),
            "exceeded_count": sum(item["exceeded_count"] for item in items),
        },
    }


def option_payload():
    return {
        "group_by": list(GROUP_BY_CHOICES),
        "metric": list(METRIC_CHOICES),
        "sort": list(SORT_CHOICES),
        "exceedance_status": [
            {"value": key, "label": label} for key, label in EXCEEDANCE_STATUS_LABELS.items()
        ],
        "station_type": [
            {"value": key, "label": label} for key, label in STATION_TYPE_LABELS.items()
        ],
        "quality_flag": [
            {"value": key, "label": label} for key, label in QUALITY_FLAG_LABELS.items()
        ],
    }
