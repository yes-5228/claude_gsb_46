"""监测数据记录."""
from ..domain.constants import (
    DATA_SOURCE_LABELS,
    INVALID_QUALITY_FLAGS,
    PERIOD_LABELS,
    QUALITY_FLAG_LABELS,
    label_of,
)
from ..domain.standards import get_pollutant
from ..extensions import db
from .base import TimestampMixin, iso


class Measurement(TimestampMixin, db.Model):
    __tablename__ = "measurements"
    __table_args__ = (
        db.UniqueConstraint(
            "station_id", "pollutant", "period", "measured_at",
            name="uq_measurement_point_factor_time",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    station_id = db.Column(
        db.Integer, db.ForeignKey("stations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pollutant = db.Column(db.String(16), nullable=False, index=True)
    period = db.Column(db.String(16), nullable=False, default="hourly")
    value = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(16))
    limit_value = db.Column(db.Float)
    exceed_ratio = db.Column(db.Float)
    is_exceeded = db.Column(db.Boolean, nullable=False, default=False, index=True)
    measured_at = db.Column(db.DateTime, nullable=False, index=True)
    data_source = db.Column(db.String(16), nullable=False, default="manual")
    recorder = db.Column(db.String(64))
    remark = db.Column(db.Text)

    # 数据质量标记 (当前状态); 完整留痕见 QualityFlagLog.
    quality_flag = db.Column(db.String(16), index=True)
    quality_reason = db.Column(db.Text)
    quality_marked_by = db.Column(db.String(64))
    quality_marked_at = db.Column(db.DateTime, index=True)
    # 人工修正前的原始读数, 与修正后的 value 对照保留.
    original_value = db.Column(db.Float)

    station = db.relationship("Station", back_populates="measurements")
    exceedance = db.relationship(
        "Exceedance",
        back_populates="measurement",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    quality_logs = db.relationship(
        "QualityFlagLog",
        back_populates="measurement",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="QualityFlagLog.id.desc()",
    )

    @property
    def is_invalid(self):
        """离群值 / 仪器异常标记的读数视为无效, 不参与达标率与排名."""
        return self.quality_flag in INVALID_QUALITY_FLAGS

    @property
    def is_quality_flagged(self):
        return self.quality_flag is not None

    def quality_flag_label(self):
        return label_of(QUALITY_FLAG_LABELS, self.quality_flag) if self.quality_flag else None

    def quality_payload(self):
        return {
            "quality_flag": self.quality_flag,
            "quality_flag_label": self.quality_flag_label(),
            "quality_reason": self.quality_reason,
            "quality_marked_by": self.quality_marked_by,
            "quality_marked_at": iso(self.quality_marked_at),
            "original_value": self.original_value,
            "is_invalid": self.is_invalid,
        }

    def pollutant_label(self):
        meta = get_pollutant(self.pollutant)
        return meta["label"] if meta else self.pollutant

    def to_dict(self, include_station=False):
        payload = {
            "id": self.id,
            "station_id": self.station_id,
            "pollutant": self.pollutant,
            "pollutant_label": self.pollutant_label(),
            "period": self.period,
            "period_label": label_of(PERIOD_LABELS, self.period),
            "value": self.value,
            "unit": self.unit,
            "limit_value": self.limit_value,
            "exceed_ratio": self.exceed_ratio,
            "is_exceeded": bool(self.is_exceeded),
            "measured_at": iso(self.measured_at),
            "data_source": self.data_source,
            "data_source_label": label_of(DATA_SOURCE_LABELS, self.data_source),
            "recorder": self.recorder,
            "remark": self.remark,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
            "exceedance_id": self.exceedance.id if self.exceedance else None,
            "exceedance_status": self.exceedance.status if self.exceedance else None,
            **self.quality_payload(),
        }
        if include_station and self.station:
            payload["station"] = {
                "id": self.station.id,
                "code": self.station.code,
                "name": self.station.name,
                "area": self.station.area,
                "station_type_label": self.station.to_dict()["station_type_label"],
            }
        return payload

    def __repr__(self):
        return "<Measurement %s %s %s>" % (self.station_id, self.pollutant, self.measured_at)

    @classmethod
    def unique_key(cls, station_id, pollutant, period, measured_at):
        return "%s|%s|%s|%s" % (station_id, pollutant, period, iso(measured_at))
