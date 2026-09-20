"""数据质量标记留痕 (标记 / 撤销标记 / 修正全过程)."""
from ..domain.constants import (
    QUALITY_FLAG_ACTION_LABELS,
    QUALITY_FLAG_LABELS,
    label_of,
)
from ..extensions import db
from .base import TimestampMixin, iso


class QualityFlagLog(TimestampMixin, db.Model):
    __tablename__ = "quality_flag_logs"

    id = db.Column(db.Integer, primary_key=True)
    measurement_id = db.Column(
        db.Integer,
        db.ForeignKey("measurements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action = db.Column(db.String(16), nullable=False)  # flag / clear
    quality_flag = db.Column(db.String(16))
    reason = db.Column(db.Text, nullable=False)
    marked_by = db.Column(db.String(64), nullable=False)
    marked_at = db.Column(db.DateTime, nullable=False, index=True)
    value_before = db.Column(db.Float)
    value_after = db.Column(db.Float)

    measurement = db.relationship("Measurement", back_populates="quality_logs")

    def to_dict(self, include_measurement=False):
        payload = {
            "id": self.id,
            "measurement_id": self.measurement_id,
            "action": self.action,
            "action_label": label_of(QUALITY_FLAG_ACTION_LABELS, self.action),
            "quality_flag": self.quality_flag,
            "quality_flag_label": label_of(QUALITY_FLAG_LABELS, self.quality_flag)
            if self.quality_flag
            else None,
            "reason": self.reason,
            "marked_by": self.marked_by,
            "marked_at": iso(self.marked_at),
            "value_before": self.value_before,
            "value_after": self.value_after,
            "created_at": iso(self.created_at),
            "station_name": self.measurement.station.name
            if self.measurement and self.measurement.station
            else None,
            "station_code": self.measurement.station.code
            if self.measurement and self.measurement.station
            else None,
            "pollutant_label": self.measurement.pollutant_label() if self.measurement else None,
            "period_label": self.measurement.to_dict()["period_label"] if self.measurement else None,
            "measured_at": iso(self.measurement.measured_at) if self.measurement else None,
        }
        if include_measurement and self.measurement:
            payload["measurement"] = self.measurement.to_dict(include_station=True)
        return payload

    def __repr__(self):
        return "<QualityFlagLog %s measurement=%s>" % (self.action, self.measurement_id)
