"""数据质量标记操作留痕 (每次标记 / 取消标记 / 修正都追加一条)."""
from datetime import datetime

from ..domain.constants import (
    PERIOD_LABELS,
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
    station_id = db.Column(db.Integer, index=True)
    action = db.Column(db.String(16), nullable=False)  # mark / unmark
    flag = db.Column(db.String(16))
    reason = db.Column(db.Text)
    marked_by = db.Column(db.String(64))
    marked_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    value_before = db.Column(db.Float)
    value_after = db.Column(db.Float)

    measurement = db.relationship("Measurement")

    def to_dict(self, include_measurement=False):
        payload = {
            "id": self.id,
            "measurement_id": self.measurement_id,
            "station_id": self.station_id,
            "action": self.action,
            "action_label": "标记" if self.action == "mark" else "取消标记",
            "flag": self.flag,
            "flag_label": label_of(QUALITY_FLAG_LABELS, self.flag) if self.flag else None,
            "reason": self.reason,
            "marked_by": self.marked_by,
            "marked_at": iso(self.marked_at),
            "value_before": self.value_before,
            "value_after": self.value_after,
            "created_at": iso(self.created_at),
        }
        if include_measurement and self.measurement:
            m = self.measurement
            payload["measurement"] = {
                "id": m.id,
                "station_id": m.station_id,
                "pollutant": m.pollutant,
                "pollutant_label": m.pollutant_label(),
                "period": m.period,
                "period_label": label_of(PERIOD_LABELS, m.period),
                "measured_at": iso(m.measured_at),
            }
        return payload

    def __repr__(self):
        return "<QualityFlagLog %s %s %s>" % (self.measurement_id, self.action, self.flag)
