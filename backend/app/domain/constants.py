"""Enumerations shared by the API layer and the frontend."""

PERIOD_LABELS = {"hourly": "小时均值", "daily": "日均值"}

DATA_SOURCE_LABELS = {"manual": "手工录入", "device": "设备上传", "import": "历史导入"}

STATION_TYPE_LABELS = {
    "ambient": "环境空气",
    "traffic": "道路交通",
    "background": "区域背景",
    "industrial": "工业园区",
    "rural": "农村站点",
}

STATION_STATUS_LABELS = {"active": "运行中", "maintenance": "维护中", "offline": "停用"}

EXCEEDANCE_LEVEL_LABELS = {"light": "轻度超标", "moderate": "中度超标", "severe": "重度超标"}

EXCEEDANCE_STATUS_LABELS = {"pending": "待标注", "confirmed": "已确认", "ignored": "已忽略"}

# 数据质量标记: 离群值 / 仪器异常视为无效数据, 不参与达标率与排名;
# 人工修正是对错误读数的订正, 修正后的数据仍为有效数据.
QUALITY_FLAG_LABELS = {
    "outlier": "离群值",
    "instrument": "仪器异常",
    "corrected": "人工修正",
}
INVALID_QUALITY_FLAGS = ("outlier", "instrument")
QUALITY_FLAG_ACTION_LABELS = {"flag": "标记", "clear": "撤销标记"}


def as_options(label_map):
    return [{"value": key, "label": label} for key, label in label_map.items()]


def options_payload():
    return {
        "station_type": as_options(STATION_TYPE_LABELS),
        "station_status": as_options(STATION_STATUS_LABELS),
        "period": as_options(PERIOD_LABELS),
        "data_source": as_options(DATA_SOURCE_LABELS),
        "exceedance_level": as_options(EXCEEDANCE_LEVEL_LABELS),
        "exceedance_status": as_options(EXCEEDANCE_STATUS_LABELS),
        "quality_flag": as_options(QUALITY_FLAG_LABELS),
    }


def label_of(label_map, key):
    return label_map.get(key, key)
