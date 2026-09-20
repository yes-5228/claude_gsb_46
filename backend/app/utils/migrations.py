"""轻量结构补丁: 为已存在的库补齐新增列 (项目无 Alembic).

``db.create_all()`` 只能创建缺失的表, 不会给已有表加列. 这里用
``ALTER TABLE ... ADD COLUMN`` 把历史库平滑升级到当前模型.
"""
from sqlalchemy import inspect, text

from ..extensions import db

# table -> {column: column DDL}
_PENDING_COLUMNS = {
    "measurements": {
        "quality_flag": "VARCHAR(16)",
        "quality_reason": "TEXT",
        "quality_marked_by": "VARCHAR(64)",
        "quality_marked_at": "DATETIME",
        "original_value": "FLOAT",
    },
}


def ensure_schema():
    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())
    statements = []
    for table, columns in _PENDING_COLUMNS.items():
        if table not in existing_tables:
            continue
        present = {column["name"] for column in inspector.get_columns(table)}
        for name, ddl in columns.items():
            if name not in present:
                statements.append(
                    'ALTER TABLE "%s" ADD COLUMN %s %s' % (table, name, ddl)
                )
    if not statements:
        return 0
    with db.engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
    return len(statements)
