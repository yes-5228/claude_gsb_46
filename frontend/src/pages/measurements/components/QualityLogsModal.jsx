import { useEffect, useState } from 'react'
import { listQualityLogs } from '../../../api/measurements.js'
import Modal from '../../../components/common/Modal.jsx'
import Tag from '../../../components/common/Tag.jsx'
import Pagination from '../../../components/common/Pagination.jsx'
import { Alert } from '../../../components/common/Feedback.jsx'
import { Field, Input, Select } from '../../../components/common/FormField.jsx'
import { QUALITY_FLAG_OPTIONS, QUALITY_FLAG_TONE } from '../../../constants/index.js'
import { formatDateTime, formatNumber } from '../../../utils/format.js'

export default function QualityLogsModal({ open, onClose, initialMeasurementId }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState({ flag: '', keyword: '' })

  useEffect(() => {
    if (!open) return undefined
    let active = true
    setLoading(true)
    setError(null)
    listQualityLogs({
      ...filters,
      measurement_id: initialMeasurementId || '',
      page,
      page_size: 10
    })
      .then((payload) => active && setData(payload))
      .catch((err) => active && setError(err))
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [open, page, filters, initialMeasurementId])

  return (
    <Modal
      open={open}
      wide
      title="数据质量标记留痕"
      onClose={onClose}
      footer={
        <button type="button" className="btn" onClick={onClose}>
          关闭
        </button>
      }
    >
      <div className="stack">
        <Alert tone="info">
          所有标记、取消标记与人工修正操作均在此留痕; 取消标记不会删除历史记录。
        </Alert>
        <div className="filter-bar">
          {!initialMeasurementId ? (
            <Field label="标记类型">
              <Select
                value={filters.flag}
                onChange={(event) => {
                  setPage(1)
                  setFilters({ ...filters, flag: event.target.value })
                }}
                placeholder="全部类型"
                options={QUALITY_FLAG_OPTIONS}
              />
            </Field>
          ) : null}
          {!initialMeasurementId ? (
            <Field label="关键字 (原因 / 标记人)">
              <Input
                value={filters.keyword}
                onChange={(event) => {
                  setPage(1)
                  setFilters({ ...filters, keyword: event.target.value })
                }}
                placeholder="输入关键字后自动刷新"
              />
            </Field>
          ) : null}
        </div>

        {error ? <Alert tone="error">{error.message}</Alert> : null}

        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>标记时间</th>
                <th>读数</th>
                <th>操作</th>
                <th>标记</th>
                <th>原因</th>
                <th>标记人</th>
                <th>数值变化</th>
              </tr>
            </thead>
            <tbody>
              {(data?.items || []).map((log) => (
                <tr key={log.id}>
                  <td className="cell-nowrap">{formatDateTime(log.marked_at)}</td>
                  <td className="cell-nowrap small">
                    {log.measurement
                      ? `${log.measurement.pollutant_label} · ${formatDateTime(log.measurement.measured_at)}`
                      : `#${log.measurement_id}`}
                  </td>
                  <td>{log.action_label}</td>
                  <td>
                    {log.flag_label ? (
                      <Tag tone={QUALITY_FLAG_TONE[log.flag]}>{log.flag_label}</Tag>
                    ) : (
                      '-'
                    )}
                  </td>
                  <td>{log.reason || '-'}</td>
                  <td>{log.marked_by || '未署名'}</td>
                  <td className="cell-nowrap small muted">
                    {log.value_before !== null && log.value_before !== undefined &&
                    log.value_after !== null && log.value_after !== undefined &&
                    log.value_before !== log.value_after
                      ? `${formatNumber(log.value_before)} → ${formatNumber(log.value_after)}`
                      : '-'}
                  </td>
                </tr>
              ))}
              {!loading && (data?.items || []).length === 0 ? (
                <tr>
                  <td colSpan={7} className="muted" style={{ textAlign: 'center', padding: 24 }}>
                    暂无质量标记记录
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>

        <Pagination
          page={page}
          pages={data?.pages ?? 0}
          total={data?.total ?? 0}
          pageSize={data?.page_size ?? 10}
          onPageChange={setPage}
        />
      </div>
    </Modal>
  )
}
