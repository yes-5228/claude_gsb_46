import { useCallback } from 'react'
import { getMeasurementFlags } from '../../../api/quality.js'
import Modal from '../../../components/common/Modal.jsx'
import Tag from '../../../components/common/Tag.jsx'
import { EmptyState, ErrorState, Loading } from '../../../components/common/Feedback.jsx'
import { useAsyncData } from '../../../hooks/useAsyncData.js'
import {
  QUALITY_FLAG_ACTION_LABELS,
  QUALITY_FLAG_TONE
} from '../../../constants/index.js'
import { formatDateTime, formatNumber } from '../../../utils/format.js'

export default function QualityFlagHistoryModal({ measurementId, onClose }) {
  const loader = useCallback(
    () => getMeasurementFlags(measurementId),
    [measurementId]
  )
  const { data, loading, error } = useAsyncData(loader, { immediate: Boolean(measurementId) })

  const measurement = data?.measurement
  const logs = data?.items ?? []

  return (
    <Modal
      open={Boolean(measurementId)}
      wide
      title="数据质量标记留痕"
      onClose={onClose}
      footer={<button className="btn btn-primary" onClick={onClose}>关闭</button>}
    >
      {loading && !data ? <Loading text="正在加载标记留痕..." /> : null}
      {error && !data ? <ErrorState error={error} /> : null}
      {data ? (
        <div className="stack">
          <dl className="kv">
            <dt>监测点</dt>
            <dd>
              {measurement?.station?.name || '-'} <span className="mono muted">{measurement?.station?.code}</span>
            </dd>
            <dt>监测时间</dt>
            <dd>
              {formatDateTime(measurement?.measured_at)} · {measurement?.period_label}
            </dd>
            <dt>监测因子</dt>
            <dd>{measurement?.pollutant_label}</dd>
            <dt>当前读数</dt>
            <dd>
              {formatNumber(measurement?.value)} <span className="muted small">{measurement?.unit}</span>
              {measurement?.quality_flag === 'corrected' && measurement?.original_value !== null ? (
                <span className="muted small"> (原始值 {formatNumber(measurement.original_value)})</span>
              ) : null}
            </dd>
          </dl>

          {logs.length === 0 ? <EmptyState text="该读数暂无质量标记留痕" icon="📋" /> : null}

          <div className="timeline">
            {logs.map((log) => (
              <div key={log.id} className="timeline-item">
                <div className="inline" style={{ justifyContent: 'space-between' }}>
                  <div className="inline">
                    <Tag tone={log.action === 'clear' ? 'neutral' : QUALITY_FLAG_TONE[log.quality_flag]}>
                      {QUALITY_FLAG_ACTION_LABELS[log.action] || log.action}
                      {log.quality_flag_label ? ` · ${log.quality_flag_label}` : ''}
                    </Tag>
                  </div>
                  <span className="small muted">{formatDateTime(log.marked_at)}</span>
                </div>
                <div style={{ marginTop: 6 }}>{log.reason}</div>
                <div className="small muted" style={{ marginTop: 4 }}>
                  操作人: {log.marked_by}
                  {log.value_before !== null && log.value_after !== null &&
                  log.value_before !== log.value_after
                    ? ` · 数值变更: ${formatNumber(log.value_before)} → ${formatNumber(log.value_after)}`
                    : ''}
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </Modal>
  )
}
