import { useCallback, useEffect, useState } from 'react'
import {
  clearMeasurementQuality,
  getMeasurement,
  listQualityLogs,
  markMeasurementQuality
} from '../../../api/measurements.js'
import Modal from '../../../components/common/Modal.jsx'
import Tag from '../../../components/common/Tag.jsx'
import QualityFlagTag from '../../../components/common/QualityFlagTag.jsx'
import { Field, Input, Textarea } from '../../../components/common/FormField.jsx'
import { Alert, ErrorState, Loading } from '../../../components/common/Feedback.jsx'
import { useToast } from '../../../components/common/ToastProvider.jsx'
import { QUALITY_FLAG_OPTIONS, QUALITY_FLAG_TONE } from '../../../constants/index.js'
import { useAsyncData } from '../../../hooks/useAsyncData.js'
import { formatDateTime, formatNumber } from '../../../utils/format.js'

export default function QualityFlagModal({ measurementId, onClose, onSaved }) {
  const toast = useToast()
  const loader = useCallback(() => getMeasurement(measurementId), [measurementId])
  const { data, loading, error, reload } = useAsyncData(loader, { immediate: Boolean(measurementId) })
  const [logs, setLogs] = useState([])
  const [form, setForm] = useState({ flag: 'outlier', reason: '', marked_by: '', corrected_value: '' })
  const [errors, setErrors] = useState({})
  const [message, setMessage] = useState(null)
  const [busy, setBusy] = useState(false)
  const [cancelling, setCancelling] = useState(false)

  useEffect(() => {
    if (!data) return
    setForm({
      flag: data.quality_flag || 'outlier',
      reason: data.quality_reason || '',
      marked_by: data.quality_marked_by || '',
      corrected_value:
        data.quality_flag === 'corrected' ? String(data.value ?? '') : ''
    })
    setErrors({})
    setMessage(null)
  }, [data])

  useEffect(() => {
    if (!measurementId) return undefined
    let active = true
    listQualityLogs({ measurement_id: measurementId, page_size: 50 })
      .then((payload) => active && setLogs(payload.items || []))
      .catch(() => active && setLogs([]))
    return () => {
      active = false
    }
  }, [measurementId, data])

  const submit = async () => {
    setBusy(true)
    setMessage(null)
    try {
      await markMeasurementQuality(measurementId, {
        flag: form.flag,
        reason: form.reason,
        marked_by: form.marked_by || null,
        corrected_value: form.flag === 'corrected' ? form.corrected_value : null
      })
      toast.success('质量标记已保存')
      await reload()
      onSaved?.()
    } catch (err) {
      setErrors(err.fields || {})
      setMessage(err.message)
    } finally {
      setBusy(false)
    }
  }

  const unmark = async () => {
    setCancelling(true)
    setMessage(null)
    try {
      await clearMeasurementQuality(measurementId, {
        reason: form.reason || '复核后取消标记',
        marked_by: form.marked_by || null
      })
      toast.success('已取消质量标记 (留痕保留)')
      await reload()
      onSaved?.()
    } catch (err) {
      setMessage(err.message)
    } finally {
      setCancelling(false)
    }
  }

  return (
    <Modal
      open={Boolean(measurementId)}
      wide
      title={data ? `数据质量标记 · ${data.station?.name || ''}` : '数据质量标记'}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose} disabled={busy || cancelling}>
            关闭
          </button>
          {data?.quality_flag ? (
            <button
              type="button"
              className="btn"
              onClick={unmark}
              disabled={busy || cancelling}
              title="取消标记不会删除历史留痕"
            >
              {cancelling ? '处理中...' : '取消标记'}
            </button>
          ) : null}
          <button type="button" className="btn btn-primary" onClick={submit} disabled={busy || !data}>
            {busy ? '保存中...' : '保存标记'}
          </button>
        </>
      }
    >
      {loading && !data ? <Loading /> : null}
      {error && !data ? <ErrorState error={error} /> : null}
      {data ? (
        <div className="stack">
          <dl className="kv">
            <dt>监测点</dt>
            <dd>
              {data.station?.name || '-'} <span className="mono muted">{data.station?.code || ''}</span>
            </dd>
            <dt>监测时间</dt>
            <dd>
              {formatDateTime(data.measured_at)} · {data.period_label}
            </dd>
            <dt>监测因子</dt>
            <dd>{data.pollutant_label}</dd>
            <dt>当前读数</dt>
            <dd>
              <span className={data.is_exceeded ? 'danger-text strong' : 'strong'}>
                {formatNumber(data.value)}
              </span>{' '}
              <span className="muted small">{data.unit}</span>
              {data.original_value !== null && data.original_value !== undefined ? (
                <span className="muted small"> (修正前: {formatNumber(data.original_value)})</span>
              ) : null}
            </dd>
            <dt>当前标记</dt>
            <dd>
              {data.quality_flag ? (
                <QualityFlagTag
                  flag={data.quality_flag}
                  label={data.quality_flag_label}
                  invalid={data.is_quality_invalid}
                />
              ) : (
                <span className="muted">未标记</span>
              )}
            </dd>
            {data.quality_marked_at ? (
              <>
                <dt>标记人 / 时间</dt>
                <dd className="small muted">
                  {data.quality_marked_by || '未署名'} · {formatDateTime(data.quality_marked_at)}
                </dd>
                <dt>标记原因</dt>
                <dd>{data.quality_reason || '-'}</dd>
              </>
            ) : null}
          </dl>

          {message ? <Alert tone="error">{message}</Alert> : null}

          <Field label="标记类型" required error={errors.flag}>
            <div className="stack">
              {QUALITY_FLAG_OPTIONS.map((choice) => (
                <label key={choice.value} className="checkbox" style={{ alignItems: 'flex-start' }}>
                  <input
                    type="radio"
                    name="quality-flag"
                    checked={form.flag === choice.value}
                    onChange={() => setForm({ ...form, flag: choice.value })}
                  />
                  <span>
                    <span className="strong">
                      <Tag tone={QUALITY_FLAG_TONE[choice.value]}>{choice.label}</Tag>
                    </span>
                    <span className="small muted" style={{ display: 'block' }}>
                      {choice.hint}
                    </span>
                  </span>
                </label>
              ))}
            </div>
          </Field>

          <div className="form-grid">
            <Field label="标记人" error={errors.marked_by}>
              <Input
                value={form.marked_by}
                onChange={(event) => setForm({ ...form, marked_by: event.target.value })}
                placeholder="如: 王敏"
              />
            </Field>
            {form.flag === 'corrected' ? (
              <Field label="修正后监测值" required error={errors.corrected_value}>
                <Input
                  type="number"
                  step="0.01"
                  value={form.corrected_value}
                  onChange={(event) => setForm({ ...form, corrected_value: event.target.value })}
                  placeholder="按现场比对 / 复测值填写"
                />
              </Field>
            ) : null}
          </div>

          <Field
            label="标记原因"
            required
            error={errors.reason}
            hint="原因必填, 与标记人、标记时间一并留痕, 后续可在操作记录中追溯"
          >
            <Textarea
              value={form.reason}
              onChange={(event) => setForm({ ...form, reason: event.target.value })}
              invalid={Boolean(errors.reason)}
              placeholder="如: 该读数与相邻时段偏差超过 3 倍标准差, 经现场复核判定为离群值"
            />
          </Field>

          <div>
            <div className="small muted" style={{ marginBottom: 6 }}>
              操作留痕 ({logs.length})
            </div>
            {logs.length === 0 ? (
              <div className="muted small">暂无标记记录</div>
            ) : (
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>操作</th>
                      <th>标记</th>
                      <th>原因</th>
                      <th>标记人</th>
                      <th>标记时间</th>
                      <th>数值变化</th>
                    </tr>
                  </thead>
                  <tbody>
                    {logs.map((log) => (
                      <tr key={log.id}>
                        <td>{log.action_label}</td>
                        <td>{log.flag_label ? <Tag tone={QUALITY_FLAG_TONE[log.flag]}>{log.flag_label}</Tag> : '-'}</td>
                        <td>{log.reason || '-'}</td>
                        <td>{log.marked_by || '未署名'}</td>
                        <td className="cell-nowrap">{formatDateTime(log.marked_at)}</td>
                        <td className="cell-nowrap small muted">
                          {log.value_before !== null && log.value_before !== undefined &&
                          log.value_after !== null && log.value_after !== undefined &&
                          log.value_before !== log.value_after
                            ? `${formatNumber(log.value_before)} → ${formatNumber(log.value_after)}`
                            : '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      ) : null}
    </Modal>
  )
}
