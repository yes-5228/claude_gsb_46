import { useEffect, useState } from 'react'
import { clearMeasurementFlag, flagMeasurement } from '../../../api/quality.js'
import Modal from '../../../components/common/Modal.jsx'
import Tag from '../../../components/common/Tag.jsx'
import { Field, Input, Textarea } from '../../../components/common/FormField.jsx'
import { Alert } from '../../../components/common/Feedback.jsx'
import { useToast } from '../../../components/common/ToastProvider.jsx'
import {
  INVALID_QUALITY_FLAGS,
  QUALITY_FLAG_LABELS,
  QUALITY_FLAG_TONE
} from '../../../constants/index.js'
import { formatDateTime, formatNumber } from '../../../utils/format.js'

const FLAG_CHOICES = [
  { value: 'outlier', label: '离群值', hint: '读数明显偏离正常范围, 标为无效, 不计入达标率与排名' },
  { value: 'instrument', label: '仪器异常', hint: '分析仪故障 / 校准期等原因, 标为无效, 不计入达标率与排名' },
  { value: 'corrected', label: '人工修正', hint: '读数有误但可订正, 需填写修正后的值, 修正后仍为有效数据' }
]

export default function QualityFlagModal({ measurement, onClose, onSaved }) {
  const toast = useToast()
  const [form, setForm] = useState({
    quality_flag: 'outlier',
    reason: '',
    marked_by: '',
    corrected_value: ''
  })
  const [errors, setErrors] = useState({})
  const [message, setMessage] = useState(null)
  const [busy, setBusy] = useState(false)
  const [confirmClear, setConfirmClear] = useState(false)

  useEffect(() => {
    if (!measurement) return
    setForm({
      quality_flag: measurement.quality_flag || 'outlier',
      reason: '',
      marked_by: measurement.quality_marked_by || '',
      corrected_value:
        measurement.quality_flag === 'corrected' ? String(measurement.value ?? '') : ''
    })
    setErrors({})
    setMessage(null)
    setConfirmClear(false)
  }, [measurement])

  if (!measurement) return null

  const isInvalidFlag = INVALID_QUALITY_FLAGS.includes(measurement.quality_flag)
  const needsCorrectedValue = form.quality_flag === 'corrected'

  const submit = async () => {
    setBusy(true)
    setMessage(null)
    try {
      const payload = {
        quality_flag: form.quality_flag,
        reason: form.reason,
        marked_by: form.marked_by || null
      }
      if (form.quality_flag === 'corrected') {
        payload.corrected_value = form.corrected_value === '' ? null : Number(form.corrected_value)
      }
      await flagMeasurement(measurement.id, payload)
      toast.success('数据质量标记已保存')
      onSaved?.()
    } catch (err) {
      setErrors(err.fields || {})
      setMessage(err.message)
    } finally {
      setBusy(false)
    }
  }

  const submitClear = async () => {
    if (!confirmClear) {
      setConfirmClear(true)
      return
    }
    setBusy(true)
    setMessage(null)
    try {
      await clearMeasurementFlag(measurement.id, {
        reason: form.reason,
        marked_by: form.marked_by || null
      })
      toast.success('质量标记已撤销')
      onSaved?.()
    } catch (err) {
      setErrors(err.fields || {})
      setMessage(err.message)
    } finally {
      setBusy(false)
      setConfirmClear(false)
    }
  }

  return (
    <Modal
      open={Boolean(measurement)}
      wide
      title="数据质量标记"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose} disabled={busy}>
            关闭
          </button>
          {measurement.quality_flag ? (
            <button type="button" className="btn btn-danger" onClick={submitClear} disabled={busy}>
              {busy ? '处理中...' : confirmClear ? '确认撤销标记' : '撤销标记'}
            </button>
          ) : null}
          <button type="button" className="btn btn-primary" onClick={submit} disabled={busy}>
            {busy ? '保存中...' : '保存标记'}
          </button>
        </>
      }
    >
      <div className="stack">
        <dl className="kv">
          <dt>监测点</dt>
          <dd>
            {measurement.station?.name || '-'} <span className="mono muted">{measurement.station?.code}</span>
          </dd>
          <dt>监测时间</dt>
          <dd>
            {formatDateTime(measurement.measured_at)} · {measurement.period_label}
          </dd>
          <dt>监测因子</dt>
          <dd>{measurement.pollutant_label}</dd>
          <dt>当前读数</dt>
          <dd>
            <span className={measurement.is_exceeded ? 'danger-text strong' : 'strong'}>
              {formatNumber(measurement.value)}
            </span>{' '}
            <span className="muted small">{measurement.unit}</span>
            {measurement.quality_flag === 'corrected' && measurement.original_value !== null ? (
              <span className="muted small"> (原始值: {formatNumber(measurement.original_value)})</span>
            ) : null}
          </dd>
        </dl>

        {measurement.quality_flag ? (
          <Alert tone={isInvalidFlag ? 'warning' : 'info'}>
            当前标记:
            <Tag tone={QUALITY_FLAG_TONE[measurement.quality_flag]}>
              {measurement.quality_flag_label}
            </Tag>
            {isInvalidFlag ? ' · 该读数不参与达标率与排名, 但仍可在明细中查询' : ' · 修正后数据仍为有效数据'}
            <div className="small muted" style={{ marginTop: 4 }}>
              {measurement.quality_reason} —— {measurement.quality_marked_by || '未署名'} ·{' '}
              {formatDateTime(measurement.quality_marked_at)}
            </div>
          </Alert>
        ) : (
          <Alert tone="info">该读数暂无质量标记, 可选择标记类型并填写原因。</Alert>
        )}

        {message ? <Alert tone="error">{message}</Alert> : null}
        {confirmClear ? (
          <Alert tone="warning">
            请确认撤销该质量标记: 请在下方填写撤销原因与操作人, 然后再次点击“确认撤销标记”。
            {measurement.quality_flag === 'corrected'
              ? ' 当前修正值仍作为正式读数保留, 原始值留痕保留。'
              : ' 撤销后该读数将重新计入达标率与排名。'}
          </Alert>
        ) : null}

        <Field label="标记类型" required error={errors.quality_flag}>
          <div className="stack">
            {FLAG_CHOICES.map((choice) => (
              <label key={choice.value} className="checkbox" style={{ alignItems: 'flex-start' }}>
                <input
                  type="radio"
                  name="quality-flag"
                  checked={form.quality_flag === choice.value}
                  onChange={() => setForm({ ...form, quality_flag: choice.value })}
                />
                <span>
                  <span className="strong">
                    {choice.label}
                    {INVALID_QUALITY_FLAGS.includes(choice.value) ? (
                      <Tag tone={QUALITY_FLAG_TONE[choice.value]}>无效</Tag>
                    ) : (
                      <Tag tone="success">有效</Tag>
                    )}
                  </span>
                  <span className="small muted" style={{ display: 'block' }}>
                    {choice.hint}
                  </span>
                </span>
              </label>
            ))}
          </div>
        </Field>

        {needsCorrectedValue ? (
          <Field label="修正后监测值" required error={errors.corrected_value}>
            <Input
              type="number"
              step="0.01"
              value={form.corrected_value}
              onChange={(event) => setForm({ ...form, corrected_value: event.target.value })}
              placeholder="输入复核后的正确读数, 将重新判定超标"
            />
          </Field>
        ) : null}

        <Field
          label="标记原因 / 撤销原因"
          required
          error={errors.reason}
          hint={
            measurement.quality_flag
              ? '填写撤销原因后点击“撤销标记”; 修改标记则填写新原因后点击“保存标记”'
              : undefined
          }
        >
          <Textarea
            value={form.reason}
            onChange={(event) => setForm({ ...form, reason: event.target.value })}
            invalid={Boolean(errors.reason)}
            placeholder={
              measurement.quality_flag
                ? '如: 经复测数据正常, 撤销离群值标记'
                : '如: 该时段数据与相邻时段偏差超过 5 倍, 判定为离群值'
            }
          />
        </Field>

        <Field label="标记人" error={errors.marked_by}>
          <Input
            value={form.marked_by}
            onChange={(event) => setForm({ ...form, marked_by: event.target.value })}
            placeholder="如: 王敏 (留空记为未署名)"
          />
        </Field>

        <div className="small muted">
          标记类型、原因、标记人、标记时间均会写入留痕, 可在“数据质量留痕”中追溯;
          标记为 <b>{QUALITY_FLAG_LABELS.outlier}</b> / <b>{QUALITY_FLAG_LABELS.instrument}</b>{' '}
          的数据不计入达标率与排名。
        </div>
      </div>
    </Modal>
  )
}
