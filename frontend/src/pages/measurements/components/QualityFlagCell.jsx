import Tag from '../../../components/common/Tag.jsx'
import {
  INVALID_QUALITY_FLAGS,
  QUALITY_FLAG_TONE
} from '../../../constants/index.js'
import { formatDateTime } from '../../../utils/format.js'

export default function QualityFlagCell({ row, onFlag, onHistory }) {
  if (!row.quality_flag) {
    return (
      <button type="button" className="btn btn-sm" onClick={() => onFlag(row)}>
        标记
      </button>
    )
  }

  const isInvalid = INVALID_QUALITY_FLAGS.includes(row.quality_flag) || row.is_invalid
  const title = [
    row.quality_reason,
    `标记人: ${row.quality_marked_by || '未署名'}`,
    row.quality_marked_at ? `标记时间: ${formatDateTime(row.quality_marked_at)}` : '',
    row.original_value !== null && row.original_value !== null ? `原始读数: ${row.original_value}` : ''
  ]
    .filter(Boolean)
    .join('\n')

  return (
    <div className="stack" style={{ gap: 4 }}>
      <Tag tone={QUALITY_FLAG_TONE[row.quality_flag]} title={title}>
        {row.quality_flag_label}
        {isInvalid ? '(无效)' : ''}
      </Tag>
      <div className="inline" style={{ gap: 4 }}>
        <button type="button" className="btn btn-sm" onClick={() => onFlag(row)}>
          改标记
        </button>
        <button type="button" className="btn btn-sm" onClick={() => onHistory(row)}>
          留痕
        </button>
      </div>
    </div>
  )
}
