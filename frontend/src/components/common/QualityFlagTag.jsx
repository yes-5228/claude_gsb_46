import Tag from './Tag.jsx'
import { QUALITY_FLAG_LABELS, QUALITY_FLAG_TONE } from '../../constants/index.js'

/** 数据质量标记徽标; 离群值 / 仪器异常 额外提示该读数不计入达标率与排名. */
export default function QualityFlagTag({ flag, label, invalid }) {
  if (!flag) return <span className="muted">-</span>
  const title = invalid ? '该读数已被判为无效, 不计入达标率与排名' : undefined
  return (
    <Tag tone={QUALITY_FLAG_TONE[flag] || 'neutral'} title={title}>
      {label || QUALITY_FLAG_LABELS[flag] || flag}
    </Tag>
  )
}
