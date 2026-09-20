import DataTable from '../../../components/common/DataTable.jsx'
import Tag from '../../../components/common/Tag.jsx'
import QualityFlagTag from '../../../components/common/QualityFlagTag.jsx'
import { DATA_SOURCE_TONE } from '../../../constants/index.js'
import { formatDateTime, formatNumber, formatRatio } from '../../../utils/format.js'

export default function MeasurementTable({ rows, loading, onDelete, onMarkQuality }) {
  const columns = [
    { key: 'measured_at', title: '监测时间', className: 'cell-nowrap', render: (row) => formatDateTime(row.measured_at) },
    {
      key: 'station',
      title: '监测点',
      render: (row) => (
        <div>
          <div>{row.station?.name || '-'}</div>
          <div className="small muted mono">{row.station?.code || ''}</div>
        </div>
      )
    },
    { key: 'pollutant_label', title: '监测因子', className: 'cell-nowrap' },
    { key: 'period_label', title: '周期', className: 'cell-nowrap' },
    {
      key: 'value',
      title: '监测值',
      align: 'right',
      className: 'cell-nowrap',
      render: (row) => (
        <span className={row.is_exceeded ? 'danger-text strong' : ''}>
          {formatNumber(row.value)} <span className="muted small">{row.unit}</span>
          {row.original_value !== null && row.original_value !== undefined ? (
            <div className="small muted">原值 {formatNumber(row.original_value)}</div>
          ) : null}
        </span>
      )
    },
    {
      key: 'limit_value',
      title: '限值',
      align: 'right',
      render: (row) => (row.limit_value === null ? <span className="muted small">无限值</span> : formatNumber(row.limit_value))
    },
    {
      key: 'is_exceeded',
      title: '超标判定',
      render: (row) =>
        row.is_exceeded ? <Tag tone="danger">{formatRatio(row.exceed_ratio)}</Tag> : <Tag tone="success">达标</Tag>
    },
    {
      key: 'quality_flag',
      title: '质量标记',
      render: (row) => (
        <QualityFlagTag flag={row.quality_flag} label={row.quality_flag_label} invalid={row.is_quality_invalid} />
      )
    },
    {
      key: 'data_source_label',
      title: '来源',
      render: (row) => <Tag tone={DATA_SOURCE_TONE[row.data_source]}>{row.data_source_label}</Tag>
    },
    {
      key: 'quality_marked_by',
      title: '标记人 / 原因',
      render: (row) =>
        row.quality_flag ? (
          <div>
            <div className="small">{row.quality_marked_by || '未署名'}</div>
            <div className="small muted" title={row.quality_reason}>
              {row.quality_reason ? (row.quality_reason.length > 14 ? `${row.quality_reason.slice(0, 14)}…` : row.quality_reason) : ''}
            </div>
          </div>
        ) : (
          <span className="muted">-</span>
        )
    },
    { key: 'recorder', title: '录入人', render: (row) => row.recorder || '-' },
    {
      key: 'actions',
      title: '操作',
      align: 'right',
      className: 'cell-nowrap',
      render: (row) => (
        <>
          <button type="button" className="btn btn-sm" onClick={() => onMarkQuality(row)}>
            质量标记
          </button>
          <button type="button" className="btn btn-sm btn-danger" onClick={() => onDelete(row)}>
            删除
          </button>
        </>
      )
    }
  ]

  return (
    <DataTable
      columns={columns}
      rows={rows}
      loading={loading}
      emptyText="暂无监测数据, 请先在上方录入"
      emptyIcon="✍️"
      rowClassName={(row) => (row.is_quality_invalid ? 'row-invalid' : '')}
    />
  )
}
