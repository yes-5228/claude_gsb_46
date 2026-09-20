import DataTable from '../../../components/common/DataTable.jsx'
import Tag from '../../../components/common/Tag.jsx'
import QualityFlagTag from '../../../components/common/QualityFlagTag.jsx'
import { DATA_SOURCE_TONE, EXCEEDANCE_STATUS_TONE } from '../../../constants/index.js'
import { formatDateTime, formatNumber } from '../../../utils/format.js'

export default function QueryResultTable({ rows, loading, onMarkQuality }) {
  const columns = [
    { key: 'measured_at', title: '监测时间', className: 'cell-nowrap', render: (row) => formatDateTime(row.measured_at) },
    { key: 'station', title: '监测点', render: (row) => `${row.station?.code || ''} ${row.station?.name || ''}` },
    { key: 'station_area', title: '区域', render: (row) => row.station?.area || '-' },
    { key: 'pollutant_label', title: '因子', className: 'cell-nowrap' },
    { key: 'period_label', title: '周期', className: 'cell-nowrap' },
    {
      key: 'value',
      title: '监测值',
      align: 'right',
      render: (row) => (
        <span className={row.is_exceeded ? 'danger-text strong' : ''}>
          {formatNumber(row.value)} <span className="muted small">{row.unit}</span>
          {row.original_value !== null && row.original_value !== undefined ? (
            <div className="small muted">原值 {formatNumber(row.original_value)}</div>
          ) : null}
        </span>
      )
    },
    { key: 'limit_value', title: '限值', align: 'right', render: (row) => (row.limit_value === null ? '无限值' : formatNumber(row.limit_value)) },
    {
      key: 'is_exceeded',
      title: '超标',
      render: (row) => (row.is_exceeded ? <Tag tone="danger">是</Tag> : <Tag tone="success">否</Tag>)
    },
    {
      key: 'exceedance_status',
      title: '标注状态',
      render: (row) =>
        row.exceedance_status ? (
          <Tag tone={EXCEEDANCE_STATUS_TONE[row.exceedance_status]}>
            {row.exceedance_status === 'pending' ? '待标注' : row.exceedance_status === 'confirmed' ? '已确认' : '已忽略'}
          </Tag>
        ) : (
          <span className="muted">-</span>
        )
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
    { key: 'recorder', title: '录入人', render: (row) => row.recorder || '-' },
    {
      key: 'actions',
      title: '操作',
      align: 'right',
      render: (row) => (
        <button type="button" className="btn btn-sm" onClick={() => onMarkQuality?.(row)}>
          质量标记
        </button>
      )
    }
  ]

  return (
    <DataTable
      columns={columns}
      rows={rows}
      loading={loading}
      emptyText="没有符合条件的数据, 请调整筛选条件"
      emptyIcon="🔍"
      rowClassName={(row) => (row.is_quality_invalid ? 'row-invalid' : '')}
    />
  )
}
