import { useCallback, useState } from 'react'
import { Link } from 'react-router-dom'
import { overview } from '../../api/meta.js'
import BarChart from '../../components/common/BarChart.jsx'
import { SectionCard } from '../../components/common/Card.jsx'
import DataTable from '../../components/common/DataTable.jsx'
import { Alert, ErrorState, Loading } from '../../components/common/Feedback.jsx'
import StatCard from '../../components/common/StatCard.jsx'
import Tag from '../../components/common/Tag.jsx'
import {
  EXCEEDANCE_LEVEL_TONE,
  QUALITY_FLAG_ACTION_LABELS,
  QUALITY_FLAG_TONE
} from '../../constants/index.js'
import { useAsyncData } from '../../hooks/useAsyncData.js'
import { formatDateTime, formatNumber, formatPercent, formatRatio } from '../../utils/format.js'
import QualityFlagHistoryModal from '../measurements/components/QualityFlagHistoryModal.jsx'

export default function OverviewPage() {
  const loader = useCallback(() => overview(), [])
  const { data, loading, error, reload } = useAsyncData(loader)
  const [historyTargetId, setHistoryTargetId] = useState(null)

  if (loading && !data) return <Loading text="正在加载运行概览..." />
  if (error && !data) return <ErrorState error={error} onRetry={reload} />
  if (!data) return null

  const {
    stations,
    measurements,
    exceedances,
    trend,
    pending_exceedances: pending,
    compliance_ranking: ranking,
    recent_quality_flags: recentFlags
  } = data

  const pendingColumns = [
    { key: 'measured_at', title: '监测时间', className: 'cell-nowrap', render: (row) => formatDateTime(row.measured_at) },
    { key: 'station_name', title: '监测点', render: (row) => row.station_name },
    { key: 'pollutant_label', title: '因子' },
    {
      key: 'value',
      title: '监测值 / 限值',
      render: (row) => `${formatNumber(row.value)} / ${formatNumber(row.limit_value)}`
    },
    { key: 'exceed_ratio', title: '超标倍数', render: (row) => formatRatio(row.exceed_ratio) },
    {
      key: 'level',
      title: '等级',
      render: (row) => <Tag tone={EXCEEDANCE_LEVEL_TONE[row.level]}>{row.level_label}</Tag>
    }
  ]

  const typeRows = (stations.by_type || []).map((item) => ({
    id: item.key,
    label: item.label,
    count: item.count,
    ratio: stations.total ? item.count / stations.total : 0
  }))

  const rankingColumns = [
    {
      key: 'rank',
      title: '排名',
      className: 'cell-nowrap',
      render: (row) => (
        <span className={row.rank <= 3 ? 'strong' : 'muted'}>
          {row.rank === 1 ? '🥇' : row.rank === 2 ? '🥈' : row.rank === 3 ? '🥉' : `#${row.rank}`}
        </span>
      )
    },
    { key: 'station_name', title: '监测点', render: (row) => (
      <div>
        <div>{row.station_name}</div>
        <div className="small muted mono">{row.station_code} · {row.area}</div>
      </div>
    ) },
    {
      key: 'compliance_rate',
      title: '达标率',
      align: 'right',
      className: 'cell-nowrap',
      render: (row) => (
        <span className={row.compliance_rate >= 0.95 ? 'strong' : 'danger-text strong'}>
          {formatPercent(row.compliance_rate)}
        </span>
      )
    },
    { key: 'valid_count', title: '有效数据', align: 'right', render: (row) => row.valid_count },
    {
      key: 'exceeded_count',
      title: '超标',
      align: 'right',
      render: (row) => (row.exceeded_count ? <span className="danger-text">{row.exceeded_count}</span> : 0)
    }
  ]

  const flagColumns = [
    { key: 'marked_at', title: '时间', className: 'cell-nowrap', render: (row) => formatDateTime(row.marked_at) },
    { key: 'station_name', title: '监测点', render: (row) => (
      <div>
        <div>{row.station_name}</div>
        <div className="small muted mono">{row.station_code}</div>
      </div>
    ) },
    { key: 'pollutant_label', title: '因子', render: (row) => row.pollutant_label },
    {
      key: 'quality_flag',
      title: '操作',
      render: (row) => (
        <Tag tone={row.action === 'clear' ? 'neutral' : QUALITY_FLAG_TONE[row.quality_flag]}>
          {QUALITY_FLAG_ACTION_LABELS[row.action] || row.action}
          {row.quality_flag_label ? ` · ${row.quality_flag_label}` : ''}
        </Tag>
      )
    },
    { key: 'reason', title: '原因', render: (row) => <span className="small">{row.reason}</span> },
    { key: 'marked_by', title: '标记人', className: 'cell-nowrap', render: (row) => row.marked_by },
    {
      key: 'actions',
      title: '',
      render: (row) => (
        <button type="button" className="btn btn-sm" onClick={() => setHistoryTargetId(row.measurement_id)}>
          留痕
        </button>
      )
    }
  ]

  return (
    <>
      <div className="stat-grid">
        <StatCard
          label="监测点总数"
          value={stations.total}
          foot={(stations.by_status || [])
            .map((item) => `${item.label} ${item.count}`)
            .join(' · ')}
        />
        <StatCard
          label="监测数据总量"
          value={measurements.total}
          foot={`有效 ${measurements.valid_total} 条 · 无效剔除 ${measurements.invalid_count} 条 · 均值 ${formatNumber(measurements.avg_value)}`}
        />
        <StatCard
          label="超标记录"
          value={exceedances.total}
          tone={exceedances.total ? 'danger' : undefined}
          foot={`有效口径超标率 ${formatPercent(measurements.exceed_rate)} · 达标率 ${formatPercent(measurements.compliance_rate)}`}
        />
        <StatCard
          label="待标注超标"
          value={exceedances.pending}
          tone={exceedances.pending ? 'warning' : undefined}
          foot={
            <Link to="/exceedances">前往标注工作台 →</Link>
          }
        />
      </div>

      <div className="grid-2">
        <SectionCard title="近 7 日数据量趋势" hint="按日统计录入条数, 红色代表当日存在超标">
          <BarChart items={trend.items || []} precision={0} danger={false} />
        </SectionCard>

        <SectionCard title="监测点类型分布" hint="台账中各类站点的数量占比">
          <div className="stack">
            {typeRows.map((row) => (
              <div key={row.id}>
                <div className="inline" style={{ justifyContent: 'space-between' }}>
                  <span>{row.label}</span>
                  <span className="muted small">
                    {row.count} 个 · {formatPercent(row.ratio)}
                  </span>
                </div>
                <div className="meter" style={{ marginTop: 6 }}>
                  <div className="meter-fill" style={{ width: `${Math.max(row.ratio * 100, 2)}%` }} />
                </div>
              </div>
            ))}
            <div className="inline">
              <Link className="btn btn-sm" to="/stations">
                管理监测点台账
              </Link>
              <Link className="btn btn-sm" to="/measurements">
                录入监测数据
              </Link>
            </div>
          </div>
        </SectionCard>
      </div>

      <SectionCard
        title="待标注超标记录 (最近 5 条)"
        hint="按监测时间倒序, 点击“超标记录标注”模块可批量处理"
        actions={
          <Link className="btn btn-sm btn-primary" to="/exceedances">
            处理超标标注
          </Link>
        }
      >
        {exceedances.pending === 0 ? (
          <Alert tone="success">当前没有待标注的超标记录, 数据复核已完成 ✅</Alert>
        ) : (
          <DataTable
            columns={pendingColumns}
            rows={pending}
            loading={loading}
            emptyText="暂无待标注记录"
            emptyIcon="✅"
          />
        )}
      </SectionCard>

      <div className="grid-2">
        <SectionCard
          title="监测点达标率排名 (Top 5)"
          hint="仅统计有效读数; 被标为离群值 / 仪器异常的数据不参与排名"
          actions={<Link className="btn btn-sm" to="/query">前往数据查询 →</Link>}
        >
          {ranking && ranking.length ? (
            <DataTable columns={rankingColumns} rows={ranking} />
          ) : (
            <Alert tone="neutral">暂无可参与排名的有效数据</Alert>
          )}
        </SectionCard>

        <SectionCard
          title="最近数据质量标记"
          hint="离群值 / 仪器异常 / 人工修正的操作留痕"
        >
          {recentFlags && recentFlags.length ? (
            <DataTable columns={flagColumns} rows={recentFlags} />
          ) : (
            <Alert tone="success">暂无数据质量标记 ✅</Alert>
          )}
        </SectionCard>
      </div>

      <QualityFlagHistoryModal
        measurementId={historyTargetId}
        onClose={() => setHistoryTargetId(null)}
      />
    </>
  )
}
