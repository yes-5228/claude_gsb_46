import { useCallback, useEffect, useState } from 'react'
import { exportQueryUrl, queryMeasurements, queryStatistics } from '../../api/query.js'
import { downloadFile } from '../../api/client.js'
import Pagination from '../../components/common/Pagination.jsx'
import { SectionCard } from '../../components/common/Card.jsx'
import { Alert } from '../../components/common/Feedback.jsx'
import StatCard from '../../components/common/StatCard.jsx'
import { useToast } from '../../components/common/ToastProvider.jsx'
import { useAsyncData } from '../../hooks/useAsyncData.js'
import { useListQuery } from '../../hooks/useListQuery.js'
import { saveBlob } from '../../utils/download.js'
import { formatDateTime, formatNumber, formatPercent } from '../../utils/format.js'
import QueryFilters from './components/QueryFilters.jsx'
import QueryResultTable from './components/QueryResultTable.jsx'
import StatisticsPanel from './components/StatisticsPanel.jsx'
import QualityFlagHistoryModal from '../measurements/components/QualityFlagHistoryModal.jsx'
import QualityFlagModal from '../measurements/components/QualityFlagModal.jsx'

const INITIAL_FILTERS = {
  keyword: '',
  station_id: '',
  area: '',
  pollutant: '',
  period: '',
  is_exceeded: '',
  exceedance_status: '',
  data_source: '',
  quality_flag: '',
  is_invalid: '',
  date_from: '',
  date_to: '',
  min_value: '',
  max_value: ''
}

export default function QueryPage() {
  const toast = useToast()
  const query = useListQuery(queryMeasurements, INITIAL_FILTERS, { pageSize: 20 })
  const [statsParams, setStatsParams] = useState({ group_by: 'pollutant', metric: 'avg' })
  const [exporting, setExporting] = useState(false)
  const [flagTarget, setFlagTarget] = useState(null)
  const [historyTargetId, setHistoryTargetId] = useState(null)

  const statsLoader = useCallback(
    () => queryStatistics({ ...query.filters, ...statsParams }),
    [query.filters, statsParams]
  )
  const stats = useAsyncData(statsLoader, { immediate: false })

  const summary = query.summary

  // 筛选条件或统计维度变化时自动刷新统计, 便于即时比对
  useEffect(() => {
    stats.reload().catch(() => {})
  }, [stats.reload])

  const handleExport = async () => {
    setExporting(true)
    try {
      const blob = await downloadFile(exportQueryUrl({ ...query.filters, sort: 'measured_at', order: 'desc' }))
      saveBlob(blob, `监测数据查询结果_${Date.now()}.csv`)
      toast.success('导出任务已完成, 请查看下载文件')
    } catch (error) {
      toast.error(error.message)
    } finally {
      setExporting(false)
    }
  }

  return (
    <>
      <QueryFilters
        value={query.filters}
        loading={query.loading}
        onSubmit={(next) => query.setFilters(next)}
        onReset={() => query.setFilters(INITIAL_FILTERS)}
      />

      {query.error ? <Alert tone="error">{query.error.message}</Alert> : null}

      <div className="stat-grid">
        <StatCard
          label="符合条件的数据量"
          value={summary ? summary.total : '-'}
          foot={
            summary
              ? `有效 ${summary.valid_total} 条 · 无效剔除 ${summary.invalid_count} 条 · 涉及 ${summary.station_count} 个监测点`
              : ''
          }
        />
        <StatCard
          label="超标记录 (有效口径)"
          value={summary ? summary.exceeded_count : '-'}
          tone={summary?.exceeded_count ? 'danger' : undefined}
          foot={summary ? `超标率 ${formatPercent(summary.exceed_rate)} · 达标率 ${formatPercent(summary.compliance_rate)}` : ''}
        />
        <StatCard label="平均浓度 (有效口径)" value={summary ? formatNumber(summary.avg_value) : '-'} foot="无效读数已剔除" />
        <StatCard
          label="时间范围"
          value={summary ? formatDateTime(summary.first_measured_at).slice(5, 10) : '-'}
          unit={summary ? `~ ${formatDateTime(summary.last_measured_at).slice(5, 10)}` : ''}
          foot={summary ? `${formatDateTime(summary.first_measured_at)} ~ ${formatDateTime(summary.last_measured_at)}` : ''}
        />
      </div>

      <StatisticsPanel
        params={statsParams}
        onChange={(next) => setStatsParams(next)}
        data={stats.data}
        loading={stats.loading}
        error={stats.error}
        onRun={stats.reload}
      />

      <SectionCard
        title="查询结果"
        hint="按监测时间倒序, 单次导出最多 20000 行"
        actions={
          <>
            <button type="button" className="btn btn-sm" onClick={query.reload} disabled={query.loading}>
              刷新
            </button>
            <button type="button" className="btn btn-sm btn-primary" onClick={handleExport} disabled={exporting}>
              {exporting ? '导出中...' : '导出 CSV'}
            </button>
          </>
        }
      >
        <QueryResultTable
          rows={query.items}
          loading={query.loading}
          onFlag={(row) => setFlagTarget(row)}
          onHistory={(row) => setHistoryTargetId(row.id)}
        />
        <Pagination
          page={query.page}
          pages={query.pages}
          total={query.total}
          pageSize={query.pageSize}
          onPageChange={query.setPage}
          onPageSizeChange={query.setPageSize}
        />
      </SectionCard>

      <QualityFlagModal
        measurement={flagTarget}
        onClose={() => setFlagTarget(null)}
        onSaved={() => {
          setFlagTarget(null)
          query.reload()
          stats.reload().catch(() => {})
        }}
      />
      <QualityFlagHistoryModal
        measurementId={historyTargetId}
        onClose={() => setHistoryTargetId(null)}
      />
    </>
  )
}
