import { SectionCard } from '../../../components/common/Card.jsx'
import { Alert, EmptyState, Loading } from '../../../components/common/Feedback.jsx'
import BarChart from '../../../components/common/BarChart.jsx'
import { Field, Select } from '../../../components/common/FormField.jsx'
import { formatNumber, formatPercent } from '../../../utils/format.js'

const GROUP_OPTIONS = [
  { value: 'pollutant', label: '按监测因子' },
  { value: 'station', label: '按监测点 (达标率排名)' },
  { value: 'area', label: '按区域' },
  { value: 'day', label: '按日' },
  { value: 'month', label: '按月' },
  { value: 'period', label: '按数据周期' },
  { value: 'data_source', label: '按数据来源' }
]

const METRIC_OPTIONS = [
  { value: 'avg', label: '平均值' },
  { value: 'max', label: '最大值' },
  { value: 'min', label: '最小值' },
  { value: 'count', label: '数据条数' },
  { value: 'sum', label: '合计' }
]

export default function StatisticsPanel({ params, onChange, data, loading, error, onRun }) {
  const items = data?.items ?? []
  const isCount = params.metric === 'count'
  const isStationRanking = params.group_by === 'station'

  return (
    <SectionCard
      title="聚合统计"
      hint="统计默认剔除离群值 / 仪器异常 的无效读数; 按监测点分组即为达标率排名"
      actions={
        <>
          <div style={{ width: 180 }}>
            <Select
              value={params.group_by}
              onChange={(event) => onChange({ ...params, group_by: event.target.value })}
              options={GROUP_OPTIONS}
            />
          </div>
          <div style={{ width: 140 }}>
            <Select
              value={params.metric}
              onChange={(event) => onChange({ ...params, metric: event.target.value })}
              options={METRIC_OPTIONS}
            />
          </div>
          <button type="button" className="btn btn-sm btn-primary" onClick={() => onRun()} disabled={loading}>
            {loading ? '统计中...' : '执行统计'}
          </button>
        </>
      }
    >
      <div className="stack">
        {data?.invalid_excluded ? (
          <Alert tone="info">
            当前为有效数据口径: 已剔除被标记为离群值 / 仪器异常的读数, 不计入达标率与排名。
          </Alert>
        ) : null}
        {error ? <Alert tone="error">{error.message}</Alert> : null}
        {loading && items.length === 0 ? <Loading text="正在统计..." /> : null}
        {!loading && items.length === 0 && !error ? (
          <EmptyState text="点击“执行统计”查看聚合结果" icon="📈" />
        ) : null}
        {items.length > 0 ? (
          <>
            <BarChart items={items} danger />
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    {isStationRanking ? <th>排名</th> : null}
                    <th>分组</th>
                    <th className="text-right">{isCount ? '数据条数' : '统计值'}</th>
                    <th className="text-right">有效数据量</th>
                    <th className="text-right">超标数</th>
                    <th className="text-right">超标率</th>
                    <th className="text-right">达标率</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item, index) => (
                    <tr key={item.key}>
                      {isStationRanking ? (
                        <td>
                          <span className={`rank-badge rank-${Math.min(index + 1, 3)}`}>{item.rank ?? index + 1}</span>
                        </td>
                      ) : null}
                      <td>{item.label}</td>
                      <td className="text-right strong">{formatNumber(item.value)}</td>
                      <td className="text-right">{item.count}</td>
                      <td className="text-right danger-text">{item.exceeded_count}</td>
                      <td className="text-right">{formatPercent(item.exceed_rate)}</td>
                      <td className="text-right strong">{formatPercent(item.compliance_rate)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : null}
      </div>
    </SectionCard>
  )
}
