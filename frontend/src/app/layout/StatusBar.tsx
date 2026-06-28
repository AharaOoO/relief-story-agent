import { Button } from '@heroui/react'
import { Activity, Play } from 'lucide-react'
import demoPoster from '../../assets/demo-poster.png'
import { StatusBadge } from '../../shared/components/StatusBadge'
import { useBackendHealth, useLocalReadiness } from '../../shared/hooks/useBackendHealth'
import { normalizeEndpointLabel } from '../../shared/utils/normalizeEndpointLabel'

export function StatusBar() {
  const health = useBackendHealth()
  const readiness = useLocalReadiness()
  const ready = readiness.data
  const backendLabel = health.isFetching
    ? '检查中'
    : health.isSuccess
      ? normalizeEndpointLabel(health.data?.version ?? 'online')
      : '离线'
  const readinessItems = [
    { label: '配置', active: ready?.ready_for_configuration },
    { label: '真实运行', active: ready?.ready_for_real_runs },
    { label: '发布', active: ready?.ready_for_release },
  ]
  const refreshStatus = () => {
    void health.refetch()
    void readiness.refetch()
  }

  return (
    <aside className="right-panel" aria-label="运行状态面板">
      <div className="run-panel__header">
        <span className="panel-kicker">Live Control</span>
        <h2 className="display-font">RUN PANEL</h2>
        <p>演示视频预留位和关键运行门禁固定在这里，后续可直接接入 demo 视频。</p>
      </div>
      <div className="video-slot">
        <img src={demoPoster} alt="演示视频预留封面" />
        <div className="video-slot__footer">
          <span>演示视频预留位</span>
          <span className="video-slot__tag">
            <Play size={15} />
            Demo
          </span>
        </div>
      </div>
      <div className="metric run-panel__metric">
        <span>Backend</span>
        <strong>{backendLabel}</strong>
      </div>
      <div className="readiness-stack" aria-label="readiness 状态">
        {readinessItems.map((item) => (
          <span className="readiness-item" key={item.label}>
            <span className={`readiness-dot${item.active ? ' is-on' : ''}`} />
            <span>{item.label}</span>
          </span>
        ))}
      </div>
      <div className="stack">
        <StatusBadge
          status={ready?.ready_for_real_runs ? 'ready' : 'blocked'}
          label={ready?.ready_for_real_runs ? '真实运行可用' : '真实运行阻塞'}
        />
        <StatusBadge
          status={ready?.ready_for_release ? 'ready' : 'warning'}
          label={ready?.ready_for_release ? '可发布' : '不可宣称发布就绪'}
        />
      </div>
      <Button className="hero-button run-panel__button" onPress={refreshStatus}>
        <Activity size={16} />
        刷新状态
      </Button>
    </aside>
  )
}
