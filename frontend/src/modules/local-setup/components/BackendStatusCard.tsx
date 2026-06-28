import { Button } from '@heroui/react'
import { RefreshCcw } from 'lucide-react'
import { SectionCard } from '../../../shared/components/SectionCard'
import { StatusBadge } from '../../../shared/components/StatusBadge'
import { useBackendHealth } from '../../../shared/hooks/useBackendHealth'
import { useUiStore } from '../../../shared/store/uiStore'
import { normalizeEndpointLabel } from '../../../shared/utils/normalizeEndpointLabel'

export function BackendStatusCard() {
  const health = useBackendHealth()
  const apiBaseUrl = useUiStore((state) => state.apiBaseUrl)

  return (
    <SectionCard
      title="后端连接"
      description="读取 /api/health，后端离线时 UI 保持可读。"
      action={
        <Button className="ghost-button" onPress={() => health.refetch()}>
          <RefreshCcw size={16} />
          刷新
        </Button>
      }
    >
      <div className="metric-grid">
        <div className="metric metric--wide metric--code">
          <span>API 地址</span>
          <strong>{normalizeEndpointLabel(apiBaseUrl)}</strong>
        </div>
        <div className="metric">
          <span>状态</span>
          <strong>
            <StatusBadge status={health.isSuccess ? 'ready' : 'blocked'} />
          </strong>
        </div>
        <div className="metric">
          <span>版本</span>
          <strong>{health.data?.version ?? '未读取'}</strong>
        </div>
      </div>
    </SectionCard>
  )
}
