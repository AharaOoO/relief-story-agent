import { PageHeader } from '../../../shared/components/PageHeader'
import { useDocumentTitle } from '../../../shared/hooks/useDocumentTitle'
import { BackendStatusCard } from '../components/BackendStatusCard'
import { ComfyUIConnectionCard } from '../components/ComfyUIConnectionCard'
import { LaunchGuideCard } from '../components/LaunchGuideCard'
import { ReadinessPanel } from '../components/ReadinessPanel'
import { SetupBundlePanel } from '../components/SetupBundlePanel'
import { WorkflowDiscoveryPanel } from '../components/WorkflowDiscoveryPanel'

export function LocalSetupPage() {
  useDocumentTitle('本地环境检查')

  return (
    <div className="stack">
      <PageHeader
        title="本地环境检查"
        description="先确认打开入口、端口、API、readiness、ComfyUI 和本地证据状态，再允许进入真实模型运行。"
        kicker="Checkpoint 01"
      />
      <LaunchGuideCard />
      <div className="grid-two">
        <div className="stack">
          <BackendStatusCard />
          <ReadinessPanel />
        </div>
        <div className="stack">
          <ComfyUIConnectionCard />
          <WorkflowDiscoveryPanel />
          <SetupBundlePanel />
        </div>
      </div>
    </div>
  )
}
