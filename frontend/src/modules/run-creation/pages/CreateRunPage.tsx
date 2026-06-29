import { useMemo, useState } from 'react'
import { PageHeader } from '../../../shared/components/PageHeader'
import { SectionCard } from '../../../shared/components/SectionCard'
import { useDocumentTitle } from '../../../shared/hooks/useDocumentTitle'
import { useUiStore } from '../../../shared/store/uiStore'
import { CreateRunSubmitPanel } from '../components/CreateRunSubmitPanel'
import { GenerationModeSelector } from '../components/GenerationModeSelector'
import { PreflightPanel } from '../components/PreflightPanel'
import { RunRequestForm } from '../components/RunRequestForm'
import type { RunRequest } from '../contracts/run.contract'

export function CreateRunPage() {
  useDocumentTitle('创作任务')
  const mode = useUiStore((state) => state.selectedGenerationMode)
  const [request, setRequest] = useState<RunRequest>({
    idea: '',
    generation_mode: mode,
    approval_mode: 'manual',
    duration_seconds: 60,
    dry_run: true,
  })
  const mergedRequest = useMemo(
    () => ({ ...request, generation_mode: mode }),
    [mode, request],
  )

  return (
    <div className="stack">
      <PageHeader
        title="创作任务"
        description="输入低刺激情绪缓冲短片目标，先做 preflight，再交给后端创建 run。"
        kicker="Checkpoint 03"
      />
      <div className="grid-two">
        <div className="stack">
          <SectionCard title="Generation Mode" description="本地 / 云端入口统一。">
            <GenerationModeSelector />
          </SectionCard>
          <SectionCard title="Run Request" description="只构造 request payload，不执行 pipeline。">
            <RunRequestForm value={mergedRequest} onChange={setRequest} />
          </SectionCard>
        </div>
        <div className="stack">
          <PreflightPanel />
          <CreateRunSubmitPanel
            canSubmit={(mergedRequest.idea || '').trim().length > 0}
            request={mergedRequest}
          />
        </div>
      </div>
    </div>
  )
}
