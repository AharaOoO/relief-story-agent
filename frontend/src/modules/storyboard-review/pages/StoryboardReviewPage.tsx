import { useParams } from 'react-router-dom'
import { PageHeader } from '../../../shared/components/PageHeader'
import { SectionCard } from '../../../shared/components/SectionCard'
import { useDocumentTitle } from '../../../shared/hooks/useDocumentTitle'
import { FourGridPreview } from '../components/FourGridPreview'
import { PromptAuditPanel } from '../components/PromptAuditPanel'
import { RunActionPanel } from '../components/RunActionPanel'
import { RunEventsPanel } from '../components/RunEventsPanel'
import { RunHeader } from '../components/RunHeader'
import { StageTimeline } from '../components/StageTimeline'
import { StoryboardCardList } from '../components/StoryboardCardList'

export function StoryboardReviewPage() {
  useDocumentTitle('分镜审查')
  const params = useParams()
  const runId = params.runId ?? 'demo-run'

  return (
    <div className="stack">
      <PageHeader
        title="分镜审查"
        description="审查 storyboard、prompt audit、四宫格参考图和 run 事件，再决定 approve/retry/cancel。"
        kicker="Checkpoint 04"
      />
      <RunHeader runId={runId} />
      <div className="grid-two">
        <div className="stack">
          <SectionCard title="Pipeline Timeline" description="固定 stage 顺序，不在前端改名。">
            <StageTimeline />
          </SectionCard>
          <StoryboardCardList />
        </div>
        <div className="stack">
          <PromptAuditPanel />
          <FourGridPreview />
          <RunActionPanel runId={runId} />
          <RunEventsPanel />
        </div>
      </div>
    </div>
  )
}
