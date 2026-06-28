import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { PageHeader } from '../../../shared/components/PageHeader'
import { SectionCard } from '../../../shared/components/SectionCard'
import { useDocumentTitle } from '../../../shared/hooks/useDocumentTitle'
import { BatchControls } from '../components/BatchControls'
import { BatchInputPanel } from '../components/BatchInputPanel'
import { BatchPlanPreview } from '../components/BatchPlanPreview'
import { BatchSummaryCards } from '../components/BatchSummaryCards'
import { BatchTable } from '../components/BatchTable'
import { BatchTimeline } from '../components/BatchTimeline'

type BatchTab = 'create' | 'queue' | 'detail'

const defaultIdeas = [
  '上班前五分钟给自己松绑',
  '雨天路边的一杯热饮',
  '夜里窗边慢慢呼吸',
].join('\n')

export function BatchQueuePage() {
  useDocumentTitle('批量队列')
  const params = useParams()
  const [tab, setTab] = useState<BatchTab>(params.batchId ? 'detail' : 'create')
  const [ideasText, setIdeasText] = useState(defaultIdeas)
  const batchId = params.batchId ?? 'batch_demo_001'

  return (
    <div className="stack">
      <PageHeader
        title="批量队列"
        description="批量创建、监控、暂停、恢复、重试和进入 recovery plan。"
        kicker="Checkpoint 05"
      />
      <div className="button-row">
        {[
          ['create', 'Create Batch'],
          ['queue', 'Queue'],
          ['detail', 'Detail'],
        ].map(([key, label]) => (
          <button
            className={tab === key ? 'hero-button' : 'ghost-button'}
            key={key}
            type="button"
            onClick={() => setTab(key as BatchTab)}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === 'create' ? (
        <div className="grid-two">
          <BatchInputPanel
            ideasText={ideasText}
            onIdeasTextChange={setIdeasText}
          />
          <BatchPlanPreview ideasText={ideasText} />
        </div>
      ) : null}
      {tab === 'queue' ? (
        <SectionCard title="Queue" description="批量列表与汇总。">
          <div className="stack">
            <BatchSummaryCards />
            <BatchTable />
          </div>
        </SectionCard>
      ) : null}
      {tab === 'detail' ? (
        <SectionCard
          title="Batch Detail"
          description="按 run 展示时间线、推荐动作和控制。"
        >
          <div className="stack">
            <BatchControls batchId={batchId} />
            <BatchTimeline />
          </div>
        </SectionCard>
      ) : null}
    </div>
  )
}

export function BatchDetailPage() {
  return <BatchQueuePage />
}
