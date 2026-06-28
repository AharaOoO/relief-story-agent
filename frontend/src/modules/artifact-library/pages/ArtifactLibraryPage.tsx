import { useState } from 'react'
import { PageHeader } from '../../../shared/components/PageHeader'
import { SectionCard } from '../../../shared/components/SectionCard'
import { useDocumentTitle } from '../../../shared/hooks/useDocumentTitle'
import { ArtifactDetailDrawer } from '../components/ArtifactDetailDrawer'
import { ArtifactFilterBar } from '../components/ArtifactFilterBar'
import { ArtifactList } from '../components/ArtifactList'
import { ExportPanel } from '../components/ExportPanel'
import { ExportValidationPanel } from '../components/ExportValidationPanel'
import { VideoPreview } from '../components/VideoPreview'

export function ArtifactLibraryPage() {
  useDocumentTitle('产物库')
  const [scope, setScope] = useState<'run' | 'batch'>('batch')
  const [targetId, setTargetId] = useState('batch_demo_001')
  const [kind, setKind] = useState('all')

  return (
    <div className="stack">
      <PageHeader
        title="产物库"
        description="查看 run/batch 产物、视频、导出包和校验报告；浏览器不能读本地路径时提供复制。"
        kicker="Checkpoint 06"
      />
      <ArtifactFilterBar
        scope={scope}
        targetId={targetId}
        kind={kind}
        onScopeChange={setScope}
        onTargetIdChange={setTargetId}
        onKindChange={setKind}
      />
      <div className="grid-two">
        <div className="stack">
          <SectionCard
            title="Artifacts"
            description="路径、大小、存在性和复制操作。"
          >
            <ArtifactList scope={scope} targetId={targetId} kind={kind} />
          </SectionCard>
          <ExportValidationPanel />
        </div>
        <div className="stack">
          <VideoPreview />
          <ExportPanel scope={scope} targetId={targetId} />
          <ArtifactDetailDrawer />
        </div>
      </div>
    </div>
  )
}
