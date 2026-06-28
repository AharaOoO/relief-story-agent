import { SectionCard } from '../../../shared/components/SectionCard'
import { JsonViewer } from '../../../shared/components/JsonViewer'

export function ArtifactDetailDrawer() {
  return (
    <SectionCard title="Artifact Detail" description="默认折叠 JSON，用于诊断而不是普通阅读。">
      <JsonViewer
        value={{
          artifact_id: 'artifact_video_001',
          exists: true,
          sha256: 'redacted-demo-sha256',
          publish_ready: false,
          note: 'validation failed 时不显示可发布',
        }}
      />
    </SectionCard>
  )
}
