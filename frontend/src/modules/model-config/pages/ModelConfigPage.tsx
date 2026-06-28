import { useQuery } from '@tanstack/react-query'
import { PageHeader } from '../../../shared/components/PageHeader'
import { SectionCard } from '../../../shared/components/SectionCard'
import { useDocumentTitle } from '../../../shared/hooks/useDocumentTitle'
import { fetchModelProfiles } from '../api/modelConfig.api'
import { MissingKeyHint } from '../components/MissingKeyHint'
import { ModelCheckPanel } from '../components/ModelCheckPanel'
import { ModelProfileTable } from '../components/ModelProfileTable'
import { PromptTemplatePanel } from '../components/PromptTemplatePanel'
import { StageBindingPanel } from '../components/StageBindingPanel'

export function ModelConfigPage() {
  useDocumentTitle('模型配置')
  const profiles = useQuery({
    queryKey: ['model-profiles'],
    queryFn: fetchModelProfiles,
  })

  return (
    <div className="stack">
      <PageHeader
        title="模型配置"
        description="先确认 API key 环境变量、提示词模板路径、阶段模型绑定和真实探针状态。这里不保存、不显示明文 key。"
        kicker="Checkpoint 02"
      />
      <div className="grid-two">
        <div className="stack">
          <MissingKeyHint />
          <SectionCard
            title="Model Profiles"
            description="后端在线时读取 /api/config/models；离线时保留结构预览。"
          >
            <ModelProfileTable profiles={profiles.data?.profiles} />
          </SectionCard>
          <StageBindingPanel />
        </div>
        <div className="stack">
          <PromptTemplatePanel />
          <ModelCheckPanel />
        </div>
      </div>
    </div>
  )
}
