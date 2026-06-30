import { useQuery } from '@tanstack/react-query'
import { PageHeader } from '../../../shared/components/PageHeader'
import { SectionCard } from '../../../shared/components/SectionCard'
import { useDocumentTitle } from '../../../shared/hooks/useDocumentTitle'
import { fetchModelProfiles } from '../api/modelConfig.api'
import { ApiKeyManager } from '../components/ApiKeyManager'
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
        description="请在此处输入您的 API Key。您的 Key 将被加密保存在本地设置中，后端启动时自动读取。"
        kicker="Checkpoint 02"
      />
      <div className="grid-two">
        <div className="stack">
          <ApiKeyManager />
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
