import { Button } from '@heroui/react'
import { useMutation } from '@tanstack/react-query'
import { PackageCheck } from 'lucide-react'
import { useState } from 'react'
import { buildSetupBundleRequest } from '../../../shared/api/backendPayloads'
import { CopyButton } from '../../../shared/components/CopyButton'
import { ErrorState } from '../../../shared/components/ErrorState'
import { JsonViewer } from '../../../shared/components/JsonViewer'
import { SectionCard } from '../../../shared/components/SectionCard'
import { useUiStore } from '../../../shared/store/uiStore'
import { writeSetupBundle } from '../api/localSetup.api'

const startCommand =
  'relief-story-agent serve --host 127.0.0.1 --port 8891 --state-dir "D:/relief_story_state"'

export function SetupBundlePanel() {
  const endpoint = useUiStore((state) => state.recentComfyUIEndpoint)
  const workflowPath = useUiStore((state) => state.recentWorkflowPath)
  const [outputDir, setOutputDir] = useState('D:/relief_story_setup')
  const setupBundle = useMutation({
    mutationFn: () =>
      writeSetupBundle(
        buildSetupBundleRequest({
          outputDir,
          workflowPath,
          comfyuiEndpoint: endpoint,
        }),
      ),
  })

  return (
    <SectionCard
      title="Setup Bundle"
      description="生成本地配置包：写模型配置、示例请求和 templates/ 提示词模板；只写环境变量名，不写明文 key。"
      footer={
        <div className="button-row">
          <Button
            className="hero-button"
            isDisabled={
              !outputDir.trim() || !workflowPath.trim() || setupBundle.isPending
            }
            onPress={() => setupBundle.mutate()}
          >
            <PackageCheck size={16} />
            生成配置包
          </Button>
          <CopyButton value={startCommand} label="复制启动命令" />
        </div>
      }
    >
      <div className="form-grid">
        <div className="field">
          <label htmlFor="setup-output-dir">Setup Output Dir</label>
          <input
            id="setup-output-dir"
            value={outputDir}
            onChange={(event) => setOutputDir(event.target.value)}
          />
        </div>
      </div>
      <div className="metric-grid">
        <div className="metric">
          <span>模型 key</span>
          <strong>仅环境变量</strong>
        </div>
        <div className="metric">
          <span>提示词模板</span>
          <strong>{`${outputDir}/templates`}</strong>
        </div>
        <div className="metric">
          <span>默认状态目录</span>
          <strong>D:/relief_story_state</strong>
        </div>
      </div>
      {setupBundle.error ? (
        <ErrorState
          error={setupBundle.error}
          onRetry={() => setupBundle.mutate()}
        />
      ) : null}
      {setupBundle.data ? (
        <div className="alert-box" role="status">
          <h3>Setup bundle response</h3>
          <JsonViewer value={setupBundle.data} />
        </div>
      ) : null}
    </SectionCard>
  )
}
