import { Button } from '@heroui/react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { PlugZap } from 'lucide-react'
import { ErrorState } from '../../../shared/components/ErrorState'
import { JsonViewer } from '../../../shared/components/JsonViewer'
import { SectionCard } from '../../../shared/components/SectionCard'
import { useUiStore } from '../../../shared/store/uiStore'
import { connectComfyUI } from '../api/localSetup.api'

export function ComfyUIConnectionCard() {
  const queryClient = useQueryClient()
  const endpoint = useUiStore((state) => state.recentComfyUIEndpoint)
  const workflowPath = useUiStore((state) => state.recentWorkflowPath)
  const setEndpoint = useUiStore((state) => state.setRecentComfyUIEndpoint)
  const setWorkflowPath = useUiStore((state) => state.setRecentWorkflowPath)
  const connection = useMutation({
    mutationFn: () =>
      connectComfyUI({
        endpoint,
        workflow_api_path: workflowPath,
        timeout_seconds: 5,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['local-readiness'] })
    },
  })

  return (
    <SectionCard
      title="ComfyUI 连接"
      description="只做连接和 workflow 契约检查，不上传、不入队。"
      action={
        <Button
          className="secondary-button"
          isDisabled={!endpoint.trim() || connection.isPending}
          onPress={() => connection.mutate()}
        >
          <PlugZap size={16} />
          检查连接
        </Button>
      }
    >
      <div className="form-grid">
        <div className="field">
          <label htmlFor="comfy-endpoint">ComfyUI Endpoint</label>
          <input
            id="comfy-endpoint"
            value={endpoint}
            onChange={(event) => setEndpoint(event.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="workflow-path">Workflow Path</label>
          <input
            id="workflow-path"
            value={workflowPath}
            onChange={(event) => setWorkflowPath(event.target.value)}
          />
        </div>
      </div>
      {connection.error ? (
        <ErrorState error={connection.error} onRetry={() => connection.mutate()} />
      ) : null}
      {connection.data ? (
        <div className="alert-box" role="status">
          <h3>ComfyUI response</h3>
          <JsonViewer value={connection.data} />
        </div>
      ) : null}
    </SectionCard>
  )
}
