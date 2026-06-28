import { Button } from '@heroui/react'
import { useMutation } from '@tanstack/react-query'
import { Search } from 'lucide-react'
import { useState } from 'react'
import { buildWorkflowDiscoveryRequest } from '../../../shared/api/backendPayloads'
import { ErrorState } from '../../../shared/components/ErrorState'
import { JsonViewer } from '../../../shared/components/JsonViewer'
import { SectionCard } from '../../../shared/components/SectionCard'
import { StatusBadge } from '../../../shared/components/StatusBadge'
import { useUiStore } from '../../../shared/store/uiStore'
import { discoverWorkflows } from '../api/localSetup.api'

export function WorkflowDiscoveryPanel() {
  const endpoint = useUiStore((state) => state.recentComfyUIEndpoint)
  const [searchRootsText, setSearchRootsText] = useState('D:/ComfyUI/workflows')
  const discovery = useMutation({
    mutationFn: () =>
      discoverWorkflows(
        buildWorkflowDiscoveryRequest({
          endpoint,
          searchRootsText,
        }),
      ),
  })
  const workflows = discovery.data?.workflows ?? []

  return (
    <SectionCard
      title="Workflow Discovery"
      description="显示候选 workflow，但不改写原文件。"
      action={
        <Button
          className="secondary-button"
          isDisabled={!endpoint.trim() || discovery.isPending}
          onPress={() => discovery.mutate()}
        >
          <Search size={16} />
          发现
        </Button>
      }
    >
      <div className="field">
        <label htmlFor="workflow-roots">Search Roots</label>
        <textarea
          id="workflow-roots"
          value={searchRootsText}
          onChange={(event) => setSearchRootsText(event.target.value)}
        />
      </div>
      {discovery.error ? (
        <ErrorState error={discovery.error} onRetry={() => discovery.mutate()} />
      ) : null}
      {discovery.data ? (
        <div className="alert-box" role="status">
          <h3>Discovery response</h3>
          <JsonViewer value={discovery.data} />
        </div>
      ) : null}
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>路径</th>
              <th>格式</th>
              <th>检查</th>
            </tr>
          </thead>
          <tbody>
            {workflows.length > 0 ? (
              workflows.map((workflow) => (
                <tr key={workflow.path}>
                  <td>{workflow.path}</td>
                  <td>{workflow.kind ?? 'unknown'}</td>
                  <td>
                    <StatusBadge
                      status={
                        workflow.compatible ?? workflow.supported
                          ? 'ready'
                          : 'warning'
                      }
                    />
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={3}>运行发现后显示候选 workflow。</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </SectionCard>
  )
}
