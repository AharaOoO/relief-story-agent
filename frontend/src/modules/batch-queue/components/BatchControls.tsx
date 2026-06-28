import { Button } from '@heroui/react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ConfirmDialog } from '../../../shared/components/ConfirmDialog'
import { ErrorState } from '../../../shared/components/ErrorState'
import { JsonViewer } from '../../../shared/components/JsonViewer'
import {
  cancelBatch,
  exportBatchArtifacts,
  pauseBatch,
  resumeBatch,
  retryBatch,
} from '../api/batches.api'

type BatchAction = 'pause' | 'resume' | 'cancel' | 'retry failed' | 'export artifacts'

const actionCopy: Record<BatchAction, string> = {
  pause: '暂停当前 batch。',
  resume: '恢复当前 batch。',
  cancel: '取消当前 batch。',
  'retry failed': '只重试后端认为可重试的失败项。',
  'export artifacts': '导出 batch 产物并生成 manifest/zip。',
}

export function BatchControls({ batchId }: { batchId: string }) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [targetBatchId, setTargetBatchId] = useState(batchId)
  const [action, setAction] = useState<BatchAction | null>(null)
  const mutation = useMutation({
    mutationFn: (nextAction: BatchAction) => {
      if (nextAction === 'pause') return pauseBatch(targetBatchId)
      if (nextAction === 'resume') return resumeBatch(targetBatchId)
      if (nextAction === 'cancel') return cancelBatch(targetBatchId)
      if (nextAction === 'retry failed') return retryBatch(targetBatchId)
      return exportBatchArtifacts(targetBatchId)
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['batches'] })
      void queryClient.invalidateQueries({
        queryKey: ['batch-timeline', targetBatchId],
      })
    },
  })
  const canAct = targetBatchId.trim().length > 0

  return (
    <>
      <div className="field">
        <label htmlFor="batch-control-id">Target Batch ID</label>
        <input
          id="batch-control-id"
          value={targetBatchId}
          onChange={(event) => setTargetBatchId(event.target.value)}
        />
      </div>
      <div className="button-row">
        {(['pause', 'resume', 'cancel', 'retry failed'] as BatchAction[]).map(
          (item) => (
            <Button
              className={item === 'cancel' ? 'danger-button' : 'secondary-button'}
              isDisabled={!canAct || mutation.isPending}
              key={item}
              onPress={() => setAction(item)}
            >
              {item}
            </Button>
          ),
        )}
        <Button
          className="secondary-button"
          isDisabled={!canAct}
          onPress={() => navigate(`/recovery/batch/${targetBatchId}`)}
        >
          view recovery plan
        </Button>
        <Button
          className="secondary-button"
          isDisabled={!canAct || mutation.isPending}
          onPress={() => setAction('export artifacts')}
        >
          export artifacts
        </Button>
      </div>
      {mutation.error ? <ErrorState error={mutation.error} /> : null}
      {mutation.data ? (
        <div className="alert-box" role="status">
          <h3>Batch action response</h3>
          <JsonViewer value={mutation.data} />
        </div>
      ) : null}
      <ConfirmDialog
        open={action !== null}
        title={`确认 ${action ?? ''}`}
        description={action ? actionCopy[action] : ''}
        variant={action === 'cancel' ? 'danger' : 'default'}
        onCancel={() => setAction(null)}
        onConfirm={() => {
          if (action) mutation.mutate(action)
          setAction(null)
        }}
      />
    </>
  )
}
