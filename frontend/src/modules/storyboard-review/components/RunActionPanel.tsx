import { Button } from '@heroui/react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { ConfirmDialog } from '../../../shared/components/ConfirmDialog'
import { ErrorState } from '../../../shared/components/ErrorState'
import { JsonViewer } from '../../../shared/components/JsonViewer'
import { SectionCard } from '../../../shared/components/SectionCard'
import { approveRun, cancelRun, retryRun } from '../api/review.api'

type RunAction = 'approve' | 'retry' | 'cancel'

const actionCopy: Record<RunAction, { title: string; description: string }> = {
  approve: {
    title: '确认批准 prompts',
    description: '这会调用后端 approve mutation，让 run 继续进入后续阶段。',
  },
  retry: {
    title: '确认重试阶段',
    description: '这会调用后端 retry mutation，由后端决定可重试的阶段。',
  },
  cancel: {
    title: '确认取消 Run',
    description: '这会调用后端 cancel mutation，取消后不可由前端直接恢复。',
  },
}

export function RunActionPanel({ runId }: { runId: string }) {
  const queryClient = useQueryClient()
  const [action, setAction] = useState<RunAction | null>(null)
  const mutation = useMutation({
    mutationFn: (nextAction: RunAction) => {
      if (nextAction === 'approve') return approveRun(runId)
      if (nextAction === 'retry') return retryRun(runId)
      return cancelRun(runId)
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['run-events', runId] })
      void queryClient.invalidateQueries({ queryKey: ['run-timeline', runId] })
    },
  })
  const copy = action ? actionCopy[action] : null

  return (
    <SectionCard
      title="Run Actions"
      description="approve/retry/cancel 都通过后端 mutation 执行。"
    >
      <div className="button-row">
        <Button
          className="hero-button"
          isDisabled={mutation.isPending}
          onPress={() => setAction('approve')}
        >
          Approve Prompts
        </Button>
        <Button
          className="secondary-button"
          isDisabled={mutation.isPending}
          onPress={() => setAction('retry')}
        >
          Retry Stage
        </Button>
        <Button
          className="danger-button"
          isDisabled={mutation.isPending}
          onPress={() => setAction('cancel')}
        >
          Cancel Run
        </Button>
      </div>
      {mutation.error ? (
        <ErrorState error={mutation.error} />
      ) : null}
      {mutation.data ? (
        <div className="alert-box" role="status">
          <h3>Run action response</h3>
          <JsonViewer value={mutation.data} />
        </div>
      ) : null}
      <ConfirmDialog
        open={action !== null}
        title={copy?.title ?? ''}
        description={copy?.description ?? ''}
        variant={action === 'cancel' ? 'danger' : 'default'}
        onCancel={() => setAction(null)}
        onConfirm={() => {
          if (action) mutation.mutate(action)
          setAction(null)
        }}
      />
    </SectionCard>
  )
}
