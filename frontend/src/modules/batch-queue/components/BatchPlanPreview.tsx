import { Button } from '@heroui/react'
import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { buildBatchRunRequest } from '../../../shared/api/backendPayloads'
import { ConfirmDialog } from '../../../shared/components/ConfirmDialog'
import { ErrorState } from '../../../shared/components/ErrorState'
import { JsonViewer } from '../../../shared/components/JsonViewer'
import { SectionCard } from '../../../shared/components/SectionCard'
import { StatusBadge } from '../../../shared/components/StatusBadge'
import { createBatch, planBatch } from '../api/batches.api'

export function BatchPlanPreview({ ideasText }: { ideasText: string }) {
  const navigate = useNavigate()
  const [confirmOpen, setConfirmOpen] = useState(false)
  const payload = buildBatchRunRequest({
    ideasText,
    approvalMode: 'manual',
    durationSeconds: 60,
  })
  const canSubmit = payload.items.length > 0
  const plan = useMutation({
    mutationFn: () => planBatch(payload),
  })
  const create = useMutation({
    mutationFn: () => createBatch(payload),
    onSuccess: (data) => {
      if (data.batch_id) {
        void navigate(`/batches/${data.batch_id}`)
      }
    },
  })

  return (
    <SectionCard
      title="Batch Plan"
      description="预估 valid/invalid/blockers；Plan Only 不创建 batch。"
      footer={
        <div className="button-row">
          <Button
            className="secondary-button"
            isDisabled={!canSubmit || plan.isPending}
            onPress={() => plan.mutate()}
          >
            Plan Only
          </Button>
          <Button
            className="hero-button"
            isDisabled={!canSubmit || create.isPending}
            onPress={() => setConfirmOpen(true)}
          >
            Create Batch
          </Button>
        </div>
      }
    >
      <div className="metric-grid">
        <div className="metric">
          <span>Total</span>
          <strong>{payload.items.length}</strong>
        </div>
        <div className="metric">
          <span>Valid</span>
          <strong>{payload.items.length}</strong>
        </div>
        <div className="metric">
          <span>Preflight</span>
          <strong>
            <StatusBadge
              status={plan.data || create.data ? 'ready' : 'warning'}
            />
          </strong>
        </div>
      </div>
      {plan.error ? (
        <ErrorState error={plan.error} onRetry={() => plan.mutate()} />
      ) : null}
      {create.error ? (
        <ErrorState error={create.error} onRetry={() => create.mutate()} />
      ) : null}
      {plan.data ? (
        <div className="alert-box" role="status">
          <h3>Batch plan response</h3>
          <JsonViewer value={plan.data} />
        </div>
      ) : null}
      {create.data ? (
        <div className="alert-box" role="status">
          <h3>Batch created</h3>
          <JsonViewer value={create.data} />
        </div>
      ) : null}
      <ConfirmDialog
        open={confirmOpen}
        title="确认创建 Batch"
        description="这会把每行 idea 交给后端创建批量任务，并可能进入真实 pipeline。"
        confirmText="创建 Batch"
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => {
          setConfirmOpen(false)
          create.mutate()
        }}
      />
    </SectionCard>
  )
}
