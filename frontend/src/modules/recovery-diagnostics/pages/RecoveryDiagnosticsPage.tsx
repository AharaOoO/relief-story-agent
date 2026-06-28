import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { ConfirmDialog } from '../../../shared/components/ConfirmDialog'
import { DangerZone } from '../../../shared/components/DangerZone'
import { ErrorState } from '../../../shared/components/ErrorState'
import { JsonViewer } from '../../../shared/components/JsonViewer'
import { PageHeader } from '../../../shared/components/PageHeader'
import { SectionCard } from '../../../shared/components/SectionCard'
import { useDocumentTitle } from '../../../shared/hooks/useDocumentTitle'
import { recoverBatch } from '../api/recovery.api'
import { AcceptanceStatusPanel } from '../components/AcceptanceStatusPanel'
import { DiagnosticExportPanel } from '../components/DiagnosticExportPanel'
import { FailureDetailCard } from '../components/FailureDetailCard'
import { RecoveryPlanPanel } from '../components/RecoveryPlanPanel'
import { RecoveryTargetTable } from '../components/RecoveryTargetTable'

export function RecoveryDiagnosticsPage() {
  useDocumentTitle('故障恢复')
  const params = useParams()
  const queryClient = useQueryClient()
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [targetBatchId, setTargetBatchId] = useState(
    params.batchId ?? 'batch_demo_001',
  )
  const recovery = useMutation({
    mutationFn: () =>
      recoverBatch(targetBatchId, {
        dry_run: false,
        action_codes: null,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ['batch-recovery-plan', targetBatchId],
      })
    },
  })
  const canRecover = targetBatchId.trim().length > 0

  return (
    <div className="stack">
      <PageHeader
        title="故障恢复"
        description="只自动恢复安全失败；配置、模板、契约、质量问题必须人工处理。"
        kicker="Checkpoint 07"
      />
      <div className="grid-two">
        <div className="stack">
          <FailureDetailCard />
          <RecoveryPlanPanel batchId={targetBatchId} />
          <SectionCard title="Recovery Targets" description="恢复前必须展示 plan。">
            <RecoveryTargetTable />
          </SectionCard>
        </div>
        <div className="stack">
          <AcceptanceStatusPanel />
          <DiagnosticExportPanel />
          <DangerZone
            title="Recover Batch"
            description="recover 前先查看 recovery plan；configuration/validation/contract 不自动重试。"
            actionLabel="执行安全恢复"
            onAction={() => setConfirmOpen(true)}
          >
            <div className="field">
              <label htmlFor="recovery-batch-id">Target Batch ID</label>
              <input
                id="recovery-batch-id"
                value={targetBatchId}
                onChange={(event) => setTargetBatchId(event.target.value)}
              />
            </div>
            {!canRecover ? <p>需要 batch id 后才能执行恢复。</p> : null}
          </DangerZone>
          {recovery.error ? <ErrorState error={recovery.error} /> : null}
          {recovery.data ? (
            <div className="alert-box" role="status">
              <h3>Recovery response</h3>
              <JsonViewer value={recovery.data} />
            </div>
          ) : null}
        </div>
      </div>
      <ConfirmDialog
        open={confirmOpen}
        title="确认安全恢复"
        description="只执行后端 recovery plan 标记为 safe 的动作。"
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => {
          setConfirmOpen(false)
          if (canRecover) recovery.mutate()
        }}
      />
    </div>
  )
}
