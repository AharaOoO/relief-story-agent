import { Button } from '@heroui/react'
import { useMutation } from '@tanstack/react-query'
import { PlayCircle } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ConfirmDialog } from '../../../shared/components/ConfirmDialog'
import { ErrorState } from '../../../shared/components/ErrorState'
import { JsonViewer } from '../../../shared/components/JsonViewer'
import { SectionCard } from '../../../shared/components/SectionCard'
import { createRun, preflightRun } from '../api/runs.api'
import type { RunRequest } from '../contracts/run.contract'

type CreateRunSubmitPanelProps = {
  canSubmit: boolean
  request: RunRequest
}

export function CreateRunSubmitPanel({
  canSubmit,
  request,
}: CreateRunSubmitPanelProps) {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const preflight = useMutation({
    mutationFn: () => preflightRun(request),
  })
  const create = useMutation({
    mutationFn: () => createRun(request),
    onSuccess: (data) => {
      if (data.run_id) {
        void navigate(`/runs/${data.run_id}/review`)
      }
    },
  })

  return (
    <SectionCard
      title="提交控制"
      description="真实 run 需要确认；dry-run 默认安全。"
      tone="yellow"
    >
      <div className="button-row">
        <Button
          className="secondary-button"
          isDisabled={!canSubmit || preflight.isPending}
          onPress={() => preflight.mutate()}
        >
          <PlayCircle size={16} />
          Dry Run
        </Button>
        <Button
          className="hero-button"
          isDisabled={!canSubmit || create.isPending}
          onPress={() => setOpen(true)}
        >
          创建真实 Run
        </Button>
      </div>
      {!canSubmit ? (
        <p style={{ fontWeight: 900 }}>填写创作目标后才能创建或预检。</p>
      ) : null}
      {preflight.error ? (
        <ErrorState error={preflight.error} onRetry={() => preflight.mutate()} />
      ) : null}
      {create.error ? (
        <ErrorState error={create.error} onRetry={() => setOpen(true)} />
      ) : null}
      {preflight.data ? (
        <div className="alert-box" role="status">
          <h3>Dry run response</h3>
          <JsonViewer value={preflight.data} />
        </div>
      ) : null}
      {create.data ? (
        <div className="alert-box" role="status">
          <h3>Run created</h3>
          <JsonViewer value={create.data} />
        </div>
      ) : null}
      <ConfirmDialog
        open={open}
        title="确认创建真实 Run"
        description="这会触发后端 pipeline，并可能调用真实模型与 ComfyUI。"
        confirmText="创建"
        onCancel={() => setOpen(false)}
        onConfirm={() => {
          setOpen(false)
          create.mutate()
        }}
      />
    </SectionCard>
  )
}
