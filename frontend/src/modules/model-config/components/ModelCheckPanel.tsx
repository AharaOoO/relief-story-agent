import { Button } from '@heroui/react'
import { useMutation } from '@tanstack/react-query'
import { ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { ConfirmDialog } from '../../../shared/components/ConfirmDialog'
import { ErrorState } from '../../../shared/components/ErrorState'
import { JsonViewer } from '../../../shared/components/JsonViewer'
import { SectionCard } from '../../../shared/components/SectionCard'
import { runModelCheck } from '../api/modelConfig.api'

export function ModelCheckPanel() {
  const [confirmOpen, setConfirmOpen] = useState(false)
  const modelCheck = useMutation({
    mutationFn: (realRun: boolean) => runModelCheck({ real_run: realRun }),
  })

  return (
    <SectionCard
      title="模型探针"
      description="dry-run 可直接跑，real-run 必须二次确认，避免昂贵模型误触发。"
      footer={
        <div className="button-row">
          <Button
            className="secondary-button"
            isDisabled={modelCheck.isPending}
            onPress={() => modelCheck.mutate(false)}
          >
            <ShieldCheck size={16} />
            Dry Run Check
          </Button>
          <Button
            className="hero-button"
            isDisabled={modelCheck.isPending}
            onPress={() => setConfirmOpen(true)}
          >
            Real Run Check
          </Button>
        </div>
      }
    >
      <p>
        探针用于确认 endpoint、model、key 环境变量和 JSON contract。配置、验证、
        契约错误不会自动 retry。
      </p>
      {modelCheck.error ? (
        <ErrorState
          error={modelCheck.error}
          onRetry={() => modelCheck.mutate(false)}
        />
      ) : null}
      {modelCheck.data ? (
        <div className="alert-box" role="status">
          <h3>Model check response</h3>
          <JsonViewer value={modelCheck.data} />
        </div>
      ) : null}
      <ConfirmDialog
        open={confirmOpen}
        title="确认真实模型探针"
        description="这会调用真实模型 API。前端不会保存 key，但可能产生模型费用。"
        confirmText="确认运行"
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => {
          setConfirmOpen(false)
          modelCheck.mutate(true)
        }}
      />
    </SectionCard>
  )
}
