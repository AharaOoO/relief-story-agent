import { CopyButton } from '../../../shared/components/CopyButton'
import { SectionCard } from '../../../shared/components/SectionCard'

const diagnostic = `# Relief Story Agent Diagnostic Summary

## Backend
http://127.0.0.1:8891

## Failed Stage
comfyui

## Recommended Action
refresh_comfyui_outputs

## Blockers
- Missing real video evidence
- Do not include API key values`

export function DiagnosticExportPanel() {
  return (
    <SectionCard
      title="Diagnostic Export"
      description="可复制 Markdown 诊断摘要，禁止包含明文 API key。"
      footer={<CopyButton value={diagnostic} label="复制诊断摘要" />}
    >
      <pre className="json-viewer">{diagnostic}</pre>
    </SectionCard>
  )
}
