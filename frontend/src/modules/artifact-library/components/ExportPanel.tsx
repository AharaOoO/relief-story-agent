import { Button } from '@heroui/react'
import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { ErrorState } from '../../../shared/components/ErrorState'
import { JsonViewer } from '../../../shared/components/JsonViewer'
import { SectionCard } from '../../../shared/components/SectionCard'
import {
  exportBatch,
  validateBatchExport,
  validateBatchExportZip,
} from '../api/artifacts.api'

export function ExportPanel({
  scope,
  targetId,
}: {
  scope: 'run' | 'batch'
  targetId: string
}) {
  const [exportDir, setExportDir] = useState('D:/relief_story_exports')
  const [zipPath, setZipPath] = useState('D:/relief_story_exports/export.zip')
  const batchOnly = scope === 'batch' && targetId.trim().length > 0
  const action = useMutation({
    mutationFn: (kind: 'export' | 'validate-dir' | 'validate-zip') => {
      if (kind === 'export') {
        return exportBatch(targetId, {
          export_root: exportDir,
          include_zip: true,
        })
      }
      if (kind === 'validate-dir') {
        return validateBatchExport(targetId, {
          export_dir: exportDir,
          save_report: true,
        })
      }
      return validateBatchExportZip(targetId, {
        zip_path: zipPath,
        save_report: true,
      })
    },
  })

  return (
    <SectionCard
      title="Export"
      description="导出 batch、校验目录、校验 zip。"
      tone="yellow"
    >
      <div className="form-grid">
        <div className="field">
          <label htmlFor="export-dir">Export Dir</label>
          <input
            id="export-dir"
            value={exportDir}
            onChange={(event) => setExportDir(event.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="zip-path">Zip Path</label>
          <input
            id="zip-path"
            value={zipPath}
            onChange={(event) => setZipPath(event.target.value)}
          />
        </div>
        <div className="button-row">
          <Button
            className="hero-button"
            isDisabled={!batchOnly || action.isPending}
            onPress={() => action.mutate('export')}
          >
            导出 batch
          </Button>
          <Button
            className="secondary-button"
            isDisabled={!batchOnly || action.isPending}
            onPress={() => action.mutate('validate-dir')}
          >
            校验目录
          </Button>
          <Button
            className="ghost-button"
            isDisabled={!batchOnly || action.isPending}
            onPress={() => action.mutate('validate-zip')}
          >
            校验 zip
          </Button>
        </div>
      </div>
      {!batchOnly ? (
        <p style={{ fontWeight: 900 }}>导出操作需要选择 batch scope 和 batch id。</p>
      ) : null}
      {action.error ? <ErrorState error={action.error} /> : null}
      {action.data ? (
        <div className="alert-box" role="status">
          <h3>Export response</h3>
          <JsonViewer value={action.data} />
        </div>
      ) : null}
    </SectionCard>
  )
}
