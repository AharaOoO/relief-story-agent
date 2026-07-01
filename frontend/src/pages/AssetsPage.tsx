import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ExternalLink, FileText, FolderArchive, Image, LoaderCircle, Video } from 'lucide-react'
import { listArtifacts } from '../features/workbench/workbench.api'

function ArtifactIcon({ kind }: { kind: string }) {
  if (kind.includes('image') || kind.includes('grid')) return <Image size={20} />
  if (kind.includes('video')) return <Video size={20} />
  return <FileText size={20} />
}

export default function AssetsPage() {
  const artifacts = useQuery({ queryKey: ['artifacts'], queryFn: listArtifacts, refetchInterval: 15_000 })
  const [message, setMessage] = useState('')

  const openArtifact = async (path: string) => {
    if (!window.reliefDesktop) {
      setMessage('请在桌面客户端中打开本地产物。')
      return
    }
    try {
      await window.reliefDesktop.openPath(path)
      setMessage('已交给系统默认程序打开。')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '无法打开这个产物')
    }
  }
  return (
    <div className="page-surface list-page">
      <header className="page-heading content-width"><div><span className="eyebrow">PRODUCTION LIBRARY</span><h1>资产库</h1><p>剧本、提示词、四宫格参考图与最终视频按任务统一归档。</p></div></header>
      <div className="content-width">
        {artifacts.isLoading ? <div className="loading-row"><LoaderCircle className="spin" /> 正在整理产物…</div> : artifacts.data?.length ? <div className="asset-grid">{artifacts.data.map((artifact, index) => { const kind = artifact.kind ?? artifact.type ?? 'document'; const localPath = artifact.local_path ?? artifact.path ?? ''; return <article key={artifact.artifact_id ?? artifact.id ?? index}><div className="asset-icon"><ArtifactIcon kind={kind} /></div><div><span className="eyebrow">{kind}</span><strong>{artifact.name ?? localPath.split(/[\\/]/).pop() ?? '未命名产物'}</strong><small>{localPath || artifact.run_id}</small></div>{localPath && !/^https?:/i.test(localPath) && <button type="button" className="icon-button is-quiet" onClick={() => void openArtifact(localPath)} aria-label={`打开 ${artifact.name ?? localPath.split(/[\\/]/).pop()}`} title="打开产物"><ExternalLink size={16} /></button>}</article> })}</div> : <div className="empty-panel large"><FolderArchive size={30} /><strong>资产库会自动整理，不需要手工搬文件</strong><span>完成任意一道流水线任务后，标准化产物会显示在这里。</span></div>}
        {message && <div className="settings-message" role="status">{message}</div>}
      </div>
    </div>
  )
}
