import { useQuery } from '@tanstack/react-query'
import { FileText, FolderArchive, Image, LoaderCircle, Video } from 'lucide-react'
import { listArtifacts } from '../features/workbench/workbench.api'

function ArtifactIcon({ kind }: { kind: string }) {
  if (kind.includes('image') || kind.includes('grid')) return <Image size={20} />
  if (kind.includes('video')) return <Video size={20} />
  return <FileText size={20} />
}

export default function AssetsPage() {
  const artifacts = useQuery({ queryKey: ['artifacts'], queryFn: listArtifacts, refetchInterval: 15_000 })
  return (
    <div className="page-surface list-page">
      <header className="page-heading content-width"><div><span className="eyebrow">PRODUCTION LIBRARY</span><h1>资产库</h1><p>剧本、提示词、四宫格参考图与最终视频按任务统一归档。</p></div></header>
      <div className="content-width">
        {artifacts.isLoading ? <div className="loading-row"><LoaderCircle className="spin" /> 正在整理产物…</div> : artifacts.data?.length ? <div className="asset-grid">{artifacts.data.map((artifact, index) => { const kind = artifact.kind ?? artifact.type ?? 'document'; return <article key={artifact.artifact_id ?? artifact.id ?? index}><div className="asset-icon"><ArtifactIcon kind={kind} /></div><div><span className="eyebrow">{kind}</span><strong>{artifact.name ?? artifact.local_path?.split(/[\\/]/).pop() ?? '未命名产物'}</strong><small>{artifact.local_path ?? artifact.path ?? artifact.run_id}</small></div></article> })}</div> : <div className="empty-panel large"><FolderArchive size={30} /><strong>资产库会自动整理，不需要手工搬文件</strong><span>完成任意一道流水线任务后，标准化产物会显示在这里。</span></div>}
      </div>
    </div>
  )
}
