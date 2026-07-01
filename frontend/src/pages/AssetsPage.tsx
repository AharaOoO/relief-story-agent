import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ExternalLink,
  FileText,
  FolderArchive,
  FolderOpen,
  Image,
  LoaderCircle,
  Video,
} from 'lucide-react'
import { listArtifacts } from '../features/workbench/workbench.api'

function ArtifactIcon({ kind }: { kind: string }) {
  if (kind.includes('image') || kind.includes('grid')) return <Image size={20} />
  if (kind.includes('video')) return <Video size={20} />
  return <FileText size={20} />
}

function isRemoteUrl(value: string) {
  return /^https?:\/\//i.test(value)
}

function artifactName(path: string) {
  return path.split(/[\\/]/).filter(Boolean).pop() ?? path
}

function containingDirectory(path: string) {
  const index = Math.max(path.lastIndexOf('/'), path.lastIndexOf('\\'))
  return index > 0 ? path.slice(0, index) : ''
}

export default function AssetsPage() {
  const artifacts = useQuery({
    queryKey: ['artifacts'],
    queryFn: listArtifacts,
    refetchInterval: 15_000,
  })
  const [message, setMessage] = useState('')

  const openLocalPath = async (path: string, kind: 'file' | 'folder') => {
    if (!window.reliefDesktop) {
      setMessage('请在桌面客户端中打开本地产物。')
      return
    }
    try {
      await window.reliefDesktop.openPath(path)
      setMessage(kind === 'folder' ? '已打开产物所在目录。' : '已交给系统默认程序打开。')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '无法打开这个产物')
    }
  }

  return (
    <div className="page-surface list-page">
      <header className="page-heading content-width">
        <div>
          <span className="eyebrow">PRODUCTION LIBRARY</span>
          <h1>资产库</h1>
          <p>剧本、提示词、四宫格参考图与最终视频按任务统一归档。</p>
        </div>
      </header>
      <div className="content-width">
        {artifacts.isLoading ? (
          <div className="loading-row"><LoaderCircle className="spin" /> 正在整理产物...</div>
        ) : artifacts.data?.length ? (
          <div className="asset-grid">
            {artifacts.data.map((artifact, index) => {
              const kind = artifact.kind ?? artifact.type ?? 'document'
              const artifactPath = artifact.local_path ?? artifact.path ?? ''
              const name = artifact.name ?? artifactName(artifactPath) ?? '未命名产物'
              const folderPath = artifactPath && !isRemoteUrl(artifactPath)
                ? containingDirectory(artifactPath)
                : ''

              return (
                <article key={artifact.artifact_id ?? artifact.id ?? index}>
                  <div className="asset-icon"><ArtifactIcon kind={kind} /></div>
                  <div>
                    <span className="eyebrow">{kind}</span>
                    <strong>{name}</strong>
                    <small>{artifactPath || artifact.run_id}</small>
                  </div>
                  {artifactPath && (
                    <div className="asset-action-row">
                      {isRemoteUrl(artifactPath) ? (
                        <a
                          className="icon-button is-quiet"
                          href={artifactPath}
                          target="_blank"
                          rel="noreferrer"
                          aria-label={`打开链接 ${name}`}
                          title="打开链接"
                        >
                          <ExternalLink size={16} />
                        </a>
                      ) : (
                        <>
                          <button
                            type="button"
                            className="icon-button is-quiet"
                            onClick={() => void openLocalPath(artifactPath, 'file')}
                            aria-label={`打开文件 ${name}`}
                            title="打开文件"
                          >
                            <ExternalLink size={16} />
                          </button>
                          {folderPath && (
                            <button
                              type="button"
                              className="icon-button is-quiet"
                              onClick={() => void openLocalPath(folderPath, 'folder')}
                              aria-label={`打开所在目录 ${name}`}
                              title="打开所在目录"
                            >
                              <FolderOpen size={16} />
                            </button>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </article>
              )
            })}
          </div>
        ) : (
          <div className="empty-panel large">
            <FolderArchive size={30} />
            <strong>资产库会自动整理，不需要手工搬文件</strong>
            <span>完成任意一道流水线任务后，标准化产物会显示在这里。</span>
          </div>
        )}
        {message && <div className="settings-message" role="status">{message}</div>}
      </div>
    </div>
  )
}
