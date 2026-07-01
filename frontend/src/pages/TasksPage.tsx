import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, Boxes, LoaderCircle, Pause, Play, RotateCcw, XCircle } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  cancelBatch,
  listBatches,
  listRuns,
  pauseBatch,
  resumeBatch,
  retryBatch,
} from '../features/workbench/workbench.api'

type BatchAction = 'pause' | 'resume' | 'cancel' | 'retry'
const TERMINAL_BATCH = new Set(['completed', 'cancelled'])
const BATCH_ACTION_LABELS: Record<BatchAction, string> = {
  pause: '暂停',
  resume: '继续',
  retry: '重试',
  cancel: '取消',
}

export default function TasksPage() {
  const queryClient = useQueryClient()
  const [searchParams] = useSearchParams()
  const runs = useQuery({ queryKey: ['runs'], queryFn: listRuns, refetchInterval: 5_000 })
  const batches = useQuery({ queryKey: ['batches'], queryFn: listBatches, refetchInterval: 5_000 })
  const batchAction = useMutation({
    mutationFn: ({ batchId, action }: { batchId: string; action: BatchAction }) => {
      if (action === 'pause') return pauseBatch(batchId)
      if (action === 'resume') return resumeBatch(batchId)
      if (action === 'retry') return retryBatch(batchId)
      return cancelBatch(batchId)
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['batches'] })
      await queryClient.invalidateQueries({ queryKey: ['runs'] })
    },
  })

  const act = (batchId: string, action: BatchAction) => batchAction.mutate({ batchId, action })
  const activeAction = batchAction.variables
  const activeActionLabel = activeAction ? BATCH_ACTION_LABELS[activeAction.action] : ''
  const createdBatchId = searchParams.get('created') === '1' ? searchParams.get('batch') : ''

  return (
    <div className="page-surface list-page">
      <header className="page-heading content-width"><div><span className="eyebrow">PRODUCTION QUEUE</span><h1>任务队列</h1><p>批量任务和单条任务集中在这里，状态会自动刷新。</p></div></header>
      {createdBatchId && <div className="inline-notice content-width" role="status">刚创建批次 {createdBatchId}，队列会自动刷新。</div>}
      <div className="content-width queue-layout">
        <section className="queue-section">
          <div className="section-heading-row"><div><h2>批量任务</h2><p>{batches.data?.total ?? 0} 个批次</p></div></div>
          {batches.isLoading ? <div className="loading-row"><LoaderCircle className="spin" /> 正在读取…</div> : batches.data?.items.length ? (
            <div className="queue-list batch-queue-list">
              {batches.data.items.map((batch) => {
                const total = batch.item_count ?? batch.total_items ?? batch.items?.length ?? 0
                const completed = batch.completed_items ?? batch.summary?.completed ?? batch.items?.filter((item) => item.status === 'completed').length ?? 0
                const failed = batch.failed_items ?? batch.summary?.failed ?? batch.items?.filter((item) => item.status === 'failed').length ?? 0
                const paused = batch.paused || batch.status === 'paused'
                const pending = batchAction.isPending && batchAction.variables?.batchId === batch.batch_id
                const retryable = failed > 0 || ['failed', 'partial_failed', 'cancelled'].includes(batch.status)
                const childItems = batch.items?.filter((item) => item.run_id) ?? []
                return (
                  <article key={batch.batch_id}>
                    <span className={`run-state-dot is-${batch.status}`} />
                    <div className="queue-item-copy"><strong>{batch.batch_id}</strong><span>{completed}/{total} 已完成 · {failed} 失败</span></div>
                    <span className="status-chip">{paused ? '已暂停' : batch.status}</span>
                    <div className="batch-action-row" aria-label={`${batch.batch_id} 批次操作`}>
                      {!TERMINAL_BATCH.has(batch.status) && (paused ? (
                        <button type="button" className="icon-button is-quiet" disabled={pending} onClick={() => act(batch.batch_id, 'resume')} aria-label={`继续 ${batch.batch_id}`} title="继续"><Play size={16} /></button>
                      ) : (
                        <button type="button" className="icon-button is-quiet" disabled={pending} onClick={() => act(batch.batch_id, 'pause')} aria-label={`暂停 ${batch.batch_id}`} title="暂停"><Pause size={16} /></button>
                      ))}
                      {retryable && <button type="button" className="icon-button is-quiet" disabled={pending} onClick={() => act(batch.batch_id, 'retry')} aria-label={`重试 ${batch.batch_id}`} title="重试"><RotateCcw size={16} /></button>}
                      {!TERMINAL_BATCH.has(batch.status) && <button type="button" className="icon-button is-quiet is-danger" disabled={pending} onClick={() => act(batch.batch_id, 'cancel')} aria-label={`取消 ${batch.batch_id}`} title="取消"><XCircle size={16} /></button>}
                      {pending && <LoaderCircle className="spin" size={16} aria-label="正在执行批次操作" />}
                    </div>
                    {childItems.length > 0 && (
                      <div className="batch-child-list" aria-label={`${batch.batch_id} 子任务`}>
                        {childItems.map((item, index) => (
                          <Link className="batch-child-link" to={`/run/${item.run_id}`} key={item.run_id}>
                            <span className={`run-state-dot is-${item.status}`} />
                            <span className="batch-child-copy">
                              <strong>{item.idea || `子任务 ${index + 1}`}</strong>
                              <small>{item.current_stage || item.status}</small>
                            </span>
                            <ArrowRight size={14} />
                          </Link>
                        ))}
                      </div>
                    )}
                  </article>
                )
              })}
            </div>
          ) : <div className="empty-panel"><Boxes size={24} /><strong>还没有批量任务</strong><span>在控制台把任务数调到 2 个以上即可批量创建。</span></div>}
          {batchAction.isPending && activeAction && <div className="inline-notice" role="status"><LoaderCircle className="spin" size={16} />正在{activeActionLabel} {activeAction.batchId}…</div>}
          {batchAction.isSuccess && activeAction && <div className="inline-notice" role="status">{activeAction.batchId} 已{activeActionLabel}，队列正在刷新。</div>}
          {batchAction.isError && activeAction && <div className="inline-notice is-error" role="alert">{activeAction.batchId} {activeActionLabel}失败：{batchAction.error instanceof Error ? batchAction.error.message : '请稍后重试'}</div>}
        </section>
        <section className="queue-section">
          <div className="section-heading-row"><div><h2>全部作品</h2><p>{runs.data?.total ?? 0} 个任务</p></div></div>
          {runs.isLoading ? <div className="loading-row"><LoaderCircle className="spin" /> 正在读取…</div> : runs.data?.items.length ? <div className="queue-list">{runs.data.items.map((run) => <Link to={`/run/${run.run_id}`} key={run.run_id}><span className={`run-state-dot is-${run.status}`} /><div><strong>{run.idea || '自动创作任务'}</strong><span>{run.current_stage || '等待开始'}</span></div><span className="status-chip">{run.status}</span><ArrowRight size={17} /></Link>)}</div> : <div className="empty-panel"><Boxes size={24} /><strong>队列还是空的</strong><span>创建第一条任务后会出现在这里。</span></div>}
        </section>
      </div>
    </div>
  )
}
