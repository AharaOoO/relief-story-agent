import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Boxes, LoaderCircle } from 'lucide-react'
import { Link } from 'react-router-dom'
import { listBatches, listRuns } from '../features/workbench/workbench.api'

export default function TasksPage() {
  const runs = useQuery({ queryKey: ['runs'], queryFn: listRuns, refetchInterval: 5_000 })
  const batches = useQuery({ queryKey: ['batches'], queryFn: listBatches, refetchInterval: 5_000 })
  return (
    <div className="page-surface list-page">
      <header className="page-heading content-width"><div><span className="eyebrow">PRODUCTION QUEUE</span><h1>任务队列</h1><p>批量任务和单条任务集中在这里，状态会自动刷新。</p></div></header>
      <div className="content-width queue-layout">
        <section className="queue-section">
          <div className="section-heading-row"><div><h2>批量任务</h2><p>{batches.data?.total ?? 0} 个批次</p></div></div>
          {batches.isLoading ? <div className="loading-row"><LoaderCircle className="spin" /> 正在读取…</div> : batches.data?.items.length ? <div className="queue-list">{batches.data.items.map((batch) => { const total = batch.item_count ?? batch.total_items ?? batch.items?.length ?? 0; const completed = batch.completed_items ?? batch.summary?.completed ?? batch.items?.filter((item) => item.status === 'completed').length ?? 0; const failed = batch.failed_items ?? batch.summary?.failed ?? batch.items?.filter((item) => item.status === 'failed').length ?? 0; return <article key={batch.batch_id}><span className={`run-state-dot is-${batch.status}`} /><div><strong>{batch.batch_id}</strong><span>{completed}/{total} 已完成 · {failed} 失败</span></div><span className="status-chip">{batch.status}</span></article> })}</div> : <div className="empty-panel"><Boxes size={24} /><strong>还没有批量任务</strong><span>在控制台把任务数调到 2 个以上即可批量创建。</span></div>}
        </section>
        <section className="queue-section">
          <div className="section-heading-row"><div><h2>全部作品</h2><p>{runs.data?.total ?? 0} 个任务</p></div></div>
          {runs.isLoading ? <div className="loading-row"><LoaderCircle className="spin" /> 正在读取…</div> : runs.data?.items.length ? <div className="queue-list">{runs.data.items.map((run) => <Link to={`/run/${run.run_id}`} key={run.run_id}><span className={`run-state-dot is-${run.status}`} /><div><strong>{run.idea || '自动创作任务'}</strong><span>{run.current_stage || '等待开始'}</span></div><span className="status-chip">{run.status}</span><ArrowRight size={17} /></Link>)}</div> : <div className="empty-panel"><Boxes size={24} /><strong>队列还是空的</strong><span>创建第一条任务后会出现在这里。</span></div>}
        </section>
      </div>
    </div>
  )
}
