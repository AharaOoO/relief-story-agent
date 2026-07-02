import { useEffect, useMemo, useState } from 'react'
import { Image, LoaderCircle, RotateCcw, Square } from 'lucide-react'
import type { RenderPlan } from '../workbench/workbench.api'

type Props = {
  plan: RenderPlan
  busy?: boolean
  onRetryImage: (segmentId: string) => void
  onRetryVideo: (segmentId: string) => void
  onCancel: (segmentId: string) => void
}

const ACTIVE = new Set(['image_generating', 'submitting', 'queued', 'running'])

export function SegmentExecutionPanel({ plan, busy = false, onRetryImage, onRetryVideo, onCancel }: Props) {
  const fallback = plan.segments.find((segment) => segment.status === 'failed' || ACTIVE.has(segment.status)) ?? plan.segments[0]
  const [selectedId, setSelectedId] = useState(fallback?.segment_id ?? '')
  useEffect(() => {
    if (!plan.segments.some((segment) => segment.segment_id === selectedId)) setSelectedId(fallback?.segment_id ?? '')
  }, [fallback?.segment_id, plan.segments, selectedId])
  const selected = useMemo(() => plan.segments.find((segment) => segment.segment_id === selectedId) ?? fallback, [fallback, plan.segments, selectedId])
  if (!selected) return null

  return (
    <section className="segment-execution-panel" aria-label="分段执行清单">
      <header className="segment-panel-header">
        <div><span className="eyebrow">SEGMENT PIPELINE</span><h3>分段生成队列</h3></div>
        <div className="segment-total"><strong>{plan.segments.length}</strong><span>段 · {plan.planned_duration_seconds} 秒</span></div>
      </header>
      <div className="segment-table" role="table">
        <div className="segment-table-head" role="row"><span>分段</span><span>时间</span><span>G2</span><span>ComfyUI</span><span>输出</span></div>
        {plan.segments.map((segment) => (
          <button key={segment.segment_id} type="button" aria-label={`分段 ${segment.order} ${segment.render_time_range}`} className={segment.segment_id === selected.segment_id ? 'segment-row is-selected' : 'segment-row'} onClick={() => setSelectedId(segment.segment_id)}>
            <span><b>{String(segment.order).padStart(2, '0')}</b> 镜头 {segment.shot_id}</span>
            <span>{segment.render_time_range}</span>
            <span className={`segment-state is-${segment.grid_image_asset ? 'completed' : segment.status}`}>{segment.grid_image_asset ? '已就绪' : '等待'}</span>
            <span className={`segment-state is-${segment.status}`}>{segment.status}</span>
            <span>{segment.outputs.length ? `${segment.outputs.length} 个` : '—'}</span>
          </button>
        ))}
      </div>
      <div className="segment-detail">
        <div className="segment-detail-title"><div><span>分段 {selected.order}</span><h4>{selected.render_time_range}</h4></div><span className={`status-chip is-${selected.status}`}>{selected.status}</span></div>
        <dl className="segment-metrics">
          <div><dt>时长</dt><dd>{selected.duration_seconds} 秒</dd></div><div><dt>帧率</dt><dd>{selected.fps} FPS</dd></div><div><dt>总帧</dt><dd>{selected.frame_count} 帧</dd></div><div><dt>关键帧</dt><dd>{selected.local_frame_indices.join(', ')}</dd></div>
          <div><dt>随机种</dt><dd>{selected.seed}</dd></div><div><dt>Prompt ID</dt><dd>{selected.submission?.prompt_id ?? '尚未提交'}</dd></div>
        </dl>
        <div className="segment-detail-grid"><div><span>视频提示词</span><p>{selected.positive_prompt}</p></div><div><span>工作流模型</span>{selected.workflow_models.length ? selected.workflow_models.map((model) => <p key={`${model.node_id}-${model.input_name}`}>{model.selected}</p>) : <p>等待工作流预检</p>}</div></div>
        {selected.error && <div className="inline-notice is-error">{selected.error}</div>}
        <div className="segment-actions">
          <button type="button" className="secondary-button compact" disabled={busy || ACTIVE.has(selected.status)} onClick={() => onRetryImage(selected.segment_id)}><Image size={15} /> 重试本段图片</button>
          <button type="button" className="secondary-button compact" disabled={busy || ACTIVE.has(selected.status)} onClick={() => onRetryVideo(selected.segment_id)}><RotateCcw size={15} /> 重试本段视频</button>
          {ACTIVE.has(selected.status) && <button type="button" className="secondary-button compact" disabled={busy} onClick={() => onCancel(selected.segment_id)}>{busy ? <LoaderCircle className="spin" size={15} /> : <Square size={15} />} 停止本段</button>}
        </div>
      </div>
    </section>
  )
}
