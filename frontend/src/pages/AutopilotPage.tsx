import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertCircle, CheckCircle2, ChevronRight, LoaderCircle, Pause, Play, RefreshCw, RotateCcw, Settings2 } from 'lucide-react'
import { useParams } from 'react-router-dom'
import { AUTOPILOT_STAGES, stageStatusFromTimeline, type AutopilotStageStatus } from '../features/autopilot/stages'
import { StageRail } from '../features/autopilot/StageRail'
import { StageWorkspace } from '../features/autopilot/StageWorkspace'
import { RunComposer } from '../features/run-composer/RunComposer'
import {
  approveRun,
  cancelRun,
  fetchRun,
  fetchRunArtifacts,
  fetchRunEvents,
  fetchTimeline,
  refreshRunComfyUI,
  retryRun,
  type RunEventRecord,
} from '../features/workbench/workbench.api'
import { useWorkbench } from '../app/workbench/workbench.context'

const TERMINAL = new Set(['completed', 'failed', 'cancelled'])
type RunAction = 'cancel' | 'retry' | 'approve' | 'refresh'

export default function AutopilotPage() {
  const { runId } = useParams()
  const { openSettings } = useWorkbench()
  const queryClient = useQueryClient()
  const [selectedStage, setSelectedStage] = useState('chief_screenwriter')
  const [eventItems, setEventItems] = useState<RunEventRecord[]>([])
  const [actionMessage, setActionMessage] = useState('')
  const eventCursor = useRef(0)
  const run = useQuery({
    queryKey: ['run', runId],
    queryFn: () => fetchRun(runId ?? ''),
    enabled: Boolean(runId),
    refetchInterval: (query) => TERMINAL.has(query.state.data?.status ?? '') ? false : 2_000,
  })
  const timeline = useQuery({
    queryKey: ['run-timeline', runId],
    queryFn: () => fetchTimeline(runId ?? ''),
    enabled: Boolean(runId),
    refetchInterval: runId ? 2_000 : false,
  })
  const artifacts = useQuery({
    queryKey: ['run-artifacts', runId],
    queryFn: () => fetchRunArtifacts(runId ?? ''),
    enabled: Boolean(runId),
    refetchInterval: runId ? 4_000 : false,
  })
  const events = useQuery({
    queryKey: ['run-events', runId],
    queryFn: () => fetchRunEvents(runId ?? '', eventCursor.current),
    enabled: Boolean(runId),
    refetchInterval: runId && !TERMINAL.has(run.data?.status ?? '') ? 1_500 : false,
  })

  useEffect(() => {
    eventCursor.current = 0
    setEventItems([])
  }, [runId])

  useEffect(() => {
    if (!events.data) return
    eventCursor.current = events.data.next_cursor
    if (events.data.events.length) {
      setEventItems((current) => {
        const merged = [...current, ...events.data.events]
        return Array.from(new Map(merged.map((event) => [event.sequence, event])).values()).slice(-30)
      })
      void queryClient.invalidateQueries({ queryKey: ['run', runId] })
      void queryClient.invalidateQueries({ queryKey: ['run-timeline', runId] })
    }
  }, [events.data, queryClient, runId])

  const action = useMutation<unknown, Error, RunAction>({
    mutationFn: (kind) => {
      if (kind === 'cancel') return cancelRun(runId ?? '')
      if (kind === 'retry') return retryRun(runId ?? '', selectedStage)
      if (kind === 'approve') return approveRun(runId ?? '')
      return refreshRunComfyUI(runId ?? '')
    },
    onMutate: (kind) => {
      setActionMessage(kind === 'approve' ? '正在批准并继续流水线…' : kind === 'refresh' ? '正在向 ComfyUI 查询最新成片…' : kind === 'retry' ? '正在重新排队…' : '正在停止任务…')
    },
    onSuccess: async (_, kind) => {
      await queryClient.invalidateQueries({ queryKey: ['run', runId] })
      await queryClient.invalidateQueries({ queryKey: ['run-timeline', runId] })
      await queryClient.invalidateQueries({ queryKey: ['run-artifacts', runId] })
      setActionMessage(kind === 'refresh' ? '已刷新 ComfyUI 输出。' : '操作已生效。')
    },
    onError: (error) => setActionMessage(error instanceof Error ? error.message : '操作失败，请查看诊断。'),
  })

  const statuses = useMemo(() => Object.fromEntries(
    AUTOPILOT_STAGES.map((stage) => [stage.id, stageStatusFromTimeline(stage.id, timeline.data ?? [], run.data?.status, run.data?.current_stage)]),
  ) as Record<string, AutopilotStageStatus>, [run.data?.current_stage, run.data?.status, timeline.data])

  const completed = Object.values(statuses).filter((status) => status === 'completed' || status === 'skipped').length
  const activeStage = AUTOPILOT_STAGES.find((stage) => stage.id === (run.data?.current_stage || selectedStage))
  const promptSnapshot = run.data?.prompt_snapshot as Partial<Record<(typeof AUTOPILOT_STAGES)[number]['id'], string>> | undefined

  return (
    <div className="autopilot-page page-surface">
      <header className="page-heading content-width">
        <div><span className="eyebrow">AUTOMATED PRODUCTION</span><h1>自动执行</h1><p>{runId ? '流水线正在按顺序执行，你可以随时查看每一道工序。' : '先配置前六道模型工序，再让整条流水线自动工作。'}</p></div>
        <button className="secondary-button" type="button" onClick={openSettings}><Settings2 size={17} /> 高级设置</button>
      </header>

      {!runId && (
        <div className="autopilot-setup content-width">
          <div className="autopilot-progress-header">
            <span>十道工序</span><strong>前 6 道可分别选择模型和提示词</strong><span>后 4 道自动执行</span>
          </div>
          <div className="autopilot-workbench-grid">
            <StageRail selectedStage={selectedStage} statuses={statuses} onSelect={setSelectedStage} />
            <StageWorkspace stageId={selectedStage} />
          </div>
          <RunComposer compact heading="确认故事输入并开始" />
        </div>
      )}

      {runId && (
        <div className="autopilot-live content-width">
          <section className="live-overview">
            <div className="live-title-row">
              <div><span className="status-chip is-live">{run.data?.status ?? '读取中'}</span><h2>{run.data?.idea || run.data?.request?.idea || '自动创作任务'}</h2><p>任务 ID：{runId}</p></div>
              <div className="live-actions">
                {run.data?.status === 'awaiting_approval' && <button type="button" className="primary-button" disabled={action.isPending} onClick={() => action.mutate('approve')}><CheckCircle2 size={16} /> 批准并继续</button>}
                <button type="button" className="secondary-button" disabled={action.isPending} onClick={() => action.mutate('refresh')}><RefreshCw size={16} /> 刷新成片</button>
                {!TERMINAL.has(run.data?.status ?? '') && <button type="button" className="secondary-button" disabled={action.isPending} onClick={() => action.mutate('cancel')}><Pause size={16} /> 停止任务</button>}
                {(run.data?.status === 'failed' || run.data?.status === 'cancelled') && <button type="button" className="primary-button" disabled={action.isPending} onClick={() => action.mutate('retry')}><RotateCcw size={16} /> 从当前工序重试</button>}
              </div>
            </div>
            {actionMessage && <div className={`inline-notice ${action.isError ? 'is-error' : ''}`} role="status">{action.isPending && <LoaderCircle className="spin" size={16} />}{actionMessage}</div>}
            <div className="global-progress"><div style={{ width: `${completed * 10}%` }} /><span>{completed}/10</span></div>
            <div className="current-stage-callout"><Play size={17} /><span>当前</span><strong>{activeStage?.label} · {activeStage?.title}</strong><ChevronRight size={16} /></div>
          </section>

          {(run.isError || timeline.isError) && <div className="inline-notice is-error"><AlertCircle size={17} /> 无法读取任务状态，请确认本地后端仍在线。</div>}

          <div className="autopilot-workbench-grid">
            <StageRail selectedStage={selectedStage} statuses={statuses} onSelect={setSelectedStage} />
            <div className="live-stage-column">
              <StageWorkspace stageId={selectedStage} readOnly runRequest={run.data?.request} promptSnapshot={promptSnapshot} />
              <section className="stage-output-panel">
                <div className="section-heading-row"><div><span className="eyebrow">LIVE OUTPUT</span><h3>本工序产物</h3></div><span className={`status-chip is-${statuses[selectedStage]}`}>{statuses[selectedStage]}</span></div>
                {run.data?.error && statuses[selectedStage] === 'failed' && <div className="inline-notice is-error"><AlertCircle size={16} />{run.data.error}</div>}
                {artifacts.data?.filter((item) => (item.kind ?? item.type ?? '').includes(selectedStage)).length ? (
                  <ul>{artifacts.data.filter((item) => (item.kind ?? item.type ?? '').includes(selectedStage)).map((item, index) => <li key={item.artifact_id ?? item.id ?? index}><strong>{item.name ?? item.kind ?? item.type ?? '产物'}</strong><span>{item.local_path ?? item.path}</span></li>)}</ul>
                ) : (
                  <div className="stage-output-empty">{statuses[selectedStage] === 'running' ? 'Agent 正在写入本工序结果…' : statuses[selectedStage] === 'completed' ? '工序已完成，标准化结果已归档。' : '执行到这里后，产物会自动出现。'}</div>
                )}
                {eventItems.length > 0 && <div className="run-event-feed" aria-live="polite"><strong>实时事件</strong>{eventItems.slice(-5).reverse().map((event) => <div key={event.sequence}><span>{event.stage || event.event_type}</span><p>{event.message || event.event_type}</p></div>)}</div>}
              </section>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
