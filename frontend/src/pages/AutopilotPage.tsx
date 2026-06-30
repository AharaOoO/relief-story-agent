import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertCircle, ChevronRight, Pause, Play, RotateCcw, Settings2 } from 'lucide-react'
import { useParams } from 'react-router-dom'
import { AUTOPILOT_STAGES, stageStatusFromTimeline, type AutopilotStageStatus } from '../features/autopilot/stages'
import { StageRail } from '../features/autopilot/StageRail'
import { StageWorkspace } from '../features/autopilot/StageWorkspace'
import { RunComposer } from '../features/run-composer/RunComposer'
import { cancelRun, fetchRun, fetchRunArtifacts, fetchTimeline, retryRun } from '../features/workbench/workbench.api'
import { useWorkbench } from '../app/workbench/workbench.context'

const TERMINAL = new Set(['completed', 'failed', 'cancelled'])

export default function AutopilotPage() {
  const { runId } = useParams()
  const { openSettings } = useWorkbench()
  const queryClient = useQueryClient()
  const [selectedStage, setSelectedStage] = useState('chief_screenwriter')
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
  const action = useMutation({
    mutationFn: (kind: 'cancel' | 'retry') => kind === 'cancel' ? cancelRun(runId ?? '') : retryRun(runId ?? '', selectedStage),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['run', runId] })
      await queryClient.invalidateQueries({ queryKey: ['run-timeline', runId] })
    },
  })

  const statuses = useMemo(() => Object.fromEntries(
    AUTOPILOT_STAGES.map((stage) => [stage.id, stageStatusFromTimeline(stage.id, timeline.data ?? [], run.data?.status, run.data?.current_stage)]),
  ) as Record<string, AutopilotStageStatus>, [run.data?.current_stage, run.data?.status, timeline.data])

  const completed = Object.values(statuses).filter((status) => status === 'completed' || status === 'skipped').length
  const activeStage = AUTOPILOT_STAGES.find((stage) => stage.id === (run.data?.current_stage || selectedStage))

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
              <div><span className="status-chip is-live">{run.data?.status ?? '读取中'}</span><h2>{run.data?.idea || '自动创作任务'}</h2><p>任务 ID：{runId}</p></div>
              <div className="live-actions">
                {!TERMINAL.has(run.data?.status ?? '') && <button type="button" className="secondary-button" disabled={action.isPending} onClick={() => action.mutate('cancel')}><Pause size={16} /> 停止任务</button>}
                {(run.data?.status === 'failed' || run.data?.status === 'cancelled') && <button type="button" className="primary-button" disabled={action.isPending} onClick={() => action.mutate('retry')}><RotateCcw size={16} /> 从当前工序重试</button>}
              </div>
            </div>
            <div className="global-progress"><div style={{ width: `${completed * 10}%` }} /><span>{completed}/10</span></div>
            <div className="current-stage-callout"><Play size={17} /><span>当前</span><strong>{activeStage?.label} · {activeStage?.title}</strong><ChevronRight size={16} /></div>
          </section>

          {(run.isError || timeline.isError) && <div className="inline-notice is-error"><AlertCircle size={17} /> 无法读取任务状态，请确认本地后端仍在线。</div>}

          <div className="autopilot-workbench-grid">
            <StageRail selectedStage={selectedStage} statuses={statuses} onSelect={setSelectedStage} />
            <div className="live-stage-column">
              <StageWorkspace stageId={selectedStage} readOnly />
              <section className="stage-output-panel">
                <div className="section-heading-row"><div><span className="eyebrow">LIVE OUTPUT</span><h3>本工序产物</h3></div><span className={`status-chip is-${statuses[selectedStage]}`}>{statuses[selectedStage]}</span></div>
                {artifacts.data?.filter((item) => (item.kind ?? item.type ?? '').includes(selectedStage)).length ? (
                  <ul>{artifacts.data.filter((item) => (item.kind ?? item.type ?? '').includes(selectedStage)).map((item, index) => <li key={item.artifact_id ?? item.id ?? index}><strong>{item.name ?? item.kind ?? item.type ?? '产物'}</strong><span>{item.local_path ?? item.path}</span></li>)}</ul>
                ) : (
                  <div className="stage-output-empty">{statuses[selectedStage] === 'running' ? 'Agent 正在写入本工序结果…' : statuses[selectedStage] === 'completed' ? '工序已完成，标准化结果已归档。' : '执行到这里后，产物会自动出现。'}</div>
                )}
              </section>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
