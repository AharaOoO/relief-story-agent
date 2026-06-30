import { useQuery } from '@tanstack/react-query'
import { ArrowDown, ArrowRight, Clapperboard, Layers3, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import { AUTOPILOT_STAGES } from '../features/autopilot/stages'
import { RunComposer } from '../features/run-composer/RunComposer'
import { listRuns } from '../features/workbench/workbench.api'
import { OceanVideoBackground } from '../shared/components/OceanVideoBackground'

export default function DashboardPage() {
  const runs = useQuery({ queryKey: ['runs', 'dashboard'], queryFn: listRuns, refetchInterval: 10_000 })
  const recent = runs.data?.items.slice(0, 3) ?? []

  return (
    <div className="dashboard-page">
      <section className="coast-hero">
        <OceanVideoBackground />
        <div className="coast-hero-content">
          <span className="hero-kicker"><Sparkles size={15} /> LTX 2.3 AUTOMATED DIRECTOR</span>
          <h1 aria-label="把一个想法，交给整条制片流水线"><span>把一个想法，</span><span>交给整条制片流水线</span></h1>
          <p>从故事、分镜、审查、四宫格参考图，到 ComfyUI / LTX 2.3 入队，一次设置，自动完成。</p>
          <div className="hero-actions">
            <a className="primary-button large" href="#new-production"><Clapperboard size={18} /> 开始一部新短剧</a>
            <Link className="glass-button" to="/autopilot"><Layers3 size={18} /> 查看十道工序</Link>
          </div>
        </div>
        <a className="hero-scroll" href="#new-production" aria-label="向下查看创作面板"><span>开始创作</span><ArrowDown size={17} /></a>
      </section>

      <section className="production-band" id="new-production">
        <div className="content-width">
          <div className="section-intro">
            <span className="eyebrow">ONE CLICK PRODUCTION</span>
            <h2>今天想拍什么？</h2>
            <p>输入灵感、完整剧本或一段创作要求。留空时，总编剧会从零敲定内核和冲突。</p>
          </div>
          <RunComposer />
        </div>
      </section>

      <section className="process-band">
        <div className="content-width">
          <div className="section-intro is-row">
            <div><span className="eyebrow">THE AUTOPILOT</span><h2>十道工序，一条自动流</h2></div>
            <Link className="text-link" to="/autopilot">配置每一道工序 <ArrowRight size={16} /></Link>
          </div>
          <ol className="process-grid">
            {AUTOPILOT_STAGES.map((stage) => (
              <li key={stage.id}>
                <span className="process-number">{String(stage.order).padStart(2, '0')}</span>
                <div><strong>{stage.label}</strong><span>{stage.title}</span></div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="recent-band">
        <div className="content-width">
          <div className="section-intro is-row">
            <div><span className="eyebrow">RECENT PRODUCTIONS</span><h2>最近任务</h2></div>
            <Link className="text-link" to="/tasks">全部任务 <ArrowRight size={16} /></Link>
          </div>
          {recent.length > 0 ? (
            <div className="recent-run-list">
              {recent.map((run) => (
                <Link key={run.run_id} to={`/run/${run.run_id}`}>
                  <span className={`run-state-dot is-${run.status}`} />
                  <div><strong>{run.idea || '自动创作任务'}</strong><span>{run.current_stage || '等待开始'}</span></div>
                  <span className="status-chip">{run.status}</span>
                  <ArrowRight size={17} />
                </Link>
              ))}
            </div>
          ) : (
            <div className="empty-panel"><Clapperboard size={26} /><strong>第一部作品正在等你</strong><span>上面的输入框留空也能开始。</span></div>
          )}
        </div>
      </section>
    </div>
  )
}
