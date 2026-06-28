import { SectionCard } from '../../../shared/components/SectionCard'
import { formatDate } from '../../../shared/utils/formatDate'

const events = [
  { at: new Date().toISOString(), title: '进入提示词审查', detail: '等待人工确认是否允许进入修正或 final prompts。' },
  { at: new Date().toISOString(), title: 'Quality gate passed', detail: '故事保持低刺激情绪缓冲，不包含强冲突。' },
]

export function RunEventsPanel() {
  return (
    <SectionCard title="Events" description="保留后端事件明细，避免吞掉错误。">
      <div className="timeline">
        {events.map((event) => (
          <div className="timeline-item" key={`${event.title}-${event.at}`}>
            <span className="timeline-dot">•</span>
            <div>
              <strong>{event.title}</strong>
              <p>{event.detail}</p>
            </div>
            <span>{formatDate(event.at)}</span>
          </div>
        ))}
      </div>
    </SectionCard>
  )
}
