import { SectionCard } from '../../../shared/components/SectionCard'
import { StatusBadge } from '../../../shared/components/StatusBadge'
import type { StoryboardShot } from '../../../shared/fixtures/sampleRun'

export function StoryboardCard({ shot }: { shot: StoryboardShot }) {
  return (
    <SectionCard
      title={shot.title}
      description={shot.camera}
      action={<StatusBadge status={shot.status} />}
    >
      <div className="stack">
        <div className="alert-box">
          <h3>Image Prompt</h3>
          <p>{shot.imagePrompt}</p>
        </div>
        <div className="alert-box">
          <h3>Negative Prompt</h3>
          <p>{shot.negativePrompt}</p>
        </div>
      </div>
    </SectionCard>
  )
}
