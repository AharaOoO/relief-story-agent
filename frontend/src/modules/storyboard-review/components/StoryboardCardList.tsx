import { sampleStoryboard } from '../../../shared/fixtures/sampleRun'
import { StoryboardCard } from './StoryboardCard'

export function StoryboardCardList() {
  return (
    <div className="stack">
      {sampleStoryboard.map((shot) => (
        <StoryboardCard key={shot.id} shot={shot} />
      ))}
    </div>
  )
}
