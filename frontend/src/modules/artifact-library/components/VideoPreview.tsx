import demoPoster from '../../../assets/demo-poster.png'
import { SectionCard } from '../../../shared/components/SectionCard'
import { CopyButton } from '../../../shared/components/CopyButton'

export function VideoPreview() {
  const path = 'D:/relief_story_exports/batch_demo_001/publish_videos/publish_ready.mp4'

  return (
    <SectionCard
      title="视频预览"
      description="后端返回 URL 时使用 video；本地路径不可读时显示路径与复制按钮。"
      footer={<CopyButton value={path} label="复制视频路径" />}
    >
      <div className="video-slot">
        <img src={demoPoster} alt="视频预览 poster" />
        <div className="video-slot__footer">
          <span>预留演示视频位置</span>
          <span>poster</span>
        </div>
      </div>
    </SectionCard>
  )
}
