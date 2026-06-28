import { SectionCard } from '../../../shared/components/SectionCard'
import demoPoster from '../../../assets/demo-poster.png'

export function FourGridPreview() {
  return (
    <SectionCard
      title="四宫格参考"
      description="为 LTX 2.3 workflow 准备 reference asset。"
    >
      <div className="video-slot">
        <img src={demoPoster} alt="四宫格视觉预览占位" />
        <div className="video-slot__footer">
          <span>后续替换为真实 four_grid_asset</span>
          <span>16:9</span>
        </div>
      </div>
    </SectionCard>
  )
}
