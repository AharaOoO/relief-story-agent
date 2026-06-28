import { Button } from '@heroui/react'
import { Cloud, Monitor } from 'lucide-react'
import { useUiStore } from '../../../shared/store/uiStore'
import type { GenerationMode } from '../../../shared/contracts/common.contract'

const modes: Array<{
  mode: GenerationMode
  label: string
  description: string
  icon: typeof Monitor
}> = [
  {
    mode: 'local_comfyui',
    label: 'Local ComfyUI',
    description: '使用本地 LTX/ComfyUI workflow',
    icon: Monitor,
  },
  {
    mode: 'runninghub_cloud',
    label: 'RunningHub Cloud',
    description: '使用 workflowId + nodeInfoList',
    icon: Cloud,
  },
]

export function GenerationModeSelector() {
  const selected = useUiStore((state) => state.selectedGenerationMode)
  const setSelected = useUiStore((state) => state.setSelectedGenerationMode)

  return (
    <div className="grid-two">
      {modes.map((item) => {
        const Icon = item.icon
        return (
          <Button
            className={selected === item.mode ? 'hero-button' : 'ghost-button'}
            key={item.mode}
            onPress={() => setSelected(item.mode)}
          >
            <Icon size={18} />
            <span>{item.label}</span>
          </Button>
        )
      })}
    </div>
  )
}
