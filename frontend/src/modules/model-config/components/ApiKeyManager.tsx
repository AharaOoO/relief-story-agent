import { Settings2 } from 'lucide-react'

export function ApiKeyManager() {
  return (
    <div className="inline-notice is-warning">
      <Settings2 size={17} />
      API Key 已迁移到全局“高级设置”抽屉，并使用 Windows 加密存储。
    </div>
  )
}
