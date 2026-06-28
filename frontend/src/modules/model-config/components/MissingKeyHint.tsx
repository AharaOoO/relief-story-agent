import { CopyButton } from '../../../shared/components/CopyButton'
import { SectionCard } from '../../../shared/components/SectionCard'

const envCommand = [
  "[Environment]::SetEnvironmentVariable('GEMINI_API_KEY','填入你的 Gemini key','User')",
  "[Environment]::SetEnvironmentVariable('DEEPSEEK_API_KEY','填入你的 DeepSeek key','User')",
  "[Environment]::SetEnvironmentVariable('OPENAI_API_KEY','填入你的 OpenAI key','User')",
].join('\n')

export function MissingKeyHint() {
  return (
    <SectionCard
      title="API key 保存方式"
      description="前端不保存、不回显、不上传明文 API key。模型只读取环境变量名。"
      tone="blue"
      footer={<CopyButton value={envCommand} label="复制 PowerShell 设置命令" />}
    >
      <div className="guide-grid">
        <div className="guide-item">
          <span>保存位置</span>
          <strong>Windows 用户环境变量</strong>
          <p>设置后重启桌面端或启动脚本，后端才能读到新 key。</p>
        </div>
        <div className="guide-item">
          <span>Gemini</span>
          <strong>GEMINI_API_KEY</strong>
          <p>总编剧或 Gemini 兼容模型使用。</p>
        </div>
        <div className="guide-item">
          <span>DeepSeek</span>
          <strong>DEEPSEEK_API_KEY</strong>
          <p>剧本润色阶段使用。</p>
        </div>
        <div className="guide-item">
          <span>OpenAI / 图像</span>
          <strong>OPENAI_API_KEY</strong>
          <p>提示词写作、审核、图像模型默认使用。</p>
        </div>
      </div>
    </SectionCard>
  )
}
