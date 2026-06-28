import { CopyButton } from '../../../shared/components/CopyButton'
import { SectionCard } from '../../../shared/components/SectionCard'

const templateDir = 'D:/relief_story_config/templates'
const writerTemplate = 'prompt_writer.default.md'
const auditTemplate = 'prompt_audit.default.md'
const templateCheckCommand =
  'relief-story-agent template-check --writer-template "D:/relief_story_config/templates/prompt_writer.default.md" --audit-template "D:/relief_story_config/templates/prompt_audit.default.md"'

export function PromptTemplatePanel() {
  return (
    <SectionCard
      title="提示词模板目录"
      description="提示词模板是 Markdown 文件；改模板文件，不要改前端代码。"
      footer={<CopyButton value={templateCheckCommand} label="复制模板检查命令" />}
    >
      <div className="guide-grid">
        <div className="guide-item guide-item--wide">
          <span>推荐目录</span>
          <strong>{templateDir}</strong>
          <p>生成配置包时也会在输出目录下创建 templates/ 子目录。</p>
        </div>
        <div className="guide-item">
          <span>分镜提示词</span>
          <strong>{writerTemplate}</strong>
          <p>必须保留占位符：{'{{script_json}}'}。</p>
        </div>
        <div className="guide-item">
          <span>提示词审查</span>
          <strong>{auditTemplate}</strong>
          <p>必须保留占位符：{'{{script_json}}'} 和 {'{{storyboard_json}}'}。</p>
        </div>
      </div>
    </SectionCard>
  )
}
