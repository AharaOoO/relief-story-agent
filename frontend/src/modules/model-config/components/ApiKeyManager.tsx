import { Button, Input } from '@heroui/react'
import { Key, Save } from 'lucide-react'
import { useEffect, useState } from 'react'
import { SectionCard } from '../../../shared/components/SectionCard'

export function ApiKeyManager() {
  const [keys, setKeys] = useState({
    GEMINI_API_KEY: '',
    DEEPSEEK_API_KEY: '',
    OPENAI_API_KEY: '',
  })
  const [isSaving, setIsSaving] = useState(false)
  const isDesktop = typeof window !== 'undefined' && !!window.reliefDesktop

  useEffect(() => {
    if (isDesktop) {
      window.reliefDesktop!.getSettings().then((settings) => {
        setKeys((prev) => ({
          GEMINI_API_KEY: settings?.GEMINI_API_KEY || prev.GEMINI_API_KEY,
          DEEPSEEK_API_KEY: settings?.DEEPSEEK_API_KEY || prev.DEEPSEEK_API_KEY,
          OPENAI_API_KEY: settings?.OPENAI_API_KEY || prev.OPENAI_API_KEY,
        }))
      }).catch(err => {
        console.error('Failed to load settings', err)
      })
    }
  }, [isDesktop])

  const handleSave = async () => {
    if (!isDesktop) {
      window.alert('仅在桌面端可用')
      return
    }
    
    setIsSaving(true)
    try {
      await window.reliefDesktop!.saveSettings(keys)
      window.alert('API Keys 已加密保存，请重启桌面端以应用')
    } catch (err) {
      console.error(err)
      window.alert('保存失败')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <SectionCard
      title="API Key 设置"
      description="前端不回显明文。您的 Key 将被加密保存在本地设置中，重启桌面端生效。"
      tone="blue"
      footer={
        <Button
          className="hero-button"
          isLoading={isSaving}
          onPress={handleSave}
          startContent={!isSaving && <Save size={16} />}
        >
          保存配置
        </Button>
      }
    >
      <div className="stack" style={{ gap: '16px' }}>
        <Input
          label="Gemini API Key"
          placeholder="填入您的 Gemini API Key"
          type="password"
          variant="faded"
          value={keys.GEMINI_API_KEY}
          onValueChange={(val) => setKeys(p => ({ ...p, GEMINI_API_KEY: val }))}
          startContent={<Key size={16} className="text-default-400" />}
          description="总编剧或 Gemini 兼容模型使用"
        />
        <Input
          label="DeepSeek API Key"
          placeholder="填入您的 DeepSeek API Key"
          type="password"
          variant="faded"
          value={keys.DEEPSEEK_API_KEY}
          onValueChange={(val) => setKeys(p => ({ ...p, DEEPSEEK_API_KEY: val }))}
          startContent={<Key size={16} className="text-default-400" />}
          description="剧本润色阶段使用"
        />
        <Input
          label="OpenAI API Key"
          placeholder="填入您的 OpenAI API Key"
          type="password"
          variant="faded"
          value={keys.OPENAI_API_KEY}
          onValueChange={(val) => setKeys(p => ({ ...p, OPENAI_API_KEY: val }))}
          startContent={<Key size={16} className="text-default-400" />}
          description="提示词写作、审核、图像模型默认使用"
        />
      </div>
    </SectionCard>
  )
}
