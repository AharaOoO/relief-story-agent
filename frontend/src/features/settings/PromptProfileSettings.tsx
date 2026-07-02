import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Copy, LoaderCircle, RotateCcw, Save } from 'lucide-react'
import { MODEL_STAGE_IDS, type ModelStageId } from '../run-composer/runRequest.builder'
import { useRunDraft } from '../run-composer/runDraft.store'
import {
  clonePromptProfile,
  listPromptProfiles,
  resetPromptProfile,
  updatePromptProfile,
  type PromptProfile,
} from '../workbench/workbench.api'

const LABELS: Record<ModelStageId, string> = {
  chief_screenwriter: '1 备料 · 总编剧',
  deepseek_polish: '2 慢炖 · 影视化改稿',
  quality_gate: '3 试味 · 质量门禁',
  gpt_prompt_writer: '4 配菜 · 导演分镜',
  gpt_prompt_audit: '5 调味 · 提示词审查',
  gpt_prompt_reviser: '6 回锅 · 提示词修订',
}

export function PromptProfileSettings() {
  const queryClient = useQueryClient()
  const profiles = useQuery({ queryKey: ['prompt-profiles'], queryFn: listPromptProfiles })
  const { draft: runDraft, patchDraft: patchRunDraft } = useRunDraft()
  const [selectedId, setSelectedId] = useState(runDraft.promptProfileId || 'system-default')
  const [profileDraft, setProfileDraft] = useState<PromptProfile | null>(null)
  const [message, setMessage] = useState('')

  const selected = profiles.data?.items.find((profile) => profile.id === selectedId) ?? profiles.data?.items[0]

  useEffect(() => {
    if (!selected) return
    setProfileDraft({ ...selected, stages: { ...selected.stages } })
  }, [selected])

  const mutation = useMutation({
    mutationFn: async (action: 'clone' | 'save' | 'reset') => {
      if (!profileDraft) throw new Error('请先选择提示词模板。')
      if (action === 'clone') return clonePromptProfile(profileDraft.id, `${profileDraft.name === 'System Default' ? '我的专业模板' : `${profileDraft.name} 副本`}`)
      if (action === 'reset') return resetPromptProfile(profileDraft.id)
      return updatePromptProfile(profileDraft)
    },
    onMutate: (action) => setMessage(action === 'save' ? '正在保存提示词模板…' : action === 'reset' ? '正在恢复系统默认模板…' : '正在复制为可编辑模板…'),
    onSuccess: async (profile) => {
      await queryClient.invalidateQueries({ queryKey: ['prompt-profiles'] })
      setSelectedId(profile.id)
      setProfileDraft(profile)
      patchRunDraft({ promptProfileId: profile.id, promptProfileVersion: profile.version, stagePrompts: {} })
      setMessage(`已保存并用于新任务：${profile.name} v${profile.version}`)
    },
    onError: (error) => setMessage(error instanceof Error ? error.message : '提示词模板操作失败'),
  })

  if (profiles.isLoading) return <div className="loading-row"><LoaderCircle className="spin" /> 正在读取提示词模板…</div>
  if (!profileDraft) return <div className="inline-notice is-warning">后端没有返回可用的提示词模板。</div>

  const readOnly = profileDraft.source === 'system'
  const chooseForRuns = () => {
    patchRunDraft({ promptProfileId: profileDraft.id, promptProfileVersion: profileDraft.version, stagePrompts: {} })
    setMessage(`新任务将使用：${profileDraft.name} v${profileDraft.version}`)
  }

  return (
    <div className="settings-section prompt-profile-settings">
      <div><h3>提示词模板</h3><p>六道模型工序共用一个版本化模板；任务创建时会冻结快照。</p></div>
      <div className="profile-toolbar">
        <label className="field-stack"><span>模板</span><select value={profileDraft.id} onChange={(event) => setSelectedId(event.target.value)}>{profiles.data?.items.map((profile) => <option key={profile.id} value={profile.id}>{profile.name} · v{profile.version}</option>)}</select></label>
        <label className="field-stack"><span>名称</span><input disabled={readOnly} value={profileDraft.name} onChange={(event) => setProfileDraft((current) => current ? { ...current, name: event.target.value } : current)} /></label>
      </div>
      <div className="prompt-profile-grid">
        {MODEL_STAGE_IDS.map((stage) => <label className="field-stack" key={stage}><span>{LABELS[stage]}</span><textarea disabled={readOnly} value={profileDraft.stages[stage] ?? ''} onChange={(event) => setProfileDraft((current) => current ? { ...current, stages: { ...current.stages, [stage]: event.target.value } } : current)} /></label>)}
      </div>
      <div className="settings-action-row">
        <button type="button" className="secondary-button" onClick={chooseForRuns}>用于新任务</button>
        {readOnly ? <button type="button" className="primary-button" disabled={mutation.isPending} onClick={() => mutation.mutate('clone')}><Copy size={16} /> 复制为可编辑模板</button> : <><button type="button" className="secondary-button" disabled={mutation.isPending} onClick={() => mutation.mutate('reset')}><RotateCcw size={16} /> 恢复系统默认</button><button type="button" className="primary-button" disabled={mutation.isPending || !profileDraft.name.trim()} onClick={() => mutation.mutate('save')}>{mutation.isPending ? <LoaderCircle className="spin" size={16} /> : <Save size={16} />} 保存模板</button></>}
      </div>
      {message && <div className="settings-message" role="status">{message}</div>}
    </div>
  )
}
