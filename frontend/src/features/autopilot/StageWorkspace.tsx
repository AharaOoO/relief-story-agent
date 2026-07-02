import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronDown, Image as ImageIcon, Info, KeyRound, Save } from 'lucide-react'
import { AUTOPILOT_STAGES } from './stages'
import { fetchProviderCatalog, type GridImageRetryOverride } from '../workbench/workbench.api'
import { useRunDraft } from '../run-composer/runDraft.store'
import {
  defaultRunningHubModel,
  MODEL_STAGE_IDS,
  recommendedRunningHubModels,
  runningHubModelOptions,
  STANDARD_STAGE_MODEL_PRESETS,
  type ModelStageId,
  type RunningHubSite,
  type RunRequestPayload,
  type StageModelDraft,
} from '../run-composer/runRequest.builder'
import type { RecoveryDraft } from './recoveryDraft'
import { ModelCombobox } from './ModelCombobox'

const PROMPT_HINTS: Record<ModelStageId, string> = {
  chief_screenwriter: '指挥总编剧如何确定题材、内核、人物动机与核心矛盾。',
  deepseek_polish: '规定改稿的节奏、影视化标准、台词风格和必须保留的内容。',
  quality_gate: '定义剧本通过门槛，例如逻辑闭环、情绪节奏和低刺激原则。',
  gpt_prompt_writer: '定义导演运镜、镜头语言、LTX 2.3 与四宫格提示词格式。',
  gpt_prompt_audit: '定义如何检查人物一致性、空间连续性、运镜和生成漏洞。',
  gpt_prompt_reviser: '定义依据审查报告进行修补时，什么能改、什么必须保留。',
}

type StageWorkspaceProps = {
  stageId: string
  readOnly?: boolean
  runRequest?: RunRequestPayload
  promptSnapshot?: Partial<Record<ModelStageId, string>>
  recovery?: {
    value: RecoveryDraft
    onChange: (value: RecoveryDraft) => void
  }
}

export function StageWorkspace({
  stageId,
  readOnly = false,
  runRequest,
  promptSnapshot,
  recovery,
}: StageWorkspaceProps) {
  const stage = AUTOPILOT_STAGES.find((item) => item.id === stageId) ?? AUTOPILOT_STAGES[0]
  const { draft, patchDraft } = useRunDraft()
  const catalog = useQuery({
    queryKey: ['provider-catalog'],
    queryFn: fetchProviderCatalog,
    staleTime: 5 * 60_000,
  })
  const modelStageId = MODEL_STAGE_IDS.includes(stage.id as ModelStageId)
    ? (stage.id as ModelStageId)
    : null
  const isGridImageStage = stage.id === 'four_grid_asset'
  const isComfyUIStage = stage.id === 'comfyui'
  const runModel = modelStageId ? runRequest?.model_configs?.[modelStageId] : undefined
  const currentModel = modelStageId
    ? (recovery?.value.stageModels[modelStageId]
      ?? (runRequest ? runModel : draft.stageModels[modelStageId]))
    : undefined
  const providerMode = currentModel?.provider_mode ?? 'openai_compatible'
  const site = (currentModel?.runninghub_site ?? draft.runninghubSite) as RunningHubSite
  const models = modelStageId
    ? Array.from(new Set([
      ...(currentModel?.model ? [currentModel.model] : []),
      ...(catalog.data?.runninghub[site].models ?? runningHubModelOptions(site, modelStageId)),
    ]))
    : []
  const recommendedModels = modelStageId
    ? (catalog.data?.runninghub[site].recommended_by_stage[modelStageId]
      ?? recommendedRunningHubModels(site, modelStageId))
    : []
  const standardModels = modelStageId ? (STANDARD_STAGE_MODEL_PRESETS[modelStageId] ?? []) : []
  const [runtime, setRuntime] = useState<Record<string, unknown>>({})
  const [secretStatus, setSecretStatus] = useState<Record<string, { configured: boolean; masked: string }>>({})
  const frozenGridImage = runRequest?.comfyui?.grid_image
  const gridImageSite = recovery?.value.gridImage.runninghub_site
    ?? frozenGridImage?.runninghub_site
    ?? draft.gridImageSite
  const gridImageAspectRatio = recovery?.value.gridImage.aspect_ratio
    ?? frozenGridImage?.aspect_ratio
    ?? draft.aspectRatio
  const gridImageResolution = recovery?.value.gridImage.resolution
    ?? frozenGridImage?.resolution
    ?? draft.imageResolution
  const gridImageSecretName = gridImageSite === 'cn'
    ? 'RUNNINGHUB_CN_API_KEY'
    : 'RUNNINGHUB_AI_API_KEY'
  const gridImageSecretStatus = secretStatus[gridImageSecretName]
  const comfyuiConfig = recovery?.value.comfyui ?? {
    endpoint: runRequest?.comfyui?.endpoint ?? draft.comfyuiEndpoint,
    workflow_api_path: runRequest?.comfyui?.workflow_api_path ?? (draft.workflowPath || null),
    output_timeout_seconds: runRequest?.comfyui?.output_timeout_seconds ?? 600,
  }

  useEffect(() => {
    if (!window.reliefDesktop) return
    void Promise.all([
      window.reliefDesktop.getRuntimeConfig(),
      window.reliefDesktop.getSecretStatus?.() ?? Promise.resolve({}),
    ]).then(([savedRuntime, savedSecretStatus]) => {
      setRuntime(savedRuntime)
      setSecretStatus(savedSecretStatus)
    }).catch(() => undefined)
    const listener = (event: Event) => {
      setRuntime((event as CustomEvent<Record<string, unknown>>).detail)
    }
    window.addEventListener('relief:runtime-config', listener)
    return () => window.removeEventListener('relief:runtime-config', listener)
  }, [])

  const resolveStandardPreset = (preset: (typeof standardModels)[number]) => {
    const prefix = preset.api_key_env === 'GEMINI_API_KEY'
      ? 'gemini'
      : preset.api_key_env === 'DEEPSEEK_API_KEY'
        ? 'deepseek'
        : 'openai'
    const baseUrl = runtime[`${prefix}_base_url`]
    const configuredModel = runtime[`${prefix}_model`]
    return {
      ...preset,
      ...(typeof baseUrl === 'string' && baseUrl.trim() ? { base_url: baseUrl.trim() } : {}),
      ...(typeof configuredModel === 'string' && configuredModel.trim() && standardModels.length === 1
        ? { model: configuredModel.trim() }
        : {}),
    }
  }

  const toStageModel = (preset: (typeof standardModels)[number]) => {
    const { label: _label, ...config } = resolveStandardPreset(preset)
    return config
  }

  const setStageModel = (model: StageModelDraft) => {
    if (!modelStageId) return
    if (recovery) {
      recovery.onChange({
        ...recovery.value,
        stageModels: { ...recovery.value.stageModels, [modelStageId]: model },
      })
      return
    }
    patchDraft({ stageModels: { ...draft.stageModels, [modelStageId]: model } })
  }

  const patchModel = (patch: Partial<StageModelDraft>) => {
    setStageModel({
      provider_mode: 'runninghub',
      runninghub_site: site,
      model: models[0] ?? '',
      ...currentModel,
      ...patch,
    })
  }

  const switchProviderMode = (mode: 'runninghub' | 'openai_compatible') => {
    if (!modelStageId) return
    if (mode === 'runninghub') {
      const targetSite = currentModel?.runninghub_site ?? draft.runninghubSite
      setStageModel({
        provider_mode: 'runninghub',
        runninghub_site: targetSite,
        model: defaultRunningHubModel(targetSite, modelStageId),
      })
      return
    }
    const preset = standardModels[0] ? toStageModel(standardModels[0]) : undefined
    if (preset) setStageModel({ provider_mode: 'openai_compatible', ...preset })
  }

  const patchPrompt = (value: string) => {
    if (!modelStageId) return
    if (recovery) {
      recovery.onChange({
        ...recovery.value,
        stagePrompts: { ...recovery.value.stagePrompts, [modelStageId]: value },
      })
      return
    }
    patchDraft({ stagePrompts: { ...draft.stagePrompts, [modelStageId]: value } })
  }

  const patchGridImage = (patch: Partial<GridImageRetryOverride>) => {
    if (recovery) {
      recovery.onChange({
        ...recovery.value,
        gridImage: { ...recovery.value.gridImage, ...patch },
      })
      return
    }
    patchDraft({
      ...(patch.runninghub_site ? { gridImageSite: patch.runninghub_site } : {}),
      ...(patch.aspect_ratio ? { aspectRatio: patch.aspect_ratio } : {}),
      ...(patch.resolution ? { imageResolution: patch.resolution } : {}),
    })
  }

  const patchComfyUI = (patch: Partial<RecoveryDraft['comfyui']>) => {
    if (!recovery) return
    recovery.onChange({
      ...recovery.value,
      comfyui: { ...recovery.value.comfyui, ...patch },
    })
  }

  const currentPrompt = modelStageId
    ? (recovery?.value.stagePrompts[modelStageId]
      ?? (runRequest
        ? (promptSnapshot?.[modelStageId]
          ?? runRequest.prompt_profile?.stage_overrides?.[modelStageId]
          ?? '')
        : (draft.stagePrompts[modelStageId] ?? '')))
    : ''

  return (
    <section className="stage-workspace">
      <header className="stage-workspace-header">
        <div className="stage-big-number">{String(stage.order).padStart(2, '0')}</div>
        <div><span className="eyebrow">{stage.label}</span><h2>{stage.title}</h2><p>{stage.description}</p></div>
      </header>

      {modelStageId ? (
        <div className="stage-config-body">
          {recovery && !readOnly && (
            <div className="inline-notice recovery-edit-notice"><Info size={17} /><span><strong>恢复编辑</strong> 仅修改本次失败任务中尚未完成的工序。</span></div>
          )}
          <div className="provider-mode-row">
            <div><strong>模型调用模式</strong><span>普通模型 API 适合个人 key；RunningHub LLM 端点需要企业共享 key。</span></div>
            <div className="segmented-control">
              <button type="button" disabled={readOnly} className={providerMode === 'runninghub' ? 'is-active' : ''} onClick={() => switchProviderMode('runninghub')}>RunningHub 企业模型 API</button>
              <button type="button" disabled={readOnly} className={providerMode === 'openai_compatible' ? 'is-active' : ''} onClick={() => switchProviderMode('openai_compatible')}>普通模型 API</button>
            </div>
          </div>
          {providerMode === 'runninghub' ? (
            <>
              <div className="stage-config-row">
                <div className="field-stack"><span>服务站点</span><div className="model-site-segmented" role="group" aria-label="RunningHub 服务站点">
                  {(['cn', 'ai'] as const).map((targetSite) => (
                    <button
                      type="button"
                      key={targetSite}
                      disabled={readOnly}
                      className={site === targetSite ? 'is-active' : ''}
                      aria-pressed={site === targetSite}
                      onClick={() => {
                        const recommendation = catalog.data?.runninghub[targetSite].recommended_by_stage[modelStageId]?.[0]
                          ?? defaultRunningHubModel(targetSite, modelStageId)
                        setStageModel({ provider_mode: 'runninghub', runninghub_site: targetSite, model: recommendation })
                      }}
                    >
                      <span>{targetSite === 'cn' ? '国内站' : '国际站'}</span>
                      <small>.{targetSite}</small>
                    </button>
                  ))}
                </div></div>
                <ModelCombobox
                  label="本工序模型"
                  value={currentModel?.model ?? models[0] ?? ''}
                  models={models}
                  recommended={recommendedModels}
                  disabled={readOnly || catalog.isLoading}
                  onChange={(model) => patchModel({ model })}
                />
              </div>
              {!readOnly && <div className="editor-note"><Info size={15} /><span>这里读取独立的 RUNNINGHUB_{site.toUpperCase()}_SHARED_API_KEY，单次生成最长等待 5 分钟。个人/会员 key 只能用于 G2。</span></div>}
            </>
          ) : (
            <div className="stage-config-row is-single">
              <label className="field-stack"><span>本工序模型</span><div className="select-shell"><select disabled={readOnly} value={currentModel?.model ?? standardModels[0]?.model ?? ''} onChange={(event) => {
                const preset = standardModels.find((item) => item.model === event.target.value)
                if (preset) setStageModel({ provider_mode: 'openai_compatible', ...toStageModel(preset) })
              }}>{standardModels.map((preset) => <option value={preset.model} key={preset.model}>{preset.label}</option>)}</select><ChevronDown size={16} /></div></label>
              <div className="provider-endpoint-note"><Info size={15} /><span>{currentModel?.base_url ?? standardModels[0]?.base_url}<br />密钥：{currentModel?.api_key_env ?? standardModels[0]?.api_key_env}</span></div>
            </div>
          )}
          <label className="field-stack prompt-editor"><span>本工序提示词模板</span><textarea disabled={readOnly} value={currentPrompt} onChange={(event) => patchPrompt(event.target.value)} placeholder={`${PROMPT_HINTS[modelStageId]} 留空时使用内置专业模板。`} /></label>
          <div className="editor-note"><Info size={15} /><span>已完成工序保持冻结；本次修改只应用于失败工序及其后的未完成工序。</span></div>
          {!readOnly && <div className="auto-save-note"><Save size={15} /> {recovery ? '修改已保留，等待保存并重试' : '已自动保存在本机草稿'}</div>}
        </div>
      ) : isGridImageStage ? (
        <div className="stage-config-body grid-image-stage-config">
          {recovery && !readOnly && <div className="inline-notice recovery-edit-notice"><Info size={17} /><span><strong>恢复编辑</strong> 修改只在本次重试中应用，不会改变新任务默认值。</span></div>}
          <div className="provider-mode-row">
            <div><strong>G2 生图服务站点</strong><span>国内站与国际站使用不同的 API Key；这里不会修改前六步 LLM 模型。</span></div>
            <div className="segmented-control" aria-label="G2 生图服务站点">
              <button type="button" disabled={readOnly} className={gridImageSite === 'cn' ? 'is-active' : ''} onClick={() => patchGridImage({ runninghub_site: 'cn' })}>国内站 .cn</button>
              <button type="button" disabled={readOnly} className={gridImageSite === 'ai' ? 'is-active' : ''} onClick={() => patchGridImage({ runninghub_site: 'ai' })}>国际站 .ai</button>
            </div>
          </div>
          <div className="grid-image-config-row">
            <div className="grid-image-model-summary"><ImageIcon size={20} /><div><span>生图模型</span><strong>RunningHub G2</strong><small>rhart-image-g-2</small></div></div>
            <label className="field-stack"><span>画面比例</span><div className="select-shell"><select disabled={readOnly} value={gridImageAspectRatio} onChange={(event) => patchGridImage({ aspect_ratio: event.target.value as '16:9' | '9:16' })}><option value="16:9">横屏 16:9</option><option value="9:16">竖屏 9:16</option></select><ChevronDown size={16} /></div></label>
            <label className="field-stack"><span>生成清晰度</span><div className="select-shell"><select disabled={readOnly} value={gridImageResolution} onChange={(event) => patchGridImage({ resolution: event.target.value as '1k' | '2k' })}><option value="2k">2K 清晰</option><option value="1k">1K 快速</option></select><ChevronDown size={16} /></div></label>
          </div>
          <div className={`inline-notice ${gridImageSecretStatus && !gridImageSecretStatus.configured ? 'is-warning' : ''}`}><KeyRound size={17} /><span>{gridImageSecretStatus?.configured ? `当前站点密钥已配置：${gridImageSecretStatus.masked}` : gridImageSecretStatus ? '当前站点尚未配置 G2 密钥，请在高级设置中保存后再运行。' : '本工序将读取对应站点的个人/会员 G2 密钥。'}<strong>{gridImageSecretName}</strong></span></div>
          <div className="editor-note"><Info size={15} /><span>站点、比例与清晰度会随任务冻结，恢复修改不会污染新任务默认值。</span></div>
          {!readOnly && <div className="auto-save-note"><Save size={15} /> {recovery ? '等待保存修改并重试' : '已自动保存到本机草稿'}</div>}
        </div>
      ) : isComfyUIStage && (runRequest || recovery) ? (
        <div className="stage-config-body comfyui-recovery-config">
          {recovery && !readOnly && <div className="inline-notice recovery-edit-notice"><Info size={17} /><span><strong>恢复编辑</strong> 可修正 ComfyUI 地址、工作流和等待时长后再重试。</span></div>}
          <div className="stage-config-row">
            <label className="field-stack"><span>ComfyUI 地址</span><input disabled={readOnly} value={comfyuiConfig.endpoint} onChange={(event) => patchComfyUI({ endpoint: event.target.value })} /></label>
            <label className="field-stack"><span>最长等待（秒）</span><input disabled={readOnly} type="number" min="1" value={comfyuiConfig.output_timeout_seconds} onChange={(event) => patchComfyUI({ output_timeout_seconds: Number(event.target.value) || 1 })} /></label>
          </div>
          <label className="field-stack"><span>工作流 JSON 路径</span><input disabled={readOnly} value={comfyuiConfig.workflow_api_path ?? ''} onChange={(event) => patchComfyUI({ workflow_api_path: event.target.value || null })} /></label>
          <div className="editor-note"><Info size={15} /><span>已完成工序不会重跑；修改只会在第 10 步尚未完成时提交。</span></div>
        </div>
      ) : (
        <div className="stage-automatic-panel">
          <span className="stage-automatic-icon">{stage.order}</span>
          <div><strong>这一道由流水线自动完成</strong><p>它会读取前序工序的标准化产物，不需要普通用户额外配置。</p></div>
        </div>
      )}
    </section>
  )
}
