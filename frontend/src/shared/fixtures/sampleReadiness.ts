import type { ReadinessStatus } from '../contracts/readiness.contract'

export const sampleReadiness: ReadinessStatus = {
  ready_for_configuration: true,
  ready_for_real_runs: false,
  ready_for_release: false,
  summary: {
    real_run_blocking_count: 3,
    release_blocking_count: 7,
    warning_count: 2,
  },
  blockers: [
    {
      code: 'missing_model_keys',
      title: '模型 API key 尚未配置',
      detail: 'GEMINI_API_KEY、DEEPSEEK_API_KEY、OPENAI_API_KEY 需要由本机环境变量提供。',
      suggested_action: '在系统环境变量中配置 key 后重启后端服务。',
    },
    {
      code: 'acceptance_video_missing',
      title: '真实本地视频证据缺失',
      detail: 'release readiness 需要一个真实 completed run 和可识别容器签名的视频文件。',
      suggested_action: '完成单条 real run 后刷新 acceptance-status。',
    },
  ],
  warnings: [
    {
      code: 'comfyui_optional',
      title: 'ComfyUI 输出仍需人工确认',
      detail: '如果 /history 还没有 outputs，不要重复入队同一个昂贵任务。',
    },
  ],
  checks: [
    { name: 'local bootstrap', status: 'passed', detail: '本地路径和基础包可用' },
    { name: 'persistent scheduler', status: 'passed', detail: 'state-dir 可读写' },
    { name: 'model keys', status: 'failed', detail: '缺少真实模型 key' },
    { name: 'release acceptance', status: 'failed', detail: '缺少最终证据包' },
  ],
}
