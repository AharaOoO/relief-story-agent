const path = require('node:path')

function createBackendCommand({
  isDev,
  repoRoot,
  resourcesPath,
  userDataPath,
  host,
  port,
  uiOrigin = 'null',
  extraCorsOrigins = [],
  environment,
  runtimeConfig = {},
  processEnvironment,
}) {
  const integerSetting = (name, fallback, maximum) => {
    const value = Number(runtimeConfig[name])
    return Number.isInteger(value) && value >= 1 && value <= maximum ? value : fallback
  }
  const stateDir = path.join(userDataPath, 'state')
  const commonArgs = [
    '--host',
    host,
    '--port',
    String(port),
    '--state-dir',
    stateDir,
    '--ui-origin',
    uiOrigin,
    '--max-workers',
    String(integerSetting('max_workers', 2, 8)),
    '--lease-seconds',
    '300',
    '--recovery-poll-seconds',
    '5',
    '--image-generation-concurrency',
    String(integerSetting('image_generation_concurrency', 2, 4)),
    '--comfyui-submission-concurrency',
    String(integerSetting('comfyui_submission_concurrency', 1, 4)),
  ]
  if (typeof runtimeConfig.comfyui_endpoint === 'string' && runtimeConfig.comfyui_endpoint.trim()) {
    commonArgs.push('--comfyui-endpoint', runtimeConfig.comfyui_endpoint.trim())
  }
  for (const origin of extraCorsOrigins) {
    commonArgs.push('--cors-origin', origin)
  }
  const env = { ...processEnvironment, ...environment }

  if (!isDev) {
    return {
      command: path.join(resourcesPath, 'bin', 'relief-story-agent-api.exe'),
      args: commonArgs,
      cwd: resourcesPath,
      env,
    }
  }

  const modelConfig = path.join(
    repoRoot,
    'relief_story_agent',
    'examples',
    'model_config.local.example.json',
  )
  env.PYTHONPATH = processEnvironment.PYTHONPATH
    ? `${repoRoot}${path.delimiter}${processEnvironment.PYTHONPATH}`
    : repoRoot
  return {
    command: 'python',
    args: [
      '-m',
      'relief_story_agent.server',
      ...commonArgs,
      '--model-config',
      modelConfig,
    ],
    cwd: repoRoot,
    env,
  }
}

module.exports = { createBackendCommand }
