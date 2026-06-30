const path = require('node:path')

function createBackendCommand({
  isDev,
  repoRoot,
  resourcesPath,
  userDataPath,
  host,
  port,
  environment,
  processEnvironment,
}) {
  const stateDir = path.join(userDataPath, 'state')
  const commonArgs = [
    '--host',
    host,
    '--port',
    String(port),
    '--state-dir',
    stateDir,
    '--max-workers',
    '2',
    '--lease-seconds',
    '300',
    '--recovery-poll-seconds',
    '5',
  ]
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

