const path = require('path')

function buildBackendUrl(settings) {
  return `http://${settings.host}:${settings.backendPort}`
}

function buildFrontendDevUrl(settings) {
  return `${buildUiOrigin(settings)}/`
}

function buildUiOrigin(settings) {
  return `http://${settings.host}:${settings.frontendPort}`
}

function buildPythonPath(repoRoot, env = process.env) {
  return env.PYTHONPATH ? `${repoRoot}${path.delimiter}${env.PYTHONPATH}` : repoRoot
}

function buildBackendLaunch(settings, options) {
  if (options.isDev) {
    return {
      command: 'python',
      args: [
        '-m',
        'relief_story_agent.server',
        '--host',
        settings.host,
        '--port',
        String(settings.backendPort),
        '--ui-origin',
        buildUiOrigin(settings),
        '--state-dir',
        settings.stateDir,
        '--model-config',
        options.modelConfigPath,
        '--comfyui-endpoint',
        settings.comfyUiEndpoint,
        '--max-workers',
        '2',
        '--lease-seconds',
        '300',
        '--recovery-poll-seconds',
        '5',
      ],
      cwd: options.repoRoot,
      env: {
        ...options.env,
        PYTHONPATH: buildPythonPath(options.repoRoot, options.env),
      },
    }
  }

  return {
    command: path.join(
      options.resourcesPath,
      'bin',
      'relief-story-agent-api.exe',
    ),
    args: [
      '--host',
      settings.host,
      '--port',
      String(settings.backendPort),
      '--ui-origin',
      buildUiOrigin(settings),
      '--state-dir',
      settings.stateDir,
      '--comfyui-endpoint',
      settings.comfyUiEndpoint,
    ],
    cwd: undefined,
    env: options.env,
  }
}

module.exports = {
  buildBackendLaunch,
  buildBackendUrl,
  buildFrontendDevUrl,
  buildUiOrigin,
}
